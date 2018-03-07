# -*- coding: utf-8 -*-

# Copyright (C) 2017 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


import asyncio
import contextlib
import itertools
import functools


from appkit import (
    Null,
    utils
)
from appkit.blocks import (
    cache,
    httpclient,
    quicklogging
)
from appkit.db import sqlalchemyutils as sautils


from arroyo import kit
from arroyo.helpers import (
    database,
    downloads,
    filterengine,
    mediaparser,
    scanner
)


def unroll(fn):
    @functools.wraps(fn)
    def _wrapper(*args, **kwargs):
        ret = []
        for x in fn(*args, **kwargs):
            ret.append(x)

        return ret

    return _wrapper


class Arroyo(kit.Application):
    """
    Implement arroyo over customized kit.Application
    """

    DEFAULT_PLUGINS = [
        'commands.download',
        'commands.settings',

        'downloaders.mock',

        'filters.episode',
        'filters.movie',
        'filters.source',
        'filters.state',
        'filters.tags',

        'providers.epublibre',
        'providers.eztv',
        'providers.torrentapi'
    ]

    DEFAULT_SETTINGS = {
        kit.SettingsKeys.LOG_LEVEL: 'INFO',
        kit.SettingsKeys.COMMANDS_NS + 'settings.enabled': False,
        kit.SettingsKeys.ENABLE_CACHE: True,
        kit.SettingsKeys.DOWNLOADER: 'mock',
        kit.SettingsKeys.DB_URI: (
            'sqlite:///' +
            utils.user_path(utils.UserPathType.DATA, 'arroyo.db', create=True))
    }

    def __init__(self):
        super().__init__(
            name='arroyo',
            logger=kit.QuickLogger(level=quicklogging.Level.WARNING))

        # Open database connection
        db_uri = self.settings.get(kit.SettingsKeys.DB_URI)
        # Add check_same_thread=False to db_uri.
        # FIXME: This is a _hack_ required by the webui plugin.
        if '?' in db_uri:
            db_uri += '&check_same_thread=False'
        else:
            db_uri += '?check_same_thread=False'
        self._db_sess = sautils.create_session(db_uri)

        # Initialize app variables
        self.variables = sautils.KeyValueManager(kit.Variable, self._db_sess)

        # Register extension points
        self.register_extension_point(kit.FilterExtension)
        self.register_extension_point(kit.ProviderExtension)
        self.register_extension_point(kit.DownloaderExtension)

        # Initialize database controller
        self.db = database.Database(self._db_sess)

        # app.register_extension_class(DownloadSyncCronTask)
        # app.register_extension_class(DownloadQueriesCronTask)
        # app.signals.register('source-state-change')

        # Initialize app caches
        self.caches = {
            kit.Caches.SCAN: cache.NullCache()
        }

        # Initialize plugins
        plugin_enabled_key_tmpl = (
            kit.SettingsKeys.PLUGINS_NS + '{name}.enabled'
        )

        for plugin in self.DEFAULT_PLUGINS:
            settings_key = plugin_enabled_key_tmpl.format(name=plugin)

            if self.settings.get(settings_key, True):
                self.load_plugin(plugin)

            else:
                msg = 'Plugin "{name}" disabled by config'
                msg = msg.format(name=plugin)
                self.logger.info(msg)

    #
    # Own methods
    #

    @property
    def downloads(self):
        downloader_plugin = self.settings.get(kit.SettingsKeys.DOWNLOADER)
        return self.get_downloader(downloader_plugin)

    def get_providers(self):
        return [(name, self.get_provider(name))
                for name in
                self.get_extension_names_for(kit.ProviderExtension)]

    def get_provider(self, name):
        default_settings_key_tmpl = (
            kit.SettingsKeys.PROVIDERS_NS + '{name}.default-{key}'
        )
        override_settings_key_tmpl = (
            kit.SettingsKeys.PROVIDERS_NS + '{name}.force-{key}'
        )

        # Build provider's defaults and overrides from settings
        fields = ['language', 'type']

        overrides = {}
        defaults = {}

        for field in fields:
            default_key = default_settings_key_tmpl.format(name=name,
                                                           key=field)
            override_key = override_settings_key_tmpl.format(name=name,
                                                             key=field)
            default_value = self.settings.get(default_key, None)
            override_value = self.settings.get(override_key, None)

            if default_value:
                default_value[name][field] = default_value

            if override_value:
                overrides[name][field] = override_value

        return self.get_extension(kit.ProviderExtension, name,
                                  defaults=defaults, overrides=overrides)

    def get_filters(self):
        return self.get_extensions_for(kit.FilterExtension)

    def get_filter(self, name):
        return self.get_extension(kit.FilterExtension, name)

    def get_downloader(self, name):
        return self.get_extension(kit.DownloaderExtension, name)

    def search(self, query):
        def _post_process(items):
            mp = mediaparser.MediaParser(
                logger=self.logger.getChild('mediaparser'))

            for src, metatags in items:
                try:
                    entity, tags = mp.parse(src, metatags=metatags)

                except (mediaparser.InvalidEntityTypeError,
                        mediaparser.InvalidEntityArgumentsError) as e:
                    err = "Unable to parse '{name}': {e}"
                    err = err.format(name=src.name, e=e)
                    self.logger.error(err)
                    continue

                src.entity = entity
                src.tags = tags
                yield src

        try:
            results = self.caches[kit.Caches.SCAN].get(query)
            msg = "Scan data found in cache"
            self.logger.debug(msg)

        except KeyError:
            msg = "Scan data missing from cache"
            self.logger.debug(msg)

            s = scanner.Scanner(logger=self.logger,
                                providers=self.get_providers())
            sources_and_metas = s.scan(query)
            results = list(_post_process(sources_and_metas))

            self.caches[kit.Caches.SCAN].set(query, results)

        # Processed results can't be cached due a error
        # in serialization of tags
        return results

    def filter(self, results, query, ignore_state=False):
        filters = self.get_filters()
        if not filters:
            msg = "No filters available"
            self.logger.error(msg)
            return []

        fe = filterengine.Engine(
            filters=(x[1] for x in filters),
            logger=self.logger)

        results = fe.filter(query, results)
        if not ignore_state:
            results = fe.apply(self.get_filter('state'), None, None, results)

        return results

    def group(self, results):
        groups = {
            None: [],
            kit.Episode: [],
            kit.Movie: []
        }

        for res in results:
            e = res.entity
            if e is not None:
                e = e.__class__

            groups[e].append(res)

        in_order = (
            sorted(
                groups[None],
                key=lambda x: x.name) +
            sorted(
                groups[kit.Episode],
                key=lambda x: (
                    x.entity.series,
                    x.entity.modifier or '',
                    x.entity.season or -1,
                    x.entity.number or -1)) +
            sorted(
                groups[kit.Movie],
                key=lambda x: (
                    x.entity.title,
                    x.entity.modifier or ''))
        )

        groups = itertools.groupby(
            in_order,
            key=lambda x: x.entity if x.entity else None)

        ret = []
        for (leader, group) in groups:
            group = list(group)
            if leader:
                for source in group:
                    source.entity = leader

            ret.append((leader, group))

        return ret

    def select(select, options, query):
        return options[0]

    def download(self, source):
        self.db.save(source)
        self.downloads.add(source)

    @contextlib.contextmanager
    def get_async_http_client(self):
        yield ArroyoAsyncHTTPClient()


class ArroyoAsyncHTTPClient(httpclient.AsyncHTTPClient):
    def __init__(self, *args, logger=None, enable_cache=False,
                 cache_delta=-1, timeout=20, **kwargs):

        logger = logger or Null

        self._timeout = timeout

        if enable_cache:
            fetcher_cache = cache.Disk(
                basedir=utils.user_path(utils.UserPathType.CACHE, 'network',
                                        create=True, is_folder=True),
                delta=cache_delta)

            if logger:
                msg = "{clsname} using cachepath '{path}'"
                msg = msg.format(clsname=self.__class__.__name__,
                                 path=fetcher_cache.basedir)
                logger.debug(msg)
        else:
            fetcher_cache = None

        super().__init__(*args, **kwargs, cache=fetcher_cache)

    @asyncio.coroutine
    def fetch_full(self, *args, **kwargs):
        kwargs['timeout'] = self._timeout
        resp, content = yield from super().fetch_full(*args, **kwargs)
        return resp, content
