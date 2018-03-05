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
import os
from urllib import parse


from appkit import (
    Null,
    utils
)
from appkit.blocks import (
    cache,
    httpclient,
    quicklogging
)


from arroyo import kit
from arroyo.helpers import (
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

        'filters.episode',
        'filters.movie',
        'filters.source',
        'filters.tags',

        'providers.epublibre',
        'providers.eztv',
        'providers.torrentapi'
    ]

    DEFAULT_SETTINGS = {
        kit.SettingsKeys.LOG_LEVEL: 'INFO',
        kit.SettingsKeys.COMMANDS_NS + 'settings.enabled': False,
        kit.SettingsKeys.ENABLE_CACHE: True
    }

    def __init__(self):
        super().__init__(
            name='arroyo',
            logger=quicklogging.QuickLogger(level=quicklogging.Level.WARNING))

        self.register_extension_point(kit.FilterExtension)
        self.register_extension_point(kit.ProviderExtension)

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

        self.caches = {
            Caches.SCAN: cache.NullCache()
        }

    def setup_parser(self, parser):
        super().setup_parser(parser)
        parser.add_argument(
            '--disable-cache',
            action='store_true',
            help='Disable all caches'
        )

    def consume_application_parameters(self, parameters):
        enable_cache = not parameters.pop('disable_cache', False)
        self.settings.set(kit.SettingsKeys.ENABLE_CACHE, enable_cache)
        if enable_cache:
            self.caches[Caches.SCAN] = ArroyoScanCache()

        super().consume_application_parameters(parameters)

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
        return self.get_extensions(kit.FilterExtension, name)

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
            results = self.caches[Caches.SCAN].get(query)
            msg = "Scan data found in cache"
            self.logger.debug(msg)

        except KeyError:
            msg = "Scan data missing from cache"
            self.logger.debug(msg)

            s = scanner.Scanner(logger=self.logger,
                                providers=self.get_providers())
            sources_and_metas = s.scan(query)
            results = list(_post_process(sources_and_metas))

            self.caches[Caches.SCAN].set(query, results)

        # Processed results can't be cached due a error
        # in serialization of tags
        return results

    def filter(self, results, query):
        filters = self.get_filters()
        if not filters:
            msg = "No filters available"
            self.logger.error(msg)
            return []

        fe = filterengine.Engine(
            filters=(x[1] for x in filters),
            logger=self.logger)

        res = fe.filter(results, query)
        return res

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

        return itertools.groupby(
            in_order,
            key=lambda x: x.entity if x.entity else None)

    @contextlib.contextmanager
    def get_async_http_client(self):
        yield ArroyoAsyncHTTPClient()

    def main(self):
        print('arroyo is up and running')


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


class Caches:
    SCAN = 'scan'
    NETWORK = 'network'
    FILTER = 'filter'


class ArroyoScanCache(cache.DiskCache):
    def __init__(self, *args, **kwargs):
        basedir = (
            kwargs.pop('basedir', None) or
            utils.user_path(utils.UserPathType.CACHE, name='scan')
        )
        os.makedirs(basedir, exist_ok=True)
        delta = kwargs.pop('delta', None) or 60*60
        super().__init__(*args, basedir=basedir, delta=delta, **kwargs)

    def encode_key(self, query):
        data = query.asdict()
        data = sorted(data.items())
        key = parse.urlencode(data)
        return self.basedir / key
