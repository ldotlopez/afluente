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


import abc
import asyncio
import contextlib
import itertools
import functools
import os
import re
from urllib import parse


import bs4
import appkit
import appkit.application
import appkit.application.console
import appkit.blocks.extensionmanager
import appkit.blocks.httpclient
import appkit.blocks.quicklogging
import appkit.blocks.store
import appkit.db.sqlalchemyutils
import appkit.utils
import yaml


import arroyo.extensions
import arroyo.helpers.database
import arroyo.helpers.database
import arroyo.helpers.downloads
import arroyo.helpers.filterengine
import arroyo.helpers.mediaparser
import arroyo.helpers.scanner
from arroyo.models import (
    Download,
    Episode,
    Movie,
    Source,
    Variable
)


class SettingsKey:
    DB_URI                   = 'db-uri'
    DOWNLOADER               = 'downloader'
    ENABLE_CACHE             = 'enable-cache'
    LOG_LEVEL                = 'log-level'
    QUERY_DEFAULTS           = 'selector.query-defaults'
    QUERY_TYPE_DEFAULTS_TMPL = 'selector.query-{type}-defaults'
    QUERIES                  = 'queries'
    QUERIES_NS               = 'queries.'
    PLUGINS                  = 'plugins'
    PLUGINS_NS               = 'plugins.'
    FILTERS_NS               = 'plugins.filters.'
    PROVIDERS_NS             = 'plugins.providers.'
    COMMANDS_NS              = 'plugins.commands.'


class CacheType:
    SCAN = 'scan'
    NETWORK = 'network'
    FILTER = 'filter'


class DownloadState:
    INITIALIZING = 1
    QUEUED = 2
    PAUSED = 3
    DOWNLOADING = 4
    SHARING = 5
    DONE = 6
    ARCHIVED = 7


DownloadStateSymbol = {
    # State.NONE: ' ',
    DownloadState.INITIALIZING: '⋯',
    DownloadState.QUEUED: '⋯',
    DownloadState.PAUSED: '‖',
    DownloadState.DOWNLOADING: '↓',
    DownloadState.SHARING: '⇅',
    DownloadState.DONE: '✓',
    DownloadState.ARCHIVED: '▣'
}


class _BaseApplication(appkit.application.console.ConsoleApplicationMixin,
                       appkit.application.Application):
    """
    Implement our own features over appkit Application and Console Application
    """
    COMMAND_EXTENSION_POINT = arroyo.extensions.CommandExtension

    def load_plugin(self, plugin_name, *args, **kwargs):
        """
        Override this method to allow debugging and catch exceptions
        """
        try:
            super().load_plugin(plugin_name, *args, **kwargs)
            msg = "Loaded plugin {name}"
            msg = msg.format(name=plugin_name)
            self.logger.debug(msg)
        except appkit.blocks.extensionmanager.PluginNotLoadedError as e:
            msg = "Can't load plugin «{plugin_name}»: {msg}"
            msg = msg.format(plugin_name=plugin_name, msg=str(e))
            self.logger.error(msg)

    def get_shell(self):
        """
        Implement shell
        """
        return self

    def setup_parser(self, parser):
        super().setup_parser(parser)
        parser.add_argument(
            '--disable-cache',
            action='store_true',
            help='Disable all caches'
        )

    def consume_application_parameters(self, parameters):
        enable_cache = not parameters.pop('disable_cache', False)
        self.settings.set(SettingsKey.ENABLE_CACHE, enable_cache)
        if enable_cache:
            self.caches[CacheType.SCAN] = ArroyoScanCache()

        super().consume_application_parameters(parameters)

    def main(self):
        print('arroyo is up and running')

    def get_extension(self, extension_point, name, *args, **kwargs):
        kwargs['logger'] = self.logger.getChild(name)
        return super().get_extension(extension_point, name, *args, **kwargs)
    #     # FIXME: This is a hack
    #     # Parent logger can change its level to a lower level in the future.
    #     # Since level doesnt propage to children (even with NOTSET level) we
    #     # get the future level from settings
    #     # NOTE: this is not dynamic.
    #     self.logger.setLevel(self.get_shell().settings.get(SettingsKey.LOG_LEVEL))
    #     try:
    #         return super().get_extension(extension_point, name, *args, **kwargs)
    #     except Exception as e:
    #         import ipdb; ipdb.set_trace(); pass


class Application(_BaseApplication):
    """
    Implement arroyo over customized Application
    """

    DEFAULT_PLUGINS = [
        'commands.download',
        # 'commands.settings',

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
        SettingsKey.LOG_LEVEL: 'INFO',
        SettingsKey.COMMANDS_NS + 'settings.enabled': False,
        SettingsKey.ENABLE_CACHE: True,
        SettingsKey.DOWNLOADER: 'mock',
        SettingsKey.DB_URI: (
            'sqlite:///' +
            appkit.utils.user_path(
                appkit.utils.UserPathType.DATA, 'arroyo.db', create=True))
    }

    DEFAULT_SETTINGS.update({
        SettingsKey.PLUGINS_NS + plugin + '.enabled': True
        for plugin in DEFAULT_PLUGINS
    })

    def __init__(self, settings=None):
        store = ArroyoStore()

        if settings is None:
            settings = self.DEFAULT_SETTINGS

        for (key, value) in settings.items():
            store.set(key, value)

        # if SettingsKey.PLUGINS not in settings:
        #     settings[SettingsKey.PLUGINS] = {}

        super().__init__(
            name='arroyo',
            logger=QuickLogger(level=appkit.blocks.quicklogging.Level.WARNING),
            settings=store,
        )

        # Open database connection
        db_uri = self.settings.get(SettingsKey.DB_URI)

        # Add check_same_thread=False to db_uri.
        # FIXME: This is a _hack_ required by the webui plugin.
        if '?' in db_uri:
            db_uri += '&check_same_thread=False'
        else:
            db_uri += '?check_same_thread=False'

        db_sess = appkit.db.sqlalchemyutils.create_session(db_uri)

        # Initialize app variables
        self.variables = appkit.db.sqlalchemyutils.KeyValueManager(Variable,
                                                                   db_sess)

        # Register extension points
        self.register_extension_point(arroyo.extensions.FilterExtension)
        self.register_extension_point(arroyo.extensions.ProviderExtension)
        self.register_extension_point(arroyo.extensions.DownloaderExtension)

        # Initialize database controller
        self.db = arroyo.helpers.database.Database(db_sess)

        # app.register_extension_class(DownloadSyncCronTask)
        # app.register_extension_class(DownloadQueriesCronTask)
        # app.signals.register('source-state-change')

        # Initialize app caches
        self.caches = {
            CacheType.SCAN: appkit.blocks.cache.NullCache()
        }

        plugin_categories = self.settings.children(SettingsKey.PLUGINS_NS[:-1])

        for category in plugin_categories:
            plugins = self.settings.children(SettingsKey.PLUGINS_NS + category)

            for plugin in plugins:
                key = '{plugins_ns}{category}.{plugin}.enabled'.format(
                    plugins_ns=SettingsKey.PLUGINS_NS,
                    category=category,
                    plugin=plugin)

                if self.settings.get(key, True):
                    self.load_plugin(category + '.' + plugin)

                else:
                    msg = 'Plugin "{name}" disabled by config'
                    msg = msg.format(name=plugin)
                    self.logger.info(msg)

    #
    # Controllers
    #
    @property
    def scanner(self):
        return arroyo.helpers.scanner.Scanner(
            logger=self.logger,
            providers=self.get_providers())

    @property
    def mediaparser(self):
        return arroyo.helpers.mediaparser.MediaParser(
            logger=self.logger.getChild('mediaparser'))

    @property
    def filters(self):
        filters = self.get_filters()
        if not filters:
            msg = "No filters available"
            self.logger.error(msg)

        return arroyo.helpers.filterengine.Engine(
            filters=(x[1] for x in filters),
            logger=self.logger)

    @property
    def downloads(self):
        downloader_name = self.settings.get(SettingsKey.DOWNLOADER)
        return arroyo.helpers.downloads.Downloads(
            plugin=self.get_downloader(downloader_name),
            db=self.db)

    #
    # Own methods
    #

    def get_providers(self):
        return [
            (name, self.get_provider(name)) for name in
            self.get_extension_names_for(arroyo.extensions.ProviderExtension)]

    def get_provider(self, name):
        default_settings_key_tmpl = (
            SettingsKey.PROVIDERS_NS + '{name}.default-{key}'
        )
        override_settings_key_tmpl = (
            SettingsKey.PROVIDERS_NS + '{name}.force-{key}'
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

        return self.get_extension(arroyo.extensions.ProviderExtension, name,
                                  defaults=defaults, overrides=overrides)

    def get_filters(self):
        return self.get_extensions_for(arroyo.extensions.FilterExtension)

    def get_filter(self, name):
        return self.get_extension(arroyo.extensions.FilterExtension, name)

    def get_downloader(self, name):
        return self.get_extension(arroyo.extensions.DownloaderExtension, name)

    def _get_base_query_params_from_type(self, type):
        if not isinstance(type, str):
            raise TypeError(type)
        if not type:
            raise ValueError(type)

        type_defaults_key = arroyo.SettingsKey.QUERY_TYPE_DEFAULTS_TMPL
        type_defaults_key = type_defaults_key.format(type=type)

        params = {}
        params.update(self.settings.get(arroyo.SettingsKey.QUERY_DEFAULTS, {}))
        params.update(self.settings.get(type_defaults_key, {}))

        return params

    def get_queries_from_config(self):
        query_defaults = self.settings.get(arroyo.SettingsKey.QUERY_DEFAULTS,
                                           {})
        query_type_defaults = {}

        config_queries = self.settings.get(arroyo.SettingsKey.QUERIES, {})

        ret = []

        for (name, query_params) in config_queries.items():
            query_type = query_params.get('type', 'source')

            params = self._get_base_query_params_from_type(query_type)
            params.update(query_params)

            query = Query(**parms)
            ret.append(query)

        return ret

    def get_query_from_params(self, **query_params):
        query_type = query_params.get('type', 'source')

        params = self._get_base_query_params_from_type(query_type)
        params.update(query_params)

        return Query(**params)

    def get_query_from_keywords(self, keywords, **params):
        query = Query(keywords, **params)
        query_params = query.asdict()
        query_type = query_params.get('type', 'source')

        params = self._get_base_query_params_from_type(query_type)
        params.update(query_params)

        return Query(**params)

    def search(self, query):
        def _post_process(items):
            for src, metadata in items:
                try:
                    entity, tags = self.mediaparser.parse(src,
                                                          metadata=metadata)

                except (arroyo.helpers.mediaparser.InvalidEntityTypeError,
                        arroyo.helpers.mediaparser.InvalidEntityArgumentsError
                        ) as e:
                    err = "Unable to parse '{name}': {e}"
                    err = err.format(name=src.name, e=e)
                    self.logger.error(err)
                    continue

                src.entity = entity
                src.tags = tags

                yield src

        try:
            results = self.caches[CacheType.SCAN].get(query)
            msg = "Scan data found in cache"
            self.logger.debug(msg)

        except KeyError:
            msg = "Scan data missing from cache"
            self.logger.debug(msg)
            results = None

            sources_and_metas = self.scanner.scan(query)
            results = list(_post_process(sources_and_metas))

            self.caches[CacheType.SCAN].set(query, results)

        return results

    def filter(self, results, query, ignore_state=False):
        results = self.filters.filter(query, results)
        if not ignore_state:
            results = self.filters.apply(self.get_filter('state'),
                                         None,
                                         None,
                                         results)

        return results

    def group(self, results):
        groups = {
            None: [],
            Episode: [],
            Movie: []
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
                groups[Episode],
                key=lambda x: (
                    x.entity.series,
                    x.entity.modifier or '',
                    x.entity.season or -1,
                    x.entity.number or -1)) +
            sorted(
                groups[Movie],
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
        source = self.db.merge(source)
        self.downloads.add(source)

    def get_downloads(self):
        return self.downloads.list()

    def cancel(self, id_):
        return self.downloads.cancel(id_)

    def archive(self, id_):
        return self.downloads.archive(id_)

    @contextlib.contextmanager
    def get_async_http_client(self):
        yield ArroyoAsyncHTTPClient()


class ArroyoStore(appkit.blocks.store.Store):
    """
    YAML compatible store
    """

    def load(self, stream):
        data = yaml.load(stream.read())
        data = appkit.blocks.store.flatten_dict(data)

        for (k, v) in data.items():
            self.set(k, v)


class ArroyoAsyncHTTPClient(appkit.blocks.httpclient.AsyncHTTPClient):
    def __init__(self, *args, logger=None, enable_cache=False,
                 cache_delta=-1, timeout=20, **kwargs):

        logger = logger or appkit.Null

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


class ArroyoScanCache(appkit.blocks.cache.DiskCache):
    def __init__(self, *args, **kwargs):
        basedir = (
            kwargs.pop('basedir', None) or
            appkit.utils.user_path(appkit.utils.UserPathType.CACHE,
                                   name='scan')
        )
        os.makedirs(basedir, exist_ok=True)
        delta = kwargs.pop('delta', None) or 60*60
        super().__init__(*args, basedir=basedir, delta=delta, **kwargs)

    def encode_key(self, query):
        data = query.asdict()
        data = sorted(data.items())
        key = parse.urlencode(data)
        return self.basedir / key


class QuickLogger(appkit.blocks.quicklogging.QuickLogger):
    """
    Override QuickLogger to use our Formatter
    """
    def __init__(self, *args, **kwargs):
        kwargs['formatter_class'] = LoggerFormatter
        super().__init__(*args, **kwargs)


class LoggerFormatter(appkit.blocks.quicklogging.DefaultFormatter):
    """
    This formater uses three characters codes for level names
    """
    _LEVEL_NAMES = {
        'CRITICAL': '!!!',
        'ERROR': 'ERR',
        'WARNING': 'WRN',
        'INFO': 'NFO',
        'DEBUG': 'DBG'
    }

    def format(self, record):
        record.levelname = self._LEVEL_NAMES[record.levelname]
        return super().format(record)


class Query:
    """
    Represents a user query.

    All init parameters are validated and turned into object attributes
    """
    _PATTERN = r'^[a-z]+$'

    def __init__(self, *args, **params):
        if args:
            # Convert args[0] in keyword
            if len(args) != 1:
                msg = "Keywords must be a single string"
                raise TypeError(msg)

            if not isinstance(args[0], str):
                raise TypeError(args[0])

            keywords = args[0]
            if params.get('type') == 'source':
                # type='source' is a special case
                params['name_glob'] = '*' + keywords.replace(' ', '*') + '*'

            else:
                # In any other cases we relay on mediaparser to build the query
                parser = arroyo.helpers.mediaparser.MediaParser()
                type, params, _, _ = parser.parse_name(args[0], hints=params)
                params['type'] = type

        if 'type' not in params:
            params['type'] = 'source'

        _attrs = []
        for (key, value) in params.items():
            key, value = self._validate(key, value)
            _attrs.append(key)
            setattr(self, key, value)

        self._attrs = tuple(_attrs)

    @classmethod
    def _validate(cls, attr, value):
        def _is_basic_type(x):
            return isinstance(x, (int, float, bool, str))

        attr = str(attr)
        attr = attr.replace('-', '_')

        parts = attr.split('_')

        if not all([re.match(cls._PATTERN, attr) for attr in parts]):
            raise ValueError(attr)

        return attr, value

    def __str__(self):
        def _get_base_string(attr='name'):
            try:
                return getattr(self, attr).strip()
            except AttributeError:
                pass

            try:
                return getattr(self, attr + '_glob').replace('*', ' ').strip()
            except AttributeError:
                pass

            raise arroyo.exc.QueryConversionError(self.asdict())

        def _source_base_string():
            return _get_base_string('name')

        def _episode_base_string():
            ret = _get_base_string('series')
            if not ret:
                return _source_base_string()

            try:
                ret += " ({})".format(self.series_year)
            except AttributeError:
                pass

            try:
                ret += " S" + str(self.season).zfill(2)
            except AttributeError:
                return ret

            try:
                ret += "E" + str(self.number).zfill(2)
            except AttributeError:
                pass

            return ret

        def _movie_base_string():
            ret = _get_base_string('title')
            try:
                ret += " ({})".format(self.movie_year)
            except AttributeError:
                pass

            return ret

        handlers = {
            'episode': _episode_base_string,
            'movie': _movie_base_string,
            'source': _source_base_string,
        }

        try:
            return handlers[self.type]()

        except KeyError as e:
            err = "base_string for {type} not implmented"
            err = err.format(type=self.type)
            raise NotImplementedError(err)

    def asdict(self):
        return {
            x: getattr(self, x) for x in self
        }

    def __contains__(self, attr):
        return attr in self._attrs

    def __iter__(self):
        if hasattr(self, '_attrs'):
            yield from self._attrs

    def __setattr__(self, attr, value):
        if hasattr(self, '_attrs'):
            raise TypeError()

        return super().__setattr__(attr, value)

    def __repr__(self):
        items = ", ".join(
            ["{}='{}'".format(attr, getattr(self, attr)) for attr in self]
        )
        return '<{clsname}({items}) object at 0x{id:x}>'.format(
            clsname='arroyo.query.Query',
            items=items,
            id=id(self)
        )


def unroll(fn):
    @functools.wraps(fn)
    def _wrapper(*args, **kwargs):
        ret = []
        for x in fn(*args, **kwargs):
            ret.append(x)

        return ret

    return _wrapper
