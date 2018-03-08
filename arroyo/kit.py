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
import os
import re
from urllib import parse


import bs4
from appkit import (
    application,
    utils
)
from appkit.application import console
from appkit.blocks import (
    cache,
    extensionmanager,
    quicklogging
)
from arroyo.models import (
    Episode,
    Movie,
    Source,
    Variable
)

# Short-hands
Parameter = application.Parameter
# Extension = application.Extension


class QuickLogger(quicklogging.QuickLogger):
    """
    Override QuickLogger to use our Formatter
    """
    def __init__(self, *args, **kwargs):
        kwargs['formatter_class'] = LoggerFormatter
        super().__init__(*args, **kwargs)


class LoggerFormatter(quicklogging.DefaultFormatter):
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


class Extension(application.Extension):
    """
    Our extensions class adds a built-in logger
    """
    def __init__(self, shell, *args, **kwargs):
        logger = kwargs.pop('logger')
        super().__init__(shell, *args, **kwargs)
        self.logger = logger.getChild(self.__extension_name__)

        # FIXME: This is a hack
        # Parent logger can change its level to a lower level in the future.
        # Since level doesnt propage to children (even with NOTSET level) we
        # get the future level from settings
        # NOTE: this is not dynamic.
        self.logger.setLevel(shell.settings.get(SettingsKeys.LOG_LEVEL))


class FilterExtension(Extension):
    """
    Extension for filters
    """
    HANDLES = ()

    def can_handle(self, key):
        return key in self.HANDLES

    @abc.abstractmethod
    def filter(self, key, value, item):
        raise NotImplementedError()

    def apply(self, key, value, iterable):
        return filter(
            lambda item: self.filter(key, value, item),
            iterable)


class SorterExtension(Extension):
    """
    Extension for sorters
    """
    pass


class ProviderExtension(Extension):
    """
    Extension for providers
    """
    def __init__(self, *args, defaults=None, overrides=None, **kwargs):
        defaults = defaults or {}
        overrides = overrides or {}

        for d in defaults, overrides:
            if not isinstance(d, dict):
                raise TypeError(d)

            check = all([
                isinstance(k, str) and k and
                isinstance(v, str) and v
                for (k, v) in d.items()
            ])
            if not check:
                raise ValueError(d)

        self.defaults = defaults
        self.overrides = overrides

        super().__init__(*args, **kwargs)

    def compatible_uri(self, uri):
        attr_name = 'URI_PATTERNS'
        attr = getattr(self, attr_name, None)

        if not (isinstance(attr, (list, tuple)) and len(attr)):
            msg = "Class {cls} must override {attr} attribute"
            msg = msg.format(self=self.__class__.__name__, attr=attr_name)
            raise NotImplementedError(msg)

        RegexType = type(re.compile(r''))
        for pattern in attr:
            if isinstance(pattern, RegexType):
                if pattern.search(uri):
                    return True
            else:
                if re.search(pattern, uri):
                    return True

        return False

    @abc.abstractmethod
    def paginate(self, uri):
        yield uri

    @abc.abstractmethod
    def get_query_uri(self, query):
        return None

    @abc.abstractmethod
    def fetch(self, uri):
        with self.shell.get_async_http_client() as client:
            return (yield from client.fetch(uri))

    @abc.abstractmethod
    def parse(self, buffer):
        raise NotImplementedError()

    def __unicode__(self):
        return "Provider({name})".format(
            name=self.__extension_name__)

    __str__ = __unicode__


class BS4ParserProviderExtensionMixin:
    def parse(self, buffer):
        return self.parse_soup(bs4.BeautifulSoup(buffer, "html.parser"))

    @abc.abstractmethod
    def parse_soup(self, soup):
        raise NotImplementedError()


class IncompatibleQueryError(Exception):
    """
    Raised by Providers if cant generate an URI for a query
    """
    pass


class DownloaderExtension(Extension):
    """
    Extension for downloaders
    """

    def add(self, source):
        """Adds source to download.

        Must return True on successful or raise an Exception on failure
        """
        raise NotImplementedError()

    def cancel(self, foreign_id):
        """Cancels foreign ID and deletes any possible file

        Must return True on successful or raise an Exception on failure
        """
        raise NotImplementedError()

    def archive(self, foreign_id):
        """Archives source to download, just remove it from downloader keeping
        any possible files

        Must return True on successful or raise an Exception on failure
        """
        raise NotImplementedError()

    def list(self):
        raise NotImplementedError()

    def get_state(self, foreign_id):
        raise NotImplementedError()

    def get_info(self, foreign_id):
        raise NotImplementedError()

    def id_for_source(self, source):
        """For tests. Returns an acceptable (even simulated or random) local ID
        for this source"""
        raise NotImplementedError()


class CommandExtension(Extension, console.ConsoleCommandExtension):
    """
    Extension for commands. Mixing with ConsoleCommandExtension
    """
    pass


class Query:
    """
    Represents a user query.

    All init parameters are validated and turned into object attributes
    """
    _PATTERN = r'^[a-z]+$'

    def __init__(self, *args, type='source', **params):
        if args:
            if len(args) != 1:
                msg = "Keywords must be a single string"
                raise TypeError(msg)

            keywords = str(args[0])
            raise NotImplementedError("keywords='{}'".format(keywords))

        if 'type' not in params:
            params['type'] = type

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
                return getattr(self, attr + '-glob').replace('*', ' ').strip()
            except AttributeError:
                pass

            raise QueryConversionError(self.asdict())

        def _source_base_string():
            return _get_base_string('name')

        def _episode_base_string():
            ret = _get_base_string('series')
            if not ret:
                return _source_base_string()

            try:
                ret += " {}".format(self.series_year)
            except AttributeError:
                pass

            try:
                ret += " S" + self.season.zfill(2)
            except AttributeError:
                return ret

            try:
                ret += "E" + self.number.zfill(2)
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


class QueryConversionError(Exception):
    pass


class ConsoleApplicationMixin(console.ConsoleApplicationMixin):
    """
    Reconfigure ConsoleApplicationMixin to use our CommandExtension
    """
    COMMAND_EXTENSION_POINT = CommandExtension


class Application(ConsoleApplicationMixin, application.Application):
    """
    Implement application model.
    Mix necessary mixins and override some methods
    """
    def load_plugin(self, plugin_name, *args, **kwargs):
        """
        Override this method to allow debugging and catch exceptions
        """
        try:
            super().load_plugin(plugin_name, *args, **kwargs)
            msg = "Loaded plugin {name}"
            msg = msg.format(name=plugin_name)
            self.logger.debug(msg)
        except extensionmanager.PluginNotLoadedError as e:
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
        self.settings.set(SettingsKeys.ENABLE_CACHE, enable_cache)
        if enable_cache:
            self.caches[Caches.SCAN] = ArroyoScanCache()

        super().consume_application_parameters(parameters)

    def main(self):
        print('arroyo is up and running')

    def get_extension(self, extension_point, name, *args, **kwargs):
        kwargs['logger'] = self.logger
        return super().get_extension(extension_point, name, *args, **kwargs)


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


class Caches:
    SCAN = 'scan'
    NETWORK = 'network'
    FILTER = 'filter'


class SettingsKeys:
    DB_URI = 'db-uri'
    DOWNLOADER = 'downloader'
    ENABLE_CACHE = 'enable-cache'
    LOG_LEVEL = 'log-level'
    COMMANDS_NS = 'plugins.commands.'
    FILTERS_NS = 'plugins.filters.'
    PLUGINS_NS = 'plugins.'
    PROVIDERS_NS = 'plugins.providers.'
