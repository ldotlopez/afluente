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
import re


import bs4
from appkit import application
from appkit.application import console
from appkit.blocks import extensionmanager
from arroyo.dbmodels import (
    Source,
    SourceTag,
    Episode,
    Movie
)

# Short-hands
Parameter = application.Parameter
Extension = application.Extension


class CommandExtension(Extension, console.ConsoleCommandExtension):
    """
    Extension for commands. Mixing with ConsoleCommandExtension
    """
    pass


class DownloaderExtension(Extension):
    """
    Extension for downloaders
    """
    pass


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
                pass

            try:
                ret += " E" + self.number.zfill(2)
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
        return self
