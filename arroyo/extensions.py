# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
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


import appkit.application
import bs4


# Alias parameter
Parameter = appkit.application.Parameter


class Extension(appkit.application.Extension):
    """
    Our extensions class adds a built-in logger
    """
    def __init__(self, shell, *args, **kwargs):
        logger = kwargs.pop('logger')

        super().__init__(shell, *args, **kwargs)
        self.logger = logger

        # FIXME: This is a hack
        # Parent logger can change its level to a lower level in the future.
        # Since level doesnt propage to children (even with NOTSET level) we
        # get the future level from settings
        # NOTE: this is not dynamic.
        self.logger.setLevel(shell.settings.get(arroyo.SettingsKey.LOG_LEVEL))


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


class BS4ParserProviderExtensionMixin:
    def parse(self, buffer):
        return self.parse_soup(bs4.BeautifulSoup(buffer, "html.parser"))

    @abc.abstractmethod
    def parse_soup(self, soup):
        raise NotImplementedError()


class DownloaderExtension(Extension):
    """Extension point for downloaders"""

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


class CommandExtension(Extension, appkit.application.console.ConsoleCommandExtension):
    """
    Extension for commands. Mixing with ConsoleCommandExtension
    """
    pass
