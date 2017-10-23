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


import re


from appkit import application
from appkit.application import console
from appkit.blocks import extensionmanager


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
    pass


class ProviderExtension(Extension):
    """
    Extension for providers
    """
    pass


class Query:
    """
    Represents a user query.

    All init parameters are validated and turned into object attributes
    """
    _PATTERN = r'^[a-z]+$'

    def __init__(self, *args, **params):
        if args:
            if len(args) != 1:
                msg = "Keywords must be a single string"
                raise TypeError(msg)

            keywords = str(args[0])
            raise NotImplementedError("keywords='{}'".format(keywords))

        if not params:
            msg = "not enoght info for a Query"
            raise ValueError(msg)

        for (key, value) in params.items():
            key, value = self._validate(key, value)
            setattr(self, key, value)

        self._attrs = tuple(params.keys())

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

    def __contains__(self, attr):
        return attr in self._attrs

    def __iter__(self):
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
