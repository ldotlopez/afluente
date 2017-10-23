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


from appkit import application
from appkit.application import console, Parameter
from appkit.blocks import extensionmanager


class ConsoleCommandExtension(console.ConsoleCommandExtension):
    def __init__(self, shell, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.shell = shell


class ConsoleApplicationMixin(console.ConsoleApplicationMixin):
    COMMAND_EXTENSION_POINT = ConsoleCommandExtension


class Application(application.Application):
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

    def get_extension(self, extension_point, name, *args, **kwargs):
        return super().get_extension(extension_point, name, self,
                                     *args, **kwargs)
