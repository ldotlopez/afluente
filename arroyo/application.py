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


from appkit.blocks import quicklogging


from arroyo import kit


class Arroyo(kit.Application):
    """
    Implement arroyo over customized kit.Application
    """

    DEFAULT_PLUGINS = [
        'commands.download',
        'commands.settings',

        'providers.eztv'
    ]

    def __init__(self):
        super().__init__(name='arroyo')
        for plugin in self.DEFAULT_PLUGINS:
            self.load_plugin(plugin)

    def search(self, query):
        print(repr(query))

    def consume_application_parameters(self, parameters):
        quiet = parameters.pop('quiet')
        verbose = parameters.pop('verbose')
        log_level = quicklogging.Level.WARNING + verbose - quiet
        self.logger.setLevel(log_level.value)

        plugins = parameters.pop('plugins')
        for plugin in plugins:
            self.load_plugin(plugin)

        config_files = parameters.pop('config_files')
        if config_files:
            msg = "Configuration files ignored: {files}"
            msg = msg.format(files=', '.join(config_files))
            self.logger.warning(msg)

    def main(self):
        print('arroyo is up and running')

    def get_shell(self):
        return self
