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


from arroyo import kit, helpers


class Arroyo(kit.Application):
    """
    Implement arroyo over customized kit.Application
    """

    DEFAULT_PLUGINS = [
        'commands.download',
        'commands.settings',

        'providers.eztv'
    ]

    DEFAULT_SETTINGS = {
        'log-level': 'INFO',
        'plugins.commands.settings.enabled': False
    }

    def __init__(self):
        super().__init__(
            name='arroyo',
            logger=quicklogging.QuickLogger(level=quicklogging.Level.WARNING))

        self.register_extension_point(kit.ProviderExtension)

        plugin_enabled_key_tmpl = 'plugins.{name}.enabled'

        for plugin in self.DEFAULT_PLUGINS:
            settings_key = plugin_enabled_key_tmpl.format(name=plugin)

            if self.settings.get(settings_key, True):
                self.load_plugin(plugin)

            else:
                msg = 'Plugin "{name}" disabled by config'
                msg = msg.format(name=plugin)
                self.logger.info(msg)

    def get_providers(self):
        return [(name, self.get_provider(name))
                for name in
                self.get_extension_names_for(kit.ProviderExtension)]

    def get_provider(self, name):
        default_settings_key_tmpl = 'plugins.providers.{name}.default-{key}'
        override_settings_key_tmpl = 'plugins.providers.{name}.force-{key}'

        # Build provider's defaults and overrides from settings
        fields = ['language', 'type']

        overrides = {}
        defaults = {}

        for field in fields:
            default_key = default_settings_key_tmpl.format(name=name,
                                                           key=field)
            override_key = default_settings_key_tmpl.format(name=name,
                                                            key=field)
            default_value = self.settings.get(default_key, None)
            override_value = self.settings.get(override_key, None)

            if default_value:
                default_value[name][field] = default_value

            if override_value:
                overrides[name][field] = override_value

        return self.get_extension(kit.ProviderExtension, name,
                                  defaults=defaults, overrides=overrides)

    def search(self, query):
        providers = self.get_providers()
        scanner = helpers.Scanner(logger=self.logger)
        results = scanner.scan(query, providers)
        print(repr(results))

    def main(self):
        print('arroyo is up and running')
