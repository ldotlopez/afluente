from arroyo import kit
from appkit.blocks import (
    quicklogging
)


class Arroyo(kit.ConsoleApplicationMixin, kit.Application):
    DEFAULT_PLUGINS = [
        'commands.settings'
    ]

    def __init__(self):
        super().__init__(name='arroyo')
        self.register_extension_class(ScanCommand)
        for plugin in self.DEFAULT_PLUGINS:
            self.load_plugin(plugin)

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


class ScanCommand(kit.ConsoleCommandExtension):
    __extension_name__ = 'scan'
    HELP = 'Scan providers'

    def main(self):
        print(repr(self.shell))
