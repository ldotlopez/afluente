from . import kit
from appkit.blocks import (
    quicklogging
)


class Arroyo(kit.ConsoleApplicationMixin, kit.Application):
    DEFAULT_PLUGINS = []

    def __init__(self):
        super().__init__(name='arroyo')
        self.register_extension_class(ScanCommand)

    def consume_application_arguments(self, arguments):
        log_level = (
            quicklogging.Level.WARNING +
            arguments.verbose -
            arguments.quiet)
        self.logger.setLevel(log_level.value)
        delattr(arguments, 'quiet')
        delattr(arguments, 'verbose')

        plugins = self.DEFAULT_PLUGINS + arguments.plugins
        for plugin in plugins:
            self.load_plugin(plugin)
        delattr(arguments, 'plugins')

        delattr(arguments, 'config_files')

    def main(self):
        print('arroyo is up and running')


class ScanCommand(kit.ConsoleCommandExtension):
    __extension_name__ = 'scan'
    HELP = 'Scan providers'

    def main(self):
        print(repr(self.shell))
