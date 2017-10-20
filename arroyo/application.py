from appkit import application
from appkit.application import console
# from appkit.blocks import quicklogging


class Arroyo(console.ConsoleAppMixin, application.App):
    def __init__(self):
        super().__init__(name='arroyo')

    def main(self, verbose=0, quiet=0, config_files=None, plugins=None):
        if config_files is None:
            config_files = []

        if plugins is None:
            plugins = []

        # log_level = quicklogging.Level.WARNING + verbose - quiet
        # self.logger.setLevel(log_level.value)

        print('arroyo is up and running')
