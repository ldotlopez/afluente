from appkit import application
from appkit.application import console
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
        except extensionmanager.PluginNotLoadedError as e:
            msg = "Can't load plugin «{plugin_name}»: {msg}"
            msg = msg.format(plugin_name=plugin_name, msg=str(e))
            self.logger.error(msg)

    def get_extension(self, extension_point, name, *args, **kwargs):
        return super().get_extension(extension_point, name, self,
                                     *args, **kwargs)
