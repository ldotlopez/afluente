from arroyo import kit


class SettingsSet(kit.ConsoleCommandExtension):
    PARAMETERS = []

    def main(self):
        print("settings set")


class SettingsGet(kit.ConsoleCommandExtension):
    PARAMETERS = []

    def main(self):
        print("settings get")


class SettingsConsoleCommand(kit.ConsoleCommandExtension):
    __extension_name__ = 'settings'
    CHILDREN = [
        ('set', SettingsSet),
        ('get', SettingsGet)
    ]


__arroyo_extensions__ = [
    SettingsConsoleCommand
]
