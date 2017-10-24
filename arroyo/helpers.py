import collections

import appkit


_Context = collections.namedtuple('_Context', [
    'name', 'provider', 'uri'
    ])


class Scanner:
    def __init__(self, logger=appkit.Null):
        self.logger = logger

    def scan(self, query, providers=None, iterations=None):
        if providers is None:
            msg = "No providers supplied"
            self.logger.error(msg)
            return []

        msg = "Searching for {query}…"
        msg = msg.format(query=repr(query))
        self.logger.info(msg)

        for (name, provider) in providers:
            msg = "…scanning '{name}'"
            msg = msg.format(name=name)
            self.logger.info(msg)
