import hashlib
from urllib import parse

import arroyo
from arroyo import kit
from arroyo.helpers import (
    mediaparser
)


def mock_source(name, type=None, **kwargs):
    if 'provider' not in kwargs:
        kwargs['provider'] = 'mock'

    if 'uri' not in kwargs:
        kwargs['uri'] = 'magnet:?xt={urn}&dn={dn}'.format(
            urn='urn:btih:' + hashlib.sha1(name.encode('utf-8')).hexdigest(),
            dn=parse.quote_plus(name))

    return kit.Source(name=name, type=type, **kwargs)


def analyze(src):
    mp = mediaparser.MediaParser()
    entity, tags = mp.parse(src)
    src.entity = entity
    src.tags = tags
    return src


def source(*args, **kwargs):
    return analyze(mock_source(*args, **kwargs))


class TestApp(arroyo.Arroyo):
    def __init__(self, settings=None):
        if settings is None:
            settings = {}

        settings[kit.SettingsKeys.DB_URI] = 'sqlite:///:memory:'
        super().__init__(settings)
