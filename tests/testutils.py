from arroyo import kit
from arroyo.helpers import (
    mediaparser
)


def mock_source(name, type=None, **kwargs):
    return kit.Source(name=name, provider='mock', uri='fake://' + name,
                      type=type)


def analyze(src):
    mp = mediaparser.MediaParser()
    entity, tags = mp.parse(src)
    src.entity = entity
    src.tags = {tag.key: tag for tag in tags}
    return src
