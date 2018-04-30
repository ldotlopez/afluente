import unittest
from arroyo import kit
from arroyo.helpers import mediaparser


class MockSource(kit.Source):
    MP = mediaparser.MediaParser()

    def __init__(self, name, type=None, **kwargs):
        super().__init__(name=name, provider='mock', uri='fake://' + name, type=type)
        if type:
            entity, tags = self.MP.parse(self)

        self.entity = entity
        self.tags = tags


class GroupTest(unittest.TestCase):
    def setUp(self):
        self.app = None
        self.mp = mediaparser.MediaParser()

    def test_group(self):
        ss = [
            MockSource('The.Walking.Dead.S03E16.REPACK.HDTV.x264-EVOLVE', type='episode'),
            MockSource('The.Walking.Dead.S03E16.720p.HDTV.x264-2HD', type='episode')
        ]
        self.assertFalse(ss[0].entity is ss[1].entity)
        self.assertEqual(ss[0].entity, ss[1].entity)


if __name__ == '__main__':
    unittest.main()
