# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
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


import unittest


from testutils import mock_source


from arroyo import kit
from arroyo.helpers import mediaparser

__doc__ = """
The parsing stage takes the data scrapper by the providers and converts it to
models (Source+Entity+Tags usually).

Tests in this module are designed to ensure that mediaparser is tough enough
to handle all cases and sharp edges
"""


class AssertsMixin:
    def setUp(self):
        super().setUp()
        self.mp = mediaparser.MediaParser()

    def assertEntity(self, entity, entity_class, data):
        self.assertTrue(isinstance(entity, entity_class))
        _data = {attr: getattr(entity, attr) for attr in data}
        self.assertEqual(_data, data)

    def parse(self, name, **kwargs):
        source = mock_source(name, **kwargs)
        entity, tags = self.mp.parse(source)
        tags = {tag.key: tag.value for tag in tags}
        return source, entity, tags


class ParsingTest(AssertsMixin, unittest.TestCase):
    def test_episode_parse(self):
        s, e, t = self.parse('Lost s01e01.mkv')
        self.assertEntity(e,
                          kit.Episode,
                          dict(series='lost', season=1, number=1))

    def test_movie_parse(self):
        s, e, t = self.parse('Dark.City.1999.mkv')
        self.assertEntity(e,
                          kit.Movie,
                          dict(title='dark city', modifier='1999'))

    def test_language_found(self):
        # Language code embeded in name
        s, e, t = self.parse(
            'Dark.S01E05.SWE.DUBBED.1080p.WEBRip.x264-SERIOUSLY[rartv]')
        self.assertEqual(t['media.language'], 'swe-sv')

    def test_parse_und_language(self):
        # This name causes guessit to detect language='undef'
        # Make sure it doesn't crack
        s, e, t = self.parse(
            'Dark.S01E05.DUBBED.1080p.WEBRip.x264-SERIOUSLY[rartv]')
        self.assertEqual(s.language, None)

    def test_detect_release_and_distributor(self):
        # Check release and distributor
        s, e, t = self.parse(
            'Dark.S01E05.DUBBED.1080p.WEBRip.x264-SERIOUSLY[rartv]')
        self.assertEqual(t['release.distributors'], ['rartv'])
        self.assertEqual(t['release.group'], 'SERIOUSLY')

    def test_parse_movie_as_episode(self):
        # Sometimes providers (or uploaders) doen't classify the sources
        # correctly
        with self.assertRaises(TypeError):
            s, e, m = self.parse(
                'Al-Jazeera.Canadas.Dark.Secret.720p.HDTV.x264.AAC.mkv[eztv].mkv[eztv]',
                type='episode')

    def test_parse_similar_names_match_entities(self):
        # Names refering to the same entity return diferent instances but they
        # should respect equality
        _, e1, _ = self.parse(
            'Dark.S01E05.DUBBED.1080p.WEBRip.x264-SERIOUSLY[rartv]')
        _, e2, _ = self.parse(
            'Dark.S01E05.HDTV.KILLERS.PROPER[rartv]')

        self.assertEqual(e1, e2)


class TestGuessitParse(unittest.TestCase):
    def test_empty_entity_type(self):
        m = mediaparser.MediaParser()
        with self.assertRaises(mediaparser.InvalidEntityError):
            m._guessit_transform_data({})

        with self.assertRaises(mediaparser.InvalidEntityError):
            m._guessit_transform_data(dict(type='foo'))


if __name__ == '__main__':
    unittest.main()
