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


from arroyo import (
    Episode,
    Movie,
    Source
)
from arroyo.helpers.mediaparser import (
    MediaParser,
    InvalidEntityTypeError,
    InvalidEntityArgumentsError
)


from testutils import mock_source


__doc__ = """
The parsing stage takes the data scrapper by the providers and converts it to
models (Source+Entity+Tags usually).

Tests in this module are designed to ensure that mediaparser is tough enough
to handle all cases and sharp edges
"""


class NameParsingTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.mp = MediaParser()

    def assertParse(self, name, type, params):
        t, p, m, o = self.mp.parse_name(name)
        p = {k: p[k] for k in params}

        self.assertEqual(t, type)
        self.assertEqual(p, params)

    def test_episode_parse(self):
        self.assertParse(
            'Lost s01e01',
            'episode',
            dict(series='Lost', season=1, number=1))

    def test_with_hints(self):
        t, p, m, o = self.mp.parse_name('foo bar')
        self.assertEqual(t, 'movie')
        self.assertEqual(p, dict(title='foo bar'))

        t, p, m, o = self.mp.parse_name('foo bar', hints=dict(type='source'))
        self.assertTrue(t is None)
        self.assertEqual(p, dict())


class SourceParsingTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.mp = MediaParser()

    def assertEntity(self, entity, entity_class, data):
        self.assertTrue(isinstance(entity, entity_class))
        _data = {attr: getattr(entity, attr) for attr in data}
        self.assertEqual(_data, data)

    def parse(self, name, **kwargs):
        source = mock_source(name, **kwargs)
        entity, tags = self.mp.parse(source)
        return source, entity, tags

    def test_episode_parse(self):
        s, e, t = self.parse('Lost s01e01.mkv')
        self.assertEntity(e,
                          Episode,
                          dict(series='lost', season=1, number=1))

    def test_movie_parse(self):
        s, e, t = self.parse('Dark.City.1999.mkv')
        self.assertEntity(e,
                          Movie,
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
        with self.assertRaises(InvalidEntityArgumentsError):
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


if __name__ == '__main__':
    unittest.main()
