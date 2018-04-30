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
