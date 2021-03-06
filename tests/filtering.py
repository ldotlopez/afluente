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


from testutils import (
    analyze,
    mock_source
)

from appkit import Null

from arroyo import Query
from arroyo.exc import MissingFilterError
from arroyo.extensions import FilterExtension
from arroyo.helpers.filterengine import Engine
from arroyo.plugins.filters.source import SourceFieldsFilter
from arroyo.plugins.filters.episode import EpisodeFieldsFilter
from arroyo.plugins.filters.movie import MovieFieldsFilter
from arroyo.plugins.sorters.basic import BasicSorter


# class DumbFilterMixin(FilterExtension):
#     __extension_name__ = 'typefilter'

#     def filter(self, key, value, item):
#         return True


# class TypeFilter(DumbFilterMixin, FilterExtension):
#     HANDLES = ('type',)


# class FooFilter(DumbFilterMixin, FilterExtension):
#     HANDLES = ('foo',)


# class BarFilter(DumbFilterMixin, FilterExtension):
#     HANDLES = ('x', 'y')


# class AssertsMixin:
#     pass


# def get_filter(type):
#     return type(Null, logger=Null)


def s(*args, **kwargs):
    return analyze(mock_source(*args, **kwargs))


class QueryTest(unittest.TestCase):
    def test_basic_query(self):
        q = Query(name_glob='*foo*')
        self.assertEqual(q.type, 'source')
        self.assertEqual(q.name_glob, '*foo*')

    def test_forbiden_args(self):
        with self.assertRaises(ValueError):
            Query(**{'00': 1})

        with self.assertRaises(ValueError):
            Query(**{'a b': 1})

    def test_args_replacements(self):
        q = Query(**{'name-glob': '*'})
        self.assertEqual(q.name_glob, '*')


class EngineUtilsMixin:
    def get_engine(self, filters=None, sorter=None):
        if filters is None:
            filters = [SourceFieldsFilter]
        if sorter is None:
            sorter = BasicSorter

        # FIXME: shell can be null
        filters = [filter(shell=Null, logger=None) for filter in filters]
        sorter = sorter(shell=Null, logger=None)

        return Engine(filters=filters, sorter=sorter)


class TestEngine(EngineUtilsMixin, unittest.TestCase):
    def test_basic_filter(self):
        sources = [s(x) for x in [
            'foo.txt',
            'bar.txt']
        ]
        engine = self.get_engine([SourceFieldsFilter])

        res = engine.filter_by(sources, name_glob='*foo*')
        self.assertEqual(res[0], sources[0])


class TestSelection(EngineUtilsMixin, unittest.TestCase):
    def assertSelection(self, expected, sources):
        sorted = self.get_engine().sorted(sources, None)
        self.assertEqual(expected, sorted[0])

    def test_proper(self):
        sources = [s(x) for x in [
            'the.handmaids.tale.s01e01.TeamA.mkv',
            'the.handmaids.tale.s01e01.TeamA.PRoPeRmkv',
        ]]
        self.assertSelection(sources[1], sources)


# class FilterEngineTest_(unittest.TestCase):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.available_filters = {}

#     def get_engine(self, filters=None):
#         filters = [get_filter(TypeFilter)] + (filters or [])
#         return Engine(filters=filters)

#     def test_get_for_handler(self):
#         foo = get_filter(FooFilter)
#         fe = self.get_engine(filters=[foo])
#         f = fe.get_for_handler('foo')

#         self.assertEqual(foo, f)

#     def test_get_for_multi_handler(self):
#         bar = get_filter(BarFilter)
#         fe = self.get_engine(filters=[bar])
#         f = fe.get_for_handler('x')

#         self.assertEqual(bar, f)

#     def test_get_missing_handler(self):
#         fe = self.get_engine()
#         with self.assertRaises(MissingFilterError):
#             fe.get_for_handler('missing')

#     def test_get_for_query(self):
#         foo = get_filter(FooFilter)
#         fe = self.get_engine(filters=[foo])

#         query = Query(foo=1)
#         filters, missing = fe.get_for_query(query)
#         filters = dict(filters)

#         self.assertEqual(filters['foo'], foo)
#         self.assertEqual(missing, [])

#     def test_get_missing_query(self):
#         foo = get_filter(FooFilter)
#         bar = get_filter(BarFilter)
#         query = Query(x=1, missing=0)

#         fe = self.get_engine(filters=[foo, bar])
#         filters, missing = fe.get_for_query(query)
#         filters = dict(filters)

#         self.assertEqual(filters['x'], bar)
#         self.assertEqual(missing, ['missing'])

#     def test_basic_filtering(self):
#         results = [
#             source('Series A - 1x01'),
#             source('Series B - 3x03')
#         ]
#         query = Query(type='episode', series='series a')

#         fe = Engine(filters=[get_filter(TypeFilter)])
#         results = fe.filter(query, results)
#         # raise NotImplementedError()


# class TestQualityFilter(unittest.TestCase):
#     def assertResults(self, filter_class, key, value, names, expected_indexes):
#         srcs = [source(x) for x in names]

#         f = filter_class(Null, logger=Null)
#         res = f.apply(key, value, srcs)
#         self.assertEqual(
#             list(res),
#             [x for (idx, x) in enumerate(srcs) if idx in expected_indexes])

#     def test_480p(self):
#         self.assertResults(
#             TagFilters, 'quality', '480p',
#             ['Greys.Anatomy.S14E11.HDTV.x264-KILLERS[rartv]',
#              'Greys.Anatomy.S14E11.720p.x264-KILLERS[rartv]'],
#             [0])

#     def test_720p(self):
#         self.assertResults(
#             TagFilters, 'quality', '720p',
#             ['Greys.Anatomy.S14E11.1080p.x264-KILLERS[rartv]',
#              'Greys.Anatomy.S14E11.720p.x264-KILLERS[rartv]'],
#             [1])

#     def test_hdtv_format(self):
#         self.assertResults(
#             TagFilters, 'format', 'webrip',
#             ['Counterpart.S01E07.WEBRip.x264-ION10 ',
#              'The.Good.Fight.S01E10.1080p.WEB-DL.DD5.1.H264-ViSUM[rartv]'],
#             [0])


if __name__ == '__main__':
    unittest.main()
