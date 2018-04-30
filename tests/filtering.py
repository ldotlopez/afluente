import unittest


from testutils import source


from appkit import Null
from arroyo import kit
from arroyo.helpers import filterengine
from arroyo.plugins.filters.tags import TagFilters


class DumbFilterMixin(kit.FilterExtension):
    __extension_name__ = 'typefilter'

    def filter(self, key, value, item):
        return True


class TypeFilter(DumbFilterMixin, kit.FilterExtension):
    HANDLES = ('type',)


class FooFilter(DumbFilterMixin, kit.FilterExtension):
    HANDLES = ('foo',)


class BarFilter(DumbFilterMixin, kit.FilterExtension):
    HANDLES = ('x', 'y')


class AssertsMixin:
    pass


def get_filter(type):
    return type(Null, logger=Null)


class QueryTest(AssertsMixin, unittest.TestCase):
    def test_basic_query(self):
        q = kit.Query(name_glob='*foo*')
        self.assertEqual(q.type, 'source')
        self.assertEqual(q.name_glob, '*foo*')

    def test_forbiden_args(self):
        with self.assertRaises(ValueError):
            kit.Query(**{'00': 1})

        with self.assertRaises(ValueError):
            kit.Query(**{'a b': 1})

    def test_args_replacements(self):
        q = kit.Query(**{'name-glob': '*'})
        self.assertEqual(q.name_glob, '*')


class FilterEngineTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.available_filters = {}

    def get_engine(self, filters=None):
        filters = [get_filter(TypeFilter)] + (filters or [])
        return filterengine.Engine(filters=filters)

    def test_get_for_handler(self):
        foo = get_filter(FooFilter)
        fe = self.get_engine(filters=[foo])
        f = fe.get_for_handler('foo')

        self.assertEqual(foo, f)

    def test_get_for_multi_handler(self):
        bar = get_filter(BarFilter)
        fe = self.get_engine(filters=[bar])
        f = fe.get_for_handler('x')

        self.assertEqual(bar, f)

    def test_get_missing_handler(self):
        fe = self.get_engine()
        with self.assertRaises(filterengine.MissingFilterError):
            fe.get_for_handler('missing')

    def test_get_for_query(self):
        foo = get_filter(FooFilter)
        fe = self.get_engine(filters=[foo])

        query = kit.Query(foo=1)
        filters, missing = fe.get_for_query(query)
        filters = dict(filters)

        self.assertEqual(filters['foo'], foo)
        self.assertEqual(missing, [])

    def test_get_missing_query(self):
        foo = get_filter(FooFilter)
        bar = get_filter(BarFilter)
        query = kit.Query(x=1, missing=0)

        fe = self.get_engine(filters=[foo, bar])
        filters, missing = fe.get_for_query(query)
        filters = dict(filters)

        self.assertEqual(filters['x'], bar)
        self.assertEqual(missing, ['missing'])

    def test_basic_filtering(self):
        results = [
            source('Series A - 1x01'),
            source('Series B - 3x03')
        ]
        query = kit.Query(type='x')

        fe = filterengine.Engine(filters=[get_filter(TypeFilter)])

        results = fe.filter(results, query)
        raise NotImplementedError()


class TestQualityFilter(unittest.TestCase):
    def assertResults(self, filter_class, key, value, names, expected_indexes):
        srcs = [source(x) for x in names]

        f = filter_class(Null, logger=Null)
        res = f.apply(key, value, srcs)
        self.assertEqual(
            list(res),
            [x for (idx, x) in enumerate(srcs) if idx in expected_indexes])

    def test_480p(self):
        self.assertResults(
            TagFilters, 'quality', '480p',
            ['Greys.Anatomy.S14E11.HDTV.x264-KILLERS[rartv]',
             'Greys.Anatomy.S14E11.720p.x264-KILLERS[rartv]'],
            [0])

    def test_720p(self):
        self.assertResults(
            TagFilters, 'quality', '720p',
            ['Greys.Anatomy.S14E11.1080p.x264-KILLERS[rartv]',
             'Greys.Anatomy.S14E11.720p.x264-KILLERS[rartv]'],
            [1])

    def test_hdtv_format(self):
        self.assertResults(
            TagFilters, 'format', 'webrip',
            ['Counterpart.S01E07.WEBRip.x264-ION10 ',
             'The.Good.Fight.S01E10.1080p.WEB-DL.DD5.1.H264-ViSUM[rartv]'],
            [0])


if __name__ == '__main__':
    unittest.main()
