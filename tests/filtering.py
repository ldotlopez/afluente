import unittest


from testutils import mock_source


from arroyo import kit
from arroyo.helpers import (
    filterengine,
    mediaparser
)


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
        filters = [TypeFilter(None)] + (filters or [])
        return filterengine.Engine(filters=filters)

    def test_get_for_handler(self):
        foo = FooFilter(None)
        fe = self.get_engine(filters=[foo])
        f = fe.get_for_handler('foo')

        self.assertEqual(foo, f)

    def test_get_for_multi_handler(self):
        bar = BarFilter(None)
        fe = self.get_engine(filters=[bar])
        f = fe.get_for_handler('x')

        self.assertEqual(bar, f)

    def test_get_missing_handler(self):
        fe = self.get_engine()
        with self.assertRaises(filterengine.MissingFilterError):
            fe.get_for_handler('missing')

    def test_get_for_query(self):
        foo = FooFilter(None)
        fe = self.get_engine(filters=[foo])

        query = kit.Query(foo=1)
        filters, missing = fe.get_for_query(query)
        filters = dict(filters)

        self.assertEqual(filters['foo'], foo)
        self.assertEqual(missing, [])

    def test_get_missing_query(self):
        foo = FooFilter(None)
        bar = BarFilter(None)
        query = kit.Query(x=1, missing=0)

        fe = self.get_engine(filters=[foo, bar])
        filters, missing = fe.get_for_query(query)
        filters = dict(filters)

        self.assertEqual(filters['x'], bar)
        self.assertEqual(missing, ['missing'])

    def test_basic_filtering(self):
        def analyze(src):
            mp = mediaparser.MediaParser()
            entity, tags = mp.parse(src)
            src.entity = entity
            src.tags = tags
            return src

        results = [
            analyze(mock_source('Series A - 1x01')),
            analyze(mock_source('Series B - 3x03'))
        ]
        query = kit.Query(type='x')

        fe = filterengine.Engine(filters=[TypeFilter(None)])
        import ipdb; ipdb.set_trace(); pass
        results = fe.filter(results, query)

        print(results)


if __name__ == '__main__':
    unittest.main()
