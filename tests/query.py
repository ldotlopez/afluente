import unittest


from arroyo import Query


import testutils


class QueryTest(unittest.TestCase):
    def assertQuery(self, expected, *args, **kwargs):
        query = Query(*args, **kwargs)
        query_data = {
            k: v for (k, v) in query.asdict().items()
            if k in expected
        }

        self.assertEqual(expected, query_data)

    def test_source_query(self):
        self.assertQuery(
            {'name_glob': '*foo*', 'type': 'source'},
            name_glob='*foo*'
        )

    def test_parse_episode(self):
        self.assertQuery(
            {'type': 'episode',
             'series': 'westworld',
             'season': 1,
             'number': 1},
            'westworld s01e01')

    def test_keywords_query(self):
        query = Query('foo bar')
        self.assertEqual(query.type, 'movie')
        self.assertEqual(query.title, 'foo bar')

        query = Query('foo bar', type='source')
        self.assertEqual(query.type, 'source')
        self.assertEqual(query.name_glob, '*foo*bar*')


class QueryStrTest(unittest.TestCase):
    def test_source(self):
        self.assertEqual(
            str(Query(name='foo', type='source')),
            'foo')

    def test_movie(self):
        self.assertEqual(
            str(Query(type='movie', title='foo')),
            'foo')

    def test_movie_with_year(self):
        self.assertEqual(
            str(Query(type='movie', title='foo', movie_year=2018)),
            'foo (2018)')

    def test_episode(self):
        self.assertEqual(
            str(Query(type='episode', series='foo')),
            'foo')

    def test_episode_with_year(self):
        self.assertEqual(
            str(Query(type='episode', series='foo', series_year=2018)),
            'foo (2018)')

    def test_episode_with_season(self):
        self.assertEqual(
            str(Query(type='episode', series='foo', season=5)),
            'foo S05')

    def test_episode_without_season_with_number(self):
        self.assertEqual(
            str(Query(type='episode', series='foo', number=5)),
            'foo')

    def test_episode_full(self):
        self.assertEqual(
            str(Query(type='episode', series='foo', season=3, number=5)),
            'foo S03E05')

    def test_episode_full_with_year(self):
        self.assertEqual(
            str(Query(type='episode', series='foo', series_year=2018, season=3, number=5)),
            'foo (2018) S03E05')


class TestApplicationQueries(unittest.TestCase):
    SETTINGS = {
        'selector.query-defaults.age-min': '30m',
        'selector.query-episode-defaults.quality': '720p',
    }

    def setUp(self):
        super().setUp()
        self.app = testutils.TestApp(settings=self.SETTINGS)

    def test_three_layer_query(self):
        params = {
            'type': 'episode',
            'series': 'lost'
        }
        query = self.app.get_query_from_params(**params)
        self.assertEqual(
            query.asdict(),
            {'age_min': '30m', 'quality': '720p',
             'type': 'episode', 'series': 'lost'})

    def test_two_layer_query(self):
        params = {
            'type': 'movie',
            'title': 'star wars'
        }
        query = self.app.get_query_from_params(**params)
        self.assertEqual(
            query.asdict(),
            {'age_min': '30m',
             'type': 'movie', 'title': 'star wars'})

    def test_one_layer_query(self):
        params = {
            'name_glob': '*foo*'
        }
        query = self.app.get_query_from_params(**params)
        self.assertEqual(
            query.asdict(),
            {'age_min': '30m',
             'type': 'source', 'name_glob': '*foo*'})

    def test_keywords_query(self):
        query = self.app.get_query_from_keywords('foo bar')
        self.assertEqual(
            query.asdict(),
            {'age_min': '30m',
             'type': 'movie', 'title': 'foo bar'})

        query = self.app.get_query_from_keywords('foo bar', type='source')
        self.assertEqual(
            query.asdict(),
            {'age_min': '30m',
             'type': 'source', 'name_glob': '*foo*bar*'})



if __name__ == '__main__':
    unittest.main()
