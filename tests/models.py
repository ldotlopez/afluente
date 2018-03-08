import unittest

from appkit.db import sqlalchemyutils as sautils
from arroyo import kit
from arroyo.helpers import database
import testutils
from sqlalchemy import inspect


def source(name):
    return testutils.analyze(testutils.mock_source(name))


class TestModels(unittest.TestCase):
    ENTITY_MODELS = (
        kit.Episode,
        kit.Movie
    )

    def setUp(self):
        self.sess = sautils.create_session('sqlite:///:memory:')
        self.db = database.Database(self.sess)

    def test_user_created_episode_empty_modifier(self):
        """
        Test Episode.modifier behaviour (from user, via __init__)
        """
        ep1 = kit.Episode(series='foo', season=1, number=1)
        self.assertTrue(ep1.id is None)
        self.assertEqual(ep1.modifier,  '')


    def test_db_retrieved_episode_empty_modifier(self):
        """
        Test Episode.modifier behaviour (from database)
        """
        ep1 = kit.Episode(series='foo', season=1, number=1)
        self.sess.add(ep1)
        self.sess.commit()

        ep1 = self.sess.query(kit.Episode).first()

        self.assertEqual(ep1.modifier,  '')

    def test_get_source(self):
        """
        Test get method.
        Insert some source into database and try to retrieve it using similar
        data
        """
        s1 = source('Vikings - 1x01.mkv')
        self.sess.add(s1)
        self.sess.commit()
        self.assertTrue(s1.id is not None)

        s1_ = source('Vikings - 1x01.mkv')
        self.assertTrue(s1_.id is None)

        self.assertTrue(s1 is self.db.get(s1_))

    def test_get_entity(self):
        ep1 = kit.Episode(series='foo', season=1, number=1)
        self.sess.add(ep1)
        self.sess.commit()

        ep1_ = self.db.get(kit.Episode(series='foo', season=1, number=1))

        self.assertTrue(ep1 is ep1_)

    def test_merge(self):
        """
        Preinsert two sources sharing the same entity
        Create a similar source and try to merge with one of the two preexistent
        """
        s1 = source('Foo - 1x01.TeamA.mkv')
        s2 = source('Foo - 1x01.TeamB.mkv')
        s2.entity = s1.entity  # Simulate application job
        self.sess.add_all([s1, s2])
        self.sess.commit()

        with self.db.transaction():
            s1_ = self.db.merge(s1)
            s2_ = self.db.merge(s2)

        self.assertTrue(s1_.id is not None)
        self.assertTrue(s1_.id is not None)
        self.assertTrue(s1_.entity is s2_.entity)
        self.assertTrue(s1_.entity.id is not None)

    def test_merge_with_preexistent(self):
        """
        Preinsert two sources sharing the same entity
        Create a similar source and try to merge with one of the two preexistent
        """
        s1 = source('Foo - 1x01.TeamA.mkv')
        s2 = source('Foo - 1x01.TeamB.mkv')
        s2.entity = s1.entity  # Simulate application job
        self.sess.add_all([s1, s2])
        self.sess.commit()

        with self.db.transaction():
            s1_ = source('Foo - 1x01.TeamA.mkv')
            s1_ = self.db.merge(s1_)

        self.assertTrue(s1 is s1_)

    def test_merge_with_preexistent_entity(self):
        s1 = source('Foo - 1x01.TeamA.mkv')
        s1.entity.test = 'A'
        self.sess.add(s1)
        self.sess.commit()

        with self.db.transaction():
            s1_ = source('Foo - 1x01.TeamB.mkv')
            s1_.entity.test = 'B'
            s1_ = self.db.merge(s1_)

        self.assertTrue(s1.entity is s1_.entity)


if __name__ == '__main__':
    unittest.main()