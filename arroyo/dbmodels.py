# -*- coding: utf-8 -*-

# Copyright (C) 2017 Luis López <luis@cuarentaydos.com>
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


import abc
import functools
import re
import sys


from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    and_,
    func,
    orm,
    schema
)
from sqlalchemy.ext.hybrid import hybrid_property
from appkit.db import sqlalchemyutils as sautils
from appkit import utils


sautils.Base.metadata.naming_convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Source:
#   is EntityMixin

# Episode, Movie:
#    needs WhateverSelection
#
# EpisodeSelection, MovieSelection:
#   is Selection
# Selection:
#   is EntityPropertyMixin

@functools.lru_cache(maxsize=8)
def _ensure_model_class(x):

    try:
        if issubclass(x, sautils.Base):
            return x
    except TypeError:
        pass

    if '.' in x:
        mod = sys.modules[x]
        x = x.split('.')[-1]

    else:
        mod = sys.modules[__name__]

    cls = getattr(mod, x)
    issubclass(cls, sautils.Base)

    return cls


Variable = sautils.keyvaluemodel('Variable', sautils.Base, dict({
    '__doc__': "Define variables.",
    '__table_args__': (schema.UniqueConstraint('key'),)
    }))


class EntityPropertyMixin:
    """Adds support for `entity` property
    Useful for Source and Selection

    Classes using this mixin should define the class attribute ENTITY_MAP:
    ENTITY_MAP = {
        # Related class (as string or as class): attribute
        'Episode': 'episode'
    }
    """

    ENTITY_MAP = {}

    @hybrid_property
    def entity(self):
        entity_attrs = self.ENTITY_MAP.values()

        for attr in entity_attrs:
            value = getattr(self, attr, None)
            if value:
                return value

        return None

    @entity.setter
    def entity(self, entity):
        m = {_ensure_model_class(k): v
             for (k, v) in self.ENTITY_MAP.items()}

        # Check for unknown entity type
        if entity is not None and entity.__class__ not in m:
            raise TypeError(entity)

        # Set all entity-attributes correctly
        for (model, attr) in m.items():
            value = entity if isinstance(entity, model) else None
            setattr(self, attr, value)

    @abc.abstractmethod
    def __eq__(self, other):
        raise NotImplementedError()


class Source(EntityPropertyMixin, sautils.Base):
    class Formats:
        DEFAULT = '{name}'
        DETAIL = (
            "{name} "
            "(lang: {language}, size: {size}, ratio: {seeds}/{leechers})"
        )

    __tablename__ = 'source'

    ENTITY_MAP = {  # EntityPropertyMixin
        'Episode': 'episode',
        'Movie': 'movie'
    }

    # Required
    id = Column(Integer, primary_key=True)
    provider = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created = Column(Integer, nullable=False)
    last_seen = Column(Integer, nullable=False)

    # Real ID
    urn = Column(String, nullable=True, unique=True,)
    uri = Column(String, nullable=False, unique=True)

    # Other data
    size = Column(Integer, nullable=True)
    seeds = Column(Integer, nullable=True)
    leechers = Column(Integer, nullable=True)

    type = Column(String, nullable=True)
    language = Column(String, nullable=True)

    # EntitySupport
    episode_id = Column(Integer,
                        ForeignKey('episode.id', ondelete="SET NULL"),
                        nullable=True)
    episode = orm.relationship('Episode',
                               uselist=False,
                               backref=orm.backref("sources", lazy='dynamic'))

    movie_id = Column(Integer,
                      ForeignKey('movie.id', ondelete="SET NULL"),
                      nullable=True)
    movie = orm.relationship('Movie',
                             uselist=False,
                             backref=orm.backref("sources", lazy='dynamic'))

    # FIXME: change lazy to 'subquery' for simplicty or use dict-like
    # collections
    tags = orm.relationship("SourceTag",
                            uselist=True,
                            back_populates="source",
                            lazy='dynamic',
                            cascade="all, delete, delete-orphan")

    def __init__(self, **kwargs):
        for x in ['provider', 'name', 'uri']:
            if x not in kwargs:
                msg = '{name} is required'
                msg = msg.format(name=x)
                raise TypeError(msg)

        now = utils.now_timestamp()
        if 'last_seen' not in kwargs:
            kwargs['last_seen'] = now

        if 'created' not in kwargs:
            kwargs['created'] = now

        super().__init__(**kwargs)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError(self.__class__, other.__class__)

        return self.id.__eq__(other.id)

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError()

        return self.id.__lt__(other.id)

    def __iter__(self):
        yield from [
            'age', 'created', 'entity', 'episode', 'episode_id', 'id',
            'language', 'last_seen', 'leechers', 'movie', 'movie_id', 'name',
            'provider', 'seeds', 'share_ratio', 'size', 'tags', 'type', 'type',
            'uri', 'urn'
        ]

    def __str__(self):
        return self.format(self.Formats.DEFAULT)

    def __repr__(self):
        msg = "<Source (id={sid}, name='{name}') object at 0x{id:x}>"
        return msg.format(name=self.name, sid=self.id or '-', id=id(self))

    @property
    def tag_dict(self):
        return {x.key: x.value for x in self.tags.all()}

    @hybrid_property
    def _discriminator(self):
        return self.urn or self.uri

    @_discriminator.expression
    def _discriminator(self):
        return func.coalesce(self.urn, self.uri)

    @hybrid_property
    def age(self):
        return utils.now_timestamp() - self.created

    @hybrid_property
    def needs_postprocessing(self):
        return self.urn is None and self.uri is not None

    @needs_postprocessing.expression
    def needs_postprocessing(self):
        return and_(self.urn.is_(None), ~self.uri.is_(None))

    @hybrid_property
    def share_ratio(self):
        seeds = self.seeds if self.seeds is not None else 0
        leechers = self.leechers if self.leechers is not None else 0

        if not self.seeds and not self.leechers:
            return None

        if seeds and leechers == 0:
            return float(sys.maxsize)

        if seeds == 0 and leechers:
            return 0.0

        return seeds / leechers

    @hybrid_property
    def selected(self):
        return (
            self.entity and
            self.entity.selection and
            self.entity.selection.source == self)

    @staticmethod
    def normalize(key, value):
        def _normalize():
            nonlocal key
            nonlocal value

            # Those keys must be a non empty strings
            if key in ['name', 'provider', 'urn', 'uri']:
                if value == '':
                    raise ValueError()

                return str(value)

            # Those keys must be an integer (not None)
            elif key in ['created', 'last_seen']:
                return int(value)

            # Those keys must be an integer or None
            elif key in ['size', 'seeds', 'leechers']:
                if value is None:
                    return None

                return int(key)

            # language must be in form of xxx-xx or None
            elif key == 'language':
                if value is None:
                    return None

                value = str(value)

                if not re.match(r'^...(\-..)?$', value):
                    raise ValueError()

                return value

            # type is limited to some strings or None
            elif key == 'type':
                if value is None:
                    return None

                value = str(value)

                if value in (
                        'application',
                        'book',
                        'episode',
                        'game',
                        'movie',
                        'music',
                        'other',
                        'xxx'):
                    return value

                raise ValueError()

            else:
                raise KeyError()

        # Wrap the whole process for easy exception handling
        try:
            return _normalize()

        except TypeError as e:
            msg = 'invalid type for {key}: {type}'
            msg = msg.format(key=key, type=type(value))
            raise TypeError(msg) from e

        except ValueError as e:
            msg = 'invalid value for {key}: {value}'
            msg = msg.format(key=key, value=repr(value))
            raise ValueError(msg) from e

    @orm.validates('name', 'provider', 'urn', 'uri', 'language', 'type')
    def validate(self, key, value):
        """
        Wrapper around static method normalize
        """
        return self.normalize(key, value)

    def asdict(self):
        ret = {
            attr: getattr(self, attr)
            for attr in self
            if attr != 'tags'
        }
        ret['tags'] = self.tag_dict

        return ret

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        data = self.asdict()
        data['seeds'] = data.get('seeds') or '-'
        data['leechers'] = data.get('leechers') or '-'
        data['language'] = data.get('language') or 'unknow'

        data.update(extra_data)

        return fmt.format(**data)


SourceTag = sautils.keyvaluemodel(
    'SourceTag',
    sautils.Base,
    dict({
        '__doc__': "Define custom data attached to a source.",
        '__tablename__': 'sourcetag',
        '__table_args__': (schema.UniqueConstraint('source_id', 'key'),),
        'source_id': Column(Integer,
                            ForeignKey('source.id', ondelete="cascade")),
        'source': orm.relationship("Source", back_populates="tags", uselist=False)
    }))


class Selection(EntityPropertyMixin, sautils.Base):
    __tablename__ = 'selection'
    ENTITY_MAP = {
        'Episode': 'episode',
        'Movie': 'movie'
    }

    id = Column(Integer, primary_key=True)
    type = Column(String(50))

    source_id = Column(Integer,
                       ForeignKey('source.id', ondelete="cascade"),
                       nullable=False)
    source = orm.relationship('Source')

    __mapper_args__ = {
        'polymorphic_on': 'type'
    }


class EpisodeSelection(Selection):
    episode_id = Column(Integer,
                        ForeignKey('episode.id', ondelete="CASCADE"),
                        nullable=True)
    episode = orm.relationship("Episode",
                               backref=orm.backref("selection",
                                                   cascade="all, delete",
                                                   uselist=False))

    __mapper_args__ = {
        'polymorphic_identity': 'episode'
    }

    def __repr__(self):
        fmt = '<EpisodeSelection {id} episode:{episode} <-> source:{source}'
        return fmt.format(
            id=self.id,
            episode=repr(self.episode),
            source=repr(self.source))


class MovieSelection(Selection):
    movie_id = Column(Integer,
                      ForeignKey('movie.id', ondelete="CASCADE"),
                      nullable=True)
    movie = orm.relationship("Movie",
                             backref=orm.backref("selection",
                                                 cascade="all, delete",
                                                 uselist=False))

    __mapper_args__ = {
        'polymorphic_identity': 'movie'
    }

    def __repr__(self):
        fmt = '<MovieSelection {id} movie:{movie} <-> source:{source}'
        return fmt.format(
            id=self.id,
            movie=repr(self.movie),
            source=repr(self.source))


class Episode(sautils.Base):
    __tablename__ = 'episode'
    __table_args__ = (
        schema.UniqueConstraint('series', 'modifier', 'season', 'number'),
    )

    id = Column(Integer, primary_key=True)

    series = Column(String, nullable=False)
    modifier = Column(String, nullable=False, default='')

    season = Column(Integer, nullable=False)
    number = Column(Integer, nullable=False)

    SELECTION_MODEL = EpisodeSelection

    class Formats:
        DEFAULT = '{series_with_mod} s{season:02d} e{number:02d}'

    def __init__(self, *args, **kwargs):
        req = ['series', 'season', 'number']
        check = all([
            attr in kwargs
            for attr in req
        ])
        if not check:
            err = (
                "Insufficient arguments. "
                "Required: {req}, got: {got}"
            )
            err = err.format(
                req=', '.join(req),
                got=', '.join(kwargs.keys())
            )
            raise TypeError(err)

        super().__init__(*args, **kwargs)

    @classmethod
    def normalize(cls, key, value):
        if key == 'series':
            value = value.lower()
            if not value:
                raise ValueError(value)

        elif key == 'modifier':
            value = str(value) if value else ''

        elif key in ['season', 'number', 'modifier']:
            value = int(value)
            if value < 0:
                raise ValueError(value)

        else:
            msg = "{key!r}={value!r}"
            msg = msg.format(key=key, value=value)
            ValueError(msg)

        return value

    @orm.validates('series', 'modifier', 'season', 'number')
    def validate(self, key, value):
        return self.normalize(key, value)

    def asdict(self):
        return {
            attr: getattr(self, attr)
            for attr in self
        }

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        d = self.asdict()

        if self.modifier:
            series_with_mod = "{series} ({modifier})"
        else:
            series_with_mod = "{series}"

        d['series_with_mod'] = series_with_mod.format(**d)
        d.update(**extra_data)

        try:
            return fmt.format(**d)
        except TypeError:
            pass

    def __eq__(self, other):
        return all([
            getattr(self, attr) == getattr(other, attr)
            for attr in ['series', 'modifier', 'season', 'number']
        ])

    def __iter__(self):
        yield from ['id', 'series', 'modifier', 'season', 'number']

    def __repr__(self):
        return "<Episode #{id} {fmt}>".format(
            id=self.id or '??',
            fmt=self.format())

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.format()


class Movie(sautils.Base):
    __tablename__ = 'movie'
    __table_args__ = (
        schema.UniqueConstraint('title', 'modifier'),
    )

    id = Column(Integer, primary_key=True)

    title = Column(String, nullable=False)
    modifier = Column(String, nullable=False, default='')

    SELECTION_MODEL = MovieSelection

    class Formats:
        DEFAULT = '{title_with_mod}'

    @classmethod
    def normalize(cls, key, value):
        if key == 'title':
            value = value.lower()
            if not value:
                raise ValueError(value)

        elif key == 'modifier':
            value = str(value) if value else ''

        else:
            msg = "{key!r}={value!r}"
            msg = msg.format(key=key, value=value)
            ValueError(msg)

        return value

    @orm.validates('title', 'modifier')
    def validate(self, key, value):
        return self.normalize(key, value)

    def asdict(self):
        return {
            attr: getattr(self, attr)
            for attr in self
        }

    def format(self, fmt=Formats.DEFAULT, extra_data={}):
        d = self.asdict()

        if self.modifier:
            title_with_mod = "{title} ({modifier})"
        else:
            title_with_mod = "{title}"

        d['title_with_mod'] = title_with_mod.format(**d)
        d.update(**extra_data)

        return fmt.format(**d)

    def __iter__(self):
        yield from ['id', 'title', 'modifier']

    def __repr__(self):
        return "<Movie #{id} {fmt}>".format(
            id=self.id or '??',
            fmt=self.format())

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.format()

    def __eq__(self, other):
        return (
            self.title == other.title and
            self.modifier == other.modifier
        )