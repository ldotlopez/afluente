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


import re
import sys


from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    and_,
    # event,
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


class Variable(sautils.KeyValueItem, sautils.Base):
    __tablename__ = 'variable'
    __table_args__ = schema.UniqueConstraint('key'),


class Source(sautils.Base):
    __tablename__ = 'source'

    # Required
    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String, nullable=False)
    uri = Column(String, nullable=False, unique=True)
    provider = Column(String, nullable=False)

    # EntitySupport
    episode_id = Column(Integer,
                        ForeignKey('episode.id', ondelete="SET NULL"),
                        nullable=True)
    episode = orm.relationship('Episode',
                               uselist=False,
                               backref=orm.backref("sources",
                                                   cascade_backrefs=False,
                                                   lazy='select'))


    movie_id = Column(Integer,
                      ForeignKey('movie.id', ondelete="SET NULL"),
                      nullable=True)
    movie = orm.relationship('Movie',
                             uselist=False,
                             backref=orm.backref("sources",
                                                 cascade_backrefs=False,
                                                 lazy='select'))

    def __init__(self, name, uri, provider,
                 timestamp=None,
                 urn=None,
                 size=None,
                 seeds=None,
                 leechers=None,
                 type=None,
                 language=None,
                 tags=None):

        # Non database attributes
        self.urn = urn  # URN is still relevant?
        self.language = language
        self.leechers = leechers
        self.seeds = seeds
        self.size = size
        self.timestamp = timestamp or utils.now_timestamp()
        self.tags = tags or []
        self.type = type

        super().__init__(name=name, uri=uri, provider=provider)

    def __eq__(self, other):
        return _eq_from_attrs(self, other, ('uri',))

    def __lt__(self, other):
        return _lt_from_attrs(self, other, ('name',))

    def __repr__(self):
        return "<Source #{id} {fmt} object at 0x{oid:x}>".format(
            id=self.id or '??',
            oid=id(self),
            fmt=self.format())

    def __str__(self):
        return self.format()

    def __hash__(self):
        return hash(self.uri)

    @orm.validates('name', 'provider', 'urn', 'uri', 'language', 'type')
    def validate(self, key, value):
        """
        Wrapper around static method normalize
        """
        return self.normalize(key, value)

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

    @hybrid_property
    def entity(self):
        return _entity_getter(self)

    @entity.setter
    def entity(self, entity):
        _entity_setter(self, entity)

    @property
    def _discriminator(self):
        return self.urn or self.uri

    @property
    def age(self):
        return utils.now_timestamp() - self.timestamp

    @property
    def needs_postprocessing(self):
        return self.urn is None and self.uri is not None

    @property
    def ratio(self):
        seeds = self.seeds if self.seeds is not None else 0
        leechers = self.leechers if self.leechers is not None else 0

        if not self.seeds and not self.leechers:
            return None

        if seeds and leechers == 0:
            return float(sys.maxsize)

        if seeds == 0 and leechers:
            return 0.0

        return seeds / leechers

    @property
    def selected(self):
        return (
            self.entity and
            self.entity.selection and
            self.entity.selection.source == self)

    def asdict(self):
        return _asdict_from_attrs(
            self, (
                'age',
                'entity',
                'episode',
                'episode_id',
                'id',
                'language',
                'leechers',
                'movie',
                'movie_id',
                'name',
                'provider',
                'ratio',
                'seeds',
                'size',
                'tags',
                'timestamp',
                'type',
                'uri',
                'urn'))

    def format(self, fmt='{name}', extra_data={}):
        data = self.asdict()
        data['seeds'] = data.get('seeds', '-')
        data['leechers'] = data.get('leechers', '-')
        data['language'] = data.get('language', 'unknow')
        data.update(extra_data)

        return fmt.format(**data)


# @event.listens_for(Source.tags, 'dispose_collection')
# @event.listens_for(Source.tags, 'init_collection')
# @event.listens_for(Source.tags, 'remove')
# def _source_tags_modifier_cb(target, *args):
#     target.tags_map = {tag.key: tag.value for tag in target.tags}


# class SourceTag(sautils.KeyValueItem, sautils.Base):
#     __tablename__ = 'sourcetag'
#     __table_args__ = (
#         schema.UniqueConstraint('source_id', 'key'),
#     )

#     source_id = Column(Integer, ForeignKey('source.id', ondelete="cascade"))
#     source = orm.relationship("Source", back_populates="tags", uselist=False)


# class Selection(sautils.Base):
#     __tablename__ = 'selection'
#     __mapper_args__ = {
#         'polymorphic_on': 'type'
#     }

#     id = Column(Integer, primary_key=True)
#     type = Column(String(50))
#     source_id = Column(Integer,
#                        ForeignKey('source.id', ondelete="cascade"),
#                        nullable=False)
#     source = orm.relationship('Source')

#     @hybrid_property
#     def entity(self):
#         return _entity_getter(self)

#     @entity.setter
#     def entity(self, entity):
#         _entity_setter(self, entity)


# class EpisodeSelection(Selection):
#     __mapper_args__ = {
#         'polymorphic_identity': 'episode'
#     }

#     episode_id = Column(Integer,
#                         ForeignKey('episode.id', ondelete="CASCADE"),
#                         nullable=True)
#     episode = orm.relationship("Episode",
#                                backref=orm.backref("selection",
#                                                    cascade="all, delete",
#                                                    uselist=False))

#     def __repr__(self):
#         fmt = '<EpisodeSelection {id} episode:{episode} <-> source:{source}'
#         return fmt.format(
#             id=self.id,
#             episode=repr(self.episode),
#             source=repr(self.source))


# class MovieSelection(Selection):
#     __mapper_args__ = {
#         'polymorphic_identity': 'movie'
#     }

#     movie_id = Column(Integer,
#                       ForeignKey('movie.id', ondelete="CASCADE"),
#                       nullable=True)
#     movie = orm.relationship("Movie",
#                              backref=orm.backref("selection",
#                                                  cascade="all, delete",
#                                                  uselist=False))

#     def __repr__(self):
#         fmt = '<MovieSelection {id} movie:{movie} <-> source:{source}'
#         return fmt.format(
#             id=self.id,
#             movie=repr(self.movie),
#             source=repr(self.source))


class Episode(sautils.Base):
    __tablename__ = 'episode'
    __table_args__ = (
        schema.UniqueConstraint('series', 'modifier', 'season', 'number'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    series = Column(String, nullable=False)
    modifier = Column(String, nullable=False, default='')
    season = Column(Integer, nullable=False)
    number = Column(Integer, nullable=False)

    # SELECTION_MODEL = EpisodeSelection

    def __init__(self, *args, modifier='', **kwargs):
        attrs = (
            'series',
            'season',
            'number'
        )
        _init_check_required(kwargs, attrs)
        super().__init__(*args, modifier=modifier, **kwargs)

    def __eq__(self, other):
        attrs = (
            'series',
            'modifier',
            'season',
            'number'
        )
        return _eq_from_attrs(self, other, attrs)

    def __lt__(self, other):
        attrs = (
            'series',
            'modifier'
            'season',
            'number'
        )
        return _lt_from_attrs(self, other, attrs)

    def __repr__(self):
        return "<Episode #{id} {fmt} object at 0x{oid:x}>".format(
            id=self.id or '??',
            oid=id(self),
            fmt=self.format())

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.format()

    @orm.validates(
        'series',
        'modifier',
        'season',
        'number'
    )
    def validate(self, key, value):
        return self.normalize(key, value)

    @classmethod
    def normalize(cls, key, value):
        if key == 'series':
            value = value.lower()
            if not value:
                raise ValueError(value)

        elif key == 'modifier':
            value = str(value) if value is not None else ''

        elif key in ['season', 'number']:
            value = int(value)
            if value < 0:
                raise ValueError(value)

        else:
            raise NotImplementedError(key)

        return value

    # @property
    # def modifier(self):
    #     return self._modifier or None

    # @modifier.setter
    # def modifier(self, value):
        self._modifier = value if value is not None else ''

    # @hybrid_property
    # def modifier(self):
    #     return self._modifier or None

    # @modifier.expression
    # def modifier(self):
    #     return func.or_(self._modifier, None)

    # @modifier.setter
    # def modifier(self, value):
    #     self._modifier = value or ''

    def asdict(self):
        attrs = (
            'series',
            'modifier',
            'season',
            'number',
        )
        return _asdict_from_attrs(self, attrs)

    def format(self, fmt='{series_with_mod} s{season:02d} e{number:02d}',
               extra_data={}):
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


class Movie(sautils.Base):
    __tablename__ = 'movie'
    __table_args__ = (
        schema.UniqueConstraint('title', 'modifier'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    modifier = Column(String, nullable=False, default='')

    # SELECTION_MODEL = MovieSelection

    def __init__(self, *args, modifier='', **kwargs):
        attrs = (
            'title',
        )
        _init_check_required(kwargs, attrs)
        super().__init__(*args, modifier=modifier, **kwargs)

    def __eq__(self, other):
        attrs = (
            'title',
            'modifier'
        )
        return _eq_from_attrs(self, other, attrs)

    def __lt__(self, other):
        attrs = (
            'title',
            'modifier'
        )
        return _lt_from_attrs(self, other, attrs)

    def __repr__(self):
        return "<Movie #{id} {fmt} object at 0x{oid:x}>".format(
            id=self.id or '??',
            oid=id(self),
            fmt=self.format())

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return self.format()

    @orm.validates(
        'title',
        'modifier'
    )
    def validate(self, key, value):
        return self.normalize(key, value)

    @classmethod
    def normalize(cls, key, value):
        if key == 'title':
            value = value.lower()
            if not value:
                raise ValueError(value)

        elif key == 'modifier':
            value = str(value) if value else ''

        else:
            raise NotImplementedError(key)

        return value

    def asdict(self):
        attrs = (
            'title',
            'modifier'
        )
        return _asdict_from_attrs(self, attrs)

    def format(self, fmt='{title_with_mod}', extra_data={}):
        d = self.asdict()

        if self.modifier:
            title_with_mod = "{title} ({modifier})"
        else:
            title_with_mod = "{title}"

        d['title_with_mod'] = title_with_mod.format(**d)
        d.update(**extra_data)

        return fmt.format(**d)


def _init_check_required(kwargs, reqs):
    check = all([attr in kwargs for attr in reqs])

    if not check:
        err = ("Insufficient arguments. "
               "Required: {req}, got: {got}")
        err = err.format(req=', '.join(reqs),
                         got=', '.join(kwargs.keys()))
        raise TypeError(err)


def _eq_from_attrs(a, b, attrs):
    if not isinstance(b, a.__class__):
        raise TypeError(b.__class__)

    try:
        return all([
            getattr(a, attr) == getattr(b, attr)
            for attr in attrs
        ])
    except AttributeError as e:
        raise TypeError(b) from e


def _lt_from_attrs(a, b, attrs):
    for attr in attrs:
        if not hasattr(a, attr):
            raise TypeError(a)

        if not hasattr(b, attr):
            raise TypeError(a)

        ret = getattr(a, attr).__lt__(getattr(b, attr))
        if ret != 0:
            return ret

    return 0


def _asdict_from_attrs(x, attrs):
    return {attr: getattr(x, attr, None) for attr in attrs}


def _entity_getter(x):
    entity_attrs = (
        'episode',
        'movie'
    )

    for attr in entity_attrs:
        value = getattr(x, attr, None)
        if value:
            return value

    return None


def _entity_setter(x, entity):
    entity_map = {
        Episode: 'episode',
        Movie: 'movie'
    }

    # Check for unknown entity type
    if entity is not None and entity.__class__ not in entity_map:
        raise TypeError(entity)

    # Set all entity-attributes correctly
    for (model, attr) in entity_map.items():
        value = entity if isinstance(entity, model) else None
        setattr(x, attr, value)
