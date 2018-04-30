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


import contextlib


from appkit.db import sqlalchemyutils as sautils


import arroyo


class NoResultsFoundError(Exception):
    pass


class MultipleResultsFoundError(Exception):
    pass


class Database:
    def __init__(self, session):
        self.session = session

    @contextlib.contextmanager
    def transaction(self):
        yield self
        self.session.commit()

    def add(self, obj):
        self.session.add(obj)

    def add_all(self, objs):
        self.session.add_all([objs])

    def delete(self, obj):
        self.session.delete(obj)

    def get(self, obj):
        # Keep attrs in this method in sync with
        # models.py Unique fields
        attrs = None

        if isinstance(obj, arroyo.Movie):
            attrs = ('title', 'modifier')
        elif isinstance(obj, arroyo.Episode):
            attrs = ('series', 'modifier', 'season', 'number')
        elif isinstance(obj, arroyo.Source):
            attrs = ('uri',)
        else:
            raise NotImplemented(obj)

        params = {attr: getattr(obj, attr) for attr in attrs}
        db_obj = sautils.get(self.session, obj.__class__, **params)

        if db_obj is None:
            raise NoResultsFoundError(obj)

        if isinstance(db_obj, list):
            raise MultipleResultsFoundError(obj)

        return db_obj

    def merge(self, obj):
        try:
            return self.get(obj)
        except NoResultsFoundError:
            pass

        # Deep-first merging
        if isinstance(obj, arroyo.Source) and obj.entity:
            obj.entity = self.merge(obj.entity)

        self.session.add(obj)
        return obj

    def merge_all(self, objs):
        return [self.merge(obj) for obj in objs]

    def list_downloads(self):
        return self.session.query(arroyo.Download).all()
