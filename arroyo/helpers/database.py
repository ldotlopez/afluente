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


from arroyo import kit


class MultipleResultsFoundError(Exception):
    pass


class Database:
    def __init__(self, session):
        self.session = session

    def save(self, *objs):
        err = "Smart merger must be implemented"
        raise NotImplementedError(err)
        for o in objs:
            self.session.add(o)

        self.session.commit()

    def get_object(self, o):
        # Keep attrs in this method in sync with
        # models.py Unique fields

        attrs = None

        if isinstance(o, kit.Movie):
            attrs = ('title', 'modifier')
        elif isinstance(o, kit.Episode):
            attrs = ('series', 'modifier', 'season', 'number')
        elif isinstance(o, kit.Source):
            attrs = ('uri',)
        else:
            raise NotImplemented(o)

        params = {attr: getattr(o, attr) for attr in attrs}

        x = sautils.get(self.session, o.__class__, **params)
        if isinstance(x, list):
            raise MultipleResultsFoundError(o)

        return x
