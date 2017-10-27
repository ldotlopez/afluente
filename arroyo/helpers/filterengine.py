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


import functools


from appkit import Null


class MissingFilterError(Exception):
    pass


class ConflictingFilterError(Exception):
    pass


class Engine:
    __slots__ = (
        'filters',
        'logger',
        'registry')

    def __init__(self, filters=None, logger=None):
        if filters is None:
            raise TypeError(filters)

        self.registry = Registry()
        self.logger = logger or Null

        for (name, f) in filters:
            try:
                self.registry.add(f)
            except ConflictingFilterError as e:
                msg = "Filter {f} has conflicting handles: {collisions}"
                msg = msg.format(f=name, collisions=', '.join(e.args[1]))
                self.logger.warning(msg)

    def filter(self, results, query):
        filters, missing = self.matching_filters(query)

        for key in missing:
            msg = "Missing filter for key '{key}'"
            msg = msg.format(key=key)
            self.logger.warning(msg)

        results = list(results)
        for (name, fn) in filters:
            prev = len(results)
            results = list(fn(results))
            curr = len(results)
            msg = "Applied {name} over {prev} items: {curr} results"
            msg = msg.format(name=name, prev=prev, curr=curr)
            self.logger.debug(msg)

        if not isinstance(results, list):
            results = list(results)

        return results

    def matching_filters(self, query):
        matches = []
        missing = []

        for (key, value) in query.asdict().items():
            try:
                ext = self.registry.get(key)
                fn = functools.partial(ext.apply, key, value)
                matches.append((key, fn))
            except MissingFilterError:
                missing.append(key)

        return matches, missing


class Registry:
    def __init__(self):
        self._reg = {}

    def add(self, f):
        s1 = set(f.HANDLES)
        s2 = set(self._reg.keys())
        collisions = tuple(s2.intersection(s1))

        if collisions:
            raise ConflictingFilterError(f, collisions)

        self._reg.update({
            handle: f for handle in f.HANDLES
        })

    def get(self, key):
        try:
            return self._reg[key]
        except KeyError as e:
            raise MissingFilterError(key) from e
