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


import collections
import functools


from appkit import Null


import arroyo


class MissingFilterError(Exception):
    pass


class ConflictingFilterError(Exception):
    def __init__(self, collisions, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collisions = collisions


class Engine:
    __slots__ = (
        'logger',
        'registry'
    )

    def __init__(self, filters=None, logger=None):
        self.registry = {}
        self.logger = logger or Null

        for filter in filters or []:
            self.register(filter)

    def register(self, filter):
        s1 = set(filter.HANDLES)
        s2 = set(self.registry.keys())
        collisions = tuple(s2.intersection(s1))

        if collisions:
            raise ConflictingFilterError(collisions)

        self.registry.update({
            handle: filter for handle in filter.HANDLES
        })

        # msg = "Filter {f} has conflicting handles: {collisions}"
        # msg = msg.format(f=name, collisions=', '.join(e.args[1]))
        # self.logger.warning(msg)
        # raise

    def apply(self, filter, handler, value, results):
        if isinstance(results, list):
            prev = len(results)
        else:
            prev = '?? (iterable)'

        results = filter.apply(handler, value, results)

        if isinstance(results, list):
            curr = len(results)
        else:
            curr = '?? (iterable)'

        msg = "Applied {name} over {prev} items: {curr} results"
        msg = msg.format(name=handler, prev=prev, curr=curr)
        self.logger.debug(msg)

        return results

    def filter(self, query, results):
        if not isinstance(query, arroyo.Query):
            raise TypeError(query)
        if not isinstance(results, collections.Iterable):
            raise TypeError(results)

        filters, missing = self.get_for_query(query)

        if not filters:
            err = "No matching filters"
            self.logger.error(err)
            return []

        for key in missing:
            msg = "Missing filter for key '{key}'"
            msg = msg.format(key=key)
            self.logger.warning(msg)

        for (handler, filter) in filters:
            results = self.apply(filter,
                                 handler, getattr(query, handler),
                                 results)
            # fn = functools.partial(filter.apply,
            #                        handler,
            #                        getattr(query, handler))

            # prev = len(results)
            # results = list(fn(results))
            # curr = len(results)

            # msg = "Applied {name} over {prev} items: {curr} results"
            # msg = msg.format(name=handler, prev=prev, curr=curr)
            # self.logger.debug(msg)

        if not isinstance(results, list):
            results = list(results)

        return results

    def get_for_handler(self, handler):
        try:
            return self.registry[handler]
        except KeyError as e:
            raise MissingFilterError() from e

    def get_for_query(self, query):
        matches = []
        missing = []

        for (key, value) in query.asdict().items():
            try:
                filter = self.get_for_handler(key)
                matches.append((key, filter))
            except MissingFilterError:
                missing.append(key)

        return matches, missing
