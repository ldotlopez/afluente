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


import fnmatch
import functools


import arroyo
import arroyo.extensions


class SourceFieldsFilter(arroyo.extensions.FilterExtension):
    __extension_name__ = 'sourcefields'

    HANDLES = (
        'name',
        'name_glob',
        'language',
        'type',
        'provider',
        'uri_glob')

    def _exact_match(self, key, value, item):
        try:
            val = getattr(item, key)
            return val == value

        except KeyError:
            return False

    def _glob_match(self, key, value, item):
        try:
            val = getattr(item, key)
            return fnmatch.fnmatch(val.lower(), value)

        except KeyError:
            return False

    def _type_match(self, key, value, item):
        _map = {
            'source': lambda x: isinstance(x, arroyo.Source),
            'episode': lambda x: x.entity and isinstance(x.entity, arroyo.Episode),
            'movie': lambda x: x.entity and isinstance(x.entity, arroyo.Movie),
        }
        try:
            return _map[value](item)
        except KeyError:
            pass

        raise ValueError((key, value))

    def apply(self, key, value, it):
        if key in ('name', 'provider'):
            fn = functools.partial(self._exact_match, key, value)

        elif key in ('name_glob'):
            fn = functools.partial(self._glob_match, key[:-5], value.lower())

        elif key == 'type':
            fn = functools.partial(self._type_match, key, value.lower())

        else:
            raise ValueError(key)

        return filter(
            lambda x: fn(x),
            it)


__arroyo_extensions__ = (SourceFieldsFilter,)
