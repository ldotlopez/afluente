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


import arroyo.extensions


class EpisodeFieldFilters(arroyo.extensions.FilterExtension):
    __extension_name__ = 'episode'

    HANDLES = (
        'series',
        'series_year',
        'series_country',
        'season',
        'number'
    )

    def _exact_match(self, key, value, item):
        # Don't use try-except block, it can mask underliying exceptions
        if not hasattr(item, 'entity'):
            return False

        return getattr(item.entity, key) == value

    def apply(self, key, value, it):
        if key in ('series', 'season', 'number'):
            if key in ('season', 'number'):
                value = int(value)

            fn = functools.partial(self._exact_match, key, value)

        elif key in ('series-year', 'series-country'):
            fn = functools.partial(self._exact_match, 'modifier', value)

        else:
            raise NotImplementedError(key)

        return filter(lambda x: fn(x), it)


__arroyo_extensions__ = (EpisodeFieldFilters,)
