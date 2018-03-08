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


from arroyo import kit


class TagFilters(kit.FilterExtension):
    __extension_name__ = 'advancedfilters'

    HANDLES = (
        # h264, x264
        'codec',
        # rartv, eztv
        'distributor',
        # webrip, web-dl
        'format',
        # 480p (hdtv), 720p, 1080p, etc...
        'quality',
        # rarbg, ion10, sva
        'release_group'
    )

    def _match_sets(self, key, value, item):
        try:
            return getattr(item.entity, key) == value

        except (AttributeError, KeyError):
            return False

    def _apply_set_match(self, key, user_value, src):
        try:
            tag_value = src.tags[key]
        except KeyError:
            return False

        if isinstance(tag_value, list):
            tag_value = set([x.lower() for x in tag_value])
        else:
            tag_value = set([tag_value.lower()])

        if tag_value.intersection(user_value):
            return True

    def _apply_quality(self, quality, src):
        if 'video.screen-size' in src.tags:
            tag_value = src.tags['video.screen-size']
        else:
            tag_value = '480p'

        return quality == tag_value

    def _apply_format(self, format, src):
        tag = src.tags.get('video.format')
        if not tag:
            return False

        return format == tag.value.lower()

    def apply(self, key, value, it):
        m = {
            'distributor': 'release.distributors',
            'format': 'video.format',
            'quality': 'video.screen-size',
            'release_group': 'release.group',
        }

        if key in ('distributor', 'release_group'):
            key = m[key]
            user_value = set([x.strip().lower() for x in value.split(',')])
            fn = functools.partial(self._apply_set_match, key, user_value)

        elif key == 'quality':
            value = value.lower()
            if value == 'hdtv':
                value = '480p'

            fn = functools.partial(self._apply_quality, value)

        elif key == 'format':
            fn = functools.partial(self._apply_format, value.lower())

        else:
            raise NotImplementedError(key)

        return filter(lambda x: fn(x), it)


__arroyo_extensions__ = (TagFilters,)
