# -*- coding: utf-8 -*-

# Copyright (C) 2015 Luis López <luis@cuarentaydos.com>
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


import arroyo


import functools
import sys


class BasicSorter(arroyo.extensions.SorterExtension):
    __extension_name__ = 'basic'

    def cmp_source_health(self, a, b):
        def get_tag(src, tag_name, *args, **kwargs):
            return src.tags.get(tag_name, *args, **kwargs)

        def is_proper(src):
            return get_tag(src, 'core.release.proper', False)

        def has_release_group(src):
            return get_tag(src, 'core.release.group', None) is not None

        def seeds_are_relevant(src):
            return (src.seeds or 0) > 10

        def get_share_ratio(src):
            seeds = src.seeds if src.seeds is not None else 0
            leechers = src.leechers if src.leechers is not None else 0

            if not src.seeds and not src.leechers:
                return None

            if seeds and leechers == 0:
                return float(sys.maxsize)

            if seeds == 0 and leechers:
                return 0.0

            return seeds / leechers

        # proper over non-proper
        a_is_proper = is_proper(a)
        b_is_proper = is_proper(b)

        if a_is_proper and not b_is_proper:
            return -1

        if b_is_proper and not a_is_proper:
            return 1

        #
        # Priorize s/l info over others
        #
        if seeds_are_relevant(a) and not seeds_are_relevant(b):
            return -1

        if seeds_are_relevant(b) and not seeds_are_relevant(a):
            return 1

        #
        # Order by seed ratio
        #
        if (a.leechers and b.leechers):
            a_ratio = get_share_ratio(a)
            b_ratio = get_share_ratio(b)

            try:
                balance = (max(a_ratio, b_ratio) /
                           min(a_ratio, b_ratio))
                if balance > 1.2:
                    return -1 if a_ratio > b_ratio else 1

            except ZeroDivisionError:
                return -1 if int(a_ratio) else 1

            return -1 if a.seeds > b.seeds else 1

        #
        # Put releases from a team over others
        #
        a_has_release_team = has_release_group(a)
        b_has_release_team = has_release_group(b)

        if a_has_release_team and not b_has_release_team:
            return -1
        if b_has_release_team and a_has_release_team:
            return 1

        # Nothing makes one source better that the other
        # Fallback to default sort
        if a == b:
            return 0

        return -1 if a < b else 1

    def sort(self, items, query):
        return sorted(items, key=functools.cmp_to_key(self.cmp_source_health))


__arroyo_extensions__ = (
    BasicSorter,
)
