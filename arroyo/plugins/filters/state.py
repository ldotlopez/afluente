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


from arroyo import kit
from arroyo.helpers import database


class StateFilter(kit.FilterExtension):
    __extension_name__ = 'state'

    HANDLES = (
        'state',
    )

    def filter(self, key, value, source):
        if not source.entity:
            return False

        try:
            db_obj = self.shell.db.get_object(source.entity)
        except database.NoResultsFoundError:
            return True

        import ipdb; ipdb.set_trace(); pass


__arroyo_extensions__ = (StateFilter,)
