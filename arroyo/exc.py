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


class ArgumentsError(Exception):
    pass


class GenericPluginError(Exception):
    pass


class IncompatibleQueryError(Exception):
    """
    Raised by Providers if cant generate an URI for a query
    """
    pass


class QueryConversionError(Exception):
    pass


class DuplicatedDownloadError(Exception):
    """Requested download already exists

    Raised by downloader plugins
    """
    pass


class DownloadNotFoundError(Exception):
    """Requested download doesn't exists

    Raised by downloader plugins
    """
    pass


class MissingFilterError(Exception):
    pass


class ConflictingFilterError(Exception):
    def __init__(self, collisions, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collisions = collisions
