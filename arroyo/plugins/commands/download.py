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


# from arroyo import (
#     downloads,
#     selector,
#     pluginlib
# )


# import itertools
# import functools
# import re
# import sys


# import humanfriendly
# import tabulate

# models = pluginlib.models


import appkit
from arroyo import kit


class DownloadConsoleCommand(kit.CommandExtension):
    __extension_name__ = 'download'

    PARAMETERS = (
        # Selecting
        kit.Parameter(
            'from-config',
            action='store_true',
            help=("Download sources from queries defined in the configuration "
                  "file")),

        kit.Parameter(
            'filter',
            abbr='f',
            dest='filters',
            type=str,
            default={},
            action=appkit.ArgParseDictAction,
            help=('Select and download sources using filters. See search '
                  'command for more help')),

        kit.Parameter(
            'keywords',
            nargs='*',
            help='keywords')
    )

    def main(self, filters, **kwargs):
        q = kit.Query(**filters)
        self.shell.search(q)


__arroyo_extensions__ = [
    DownloadConsoleCommand,
]
