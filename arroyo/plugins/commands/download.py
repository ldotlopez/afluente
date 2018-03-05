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


import pathlib
import pickle


import appkit
from appkit import utils


from arroyo import kit


SAV_FILE = (
    pathlib.Path(utils.user_path(utils.UserPathType.CACHE)) /
    'last-search.dat')


class DownloadConsoleCommand(kit.CommandExtension):
    __extension_name__ = 'download'

    PARAMETERS = (
        kit.Parameter(
            'from-config',
            action='store_true',
            help=("Download sources from queries defined in the configuration "
                  "file")),

        kit.Parameter(
            'replay',
            action='store_true',
            help=("Show last search results")),

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

    def main(self, replay=False, filters=None, keywords=None,
             from_config=True):
        if replay:
            with SAV_FILE.open('rb') as fh:
                results = pickle.load(fh)
                self.display_results(results)
            return

        elif filters:
            query = kit.Query(**filters)
        elif keywords:
            query = kit.Query(' '.join(keywords))
        elif from_config:
            raise NotImplemented()
        else:
            raise NotImplemented()

        results = self.shell.search(query)
        if not results:
            err = "No results found"
            self.shell.logger.error(err)
            return

        results = self.shell.filter(results, query)
        if not results:
            err = "No matching results found"
            self.shell.logger.error(err)
            return

        results = [(leader, list(group))
                   for (leader, group)
                   in self.shell.group(results)]

        with SAV_FILE.open('wb+') as fh:
            pickle.dump(results, fh)

        self.display_results(results)

    def display_results(self, results):
        i = 1
        for (leader, group) in results:
            print(leader or 'None')
            print('----')
            for src in group:
                msg = "[{id}]   {src!r}"
                msg = msg.format(id=i, src=src)
                print(msg)
                i += 1
            print()


__arroyo_extensions__ = [
    DownloadConsoleCommand,
]
