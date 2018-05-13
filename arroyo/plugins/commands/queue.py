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


import itertools

import arroyo
from arroyo.extensions import (
    CommandExtension,
    Parameter
)


class DownloadQueue(CommandExtension):
    __extension_name__ = 'queue'
    HELP = "Query and handle download queue"

    PARAMETERS = (
        Parameter(
            'list',
            action='store_true',
            help="Show current download queue"),

        Parameter(
            'cancel',
            nargs='+',
            action='append',
            help="Cancel a download"),

        Parameter(
            'archive',
            nargs='+',
            action='append',
            help="Cancel a download"),

    )

    def _translate_ids(self, ids):
        def flatten(x):
            if not isinstance(x, list):
                yield x
                return

            for i in x:
                yield from flatten(i)

        if ids is None:
            return None

        ids = [x.lower() for x in flatten(ids)]

        downloads = self.shell.downloads.list()

        if 'all' in ids:
            return downloads

        downloads = {x.id: x for x in downloads}

        ids_ = []
        for id in itertools.chain.from_iterable(ids):
            try:
                id = int(id)
            except (ValueError, TypeError) as e:
                id = None

            if id is None or id not in downloads:
                errmsg = "{id} is not a valid identifier"
                errmsg = errmsg.format(id=id)
                raise arroyo.exc.GenericPluginError(errmsg)

            ids_.append(id)

        return [downloads[x] for x in ids_]

    # def _id_to_source(self, id_):
    #     id_ = int(id_)
    #     return self.shell.db.session\
    #         .query(arroyo.Source)\
    #         .filter_by(id=id_)\
    #         .one()

    def main(self,
             list=False,
             cancel=None, archive=None):

        cancel = self._translate_ids(cancel)
        archive = self._translate_ids(archive)

        if list:
            for dl in self.shell.downloads.list():
                print(dl.id, dl)

        elif cancel:
            for dl in cancel:
                self.shell.downloads.cancel(dl)

        elif archive:
            for dl in cancel:
                self.shell.downloads.cancel(dl)


__arroyo_extensions__ = (DownloadQueue,)
