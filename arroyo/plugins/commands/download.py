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


import appkit


from arroyo.extensions import (
    CommandExtension,
    Parameter
)


class DownloadConsoleCommand(CommandExtension):
    __extension_name__ = 'download'

    PARAMETERS = (
        Parameter(
            'list',
            action='store_true',
            help="Show current downloads"),

        Parameter(
            'cancel',
            help="Cancel a download"),

        Parameter(
            'archive',
            help="Cancel a download"),

        Parameter(
            'force',
            action='store_true',
            help='Force downloading of already downloaded items.'),

        Parameter(
            'from-config',
            action='store_true',
            help=("Download sources from queries defined in the configuration "
                  "file")),

        Parameter(
            'manual',
            action='store_true',
            help=("Manualy select downloads")),

        Parameter(
            'filter',
            abbr='f',
            dest='filters',
            type=str,
            default={},
            action=appkit.ArgParseDictAction,
            help=('Select and download sources using filters. See search '
                  'command for more help')),

        Parameter(
            'keywords',
            nargs='*',
            help='keywords')
    )

    def merge(self, entity, sources):
        if entity:
            entity = self.shell.db.merge(entity)
            sources = entity.sources
        else:
            sources = [self.shell.db.merge(src) for src in sources]

        return entity, sources

    def select(self, entity, sources, query, manual=False, force=False):
        downloading = [src for src in sources if src.download]

        if downloading and not force:
            msg = "{entity} already downloaded"
            msg = msg.format(entity=str(entity))
            print(msg)
            return None

        if manual:
            print(str(entity))
            for (idx, src) in enumerate(sources):
                msg = "{idx}. {src}"
                msg = msg.format(idx=idx+1, src=src)
                print(msg)
            print()

            while True:
                n = input("Selection? ")
                try:
                    n = int(n) - 1
                    if n < 0:
                        raise IndexError(n)

                    selected = sources[int(n) - 1]
                except (ValueError, IndexError):
                    print("Value not valid")
                    continue

                return selected

        return self.shell.select(sources, query)

    def main(self,
             list=False,
             cancel=None, archive=None,
             filters=None, keywords=None, from_config=False,
             force=False,
             manual=False):

        if list:
            for dl in self.shell.get_downloads():
                print(dl.id, dl)

        elif cancel:
            self.shell.cancel(cancel)

        elif archive:
            self.shell.archive(archive)

        elif filters or keywords or from_config:
            if keywords:
                keywords = ' '.join(keywords)
                # Use type=None by default to allow autodetection of media type
                queries = [self.shell.get_query_from_keywords(
                    keywords, type=filters.get('type'))]

            elif filters:
                queries = [self.shell.get_query_from_params(**filters)]

            elif from_config:
                queries = self.shell.get_queries_from_config()

            else:
                raise NotImplementedError()

            for query in queries:
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

                groups = self.shell.group(results)
                for (entity, srcs) in groups:
                    entity, srcs = self.merge(entity, srcs)
                    selected = self.select(entity, srcs, query,
                                           manual=manual, force=force)

                    if selected is None:
                        msg = "No selection for {entity}"
                        msg = msg.format(entity=str(entity))
                        continue

                    self.shell.download(selected)
                    msg = "Downloading {src}"
                    msg = msg.format(src=selected)
                    print(msg)

        else:
            raise NotImplementedError()

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
