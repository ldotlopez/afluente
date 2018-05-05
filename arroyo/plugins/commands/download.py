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

    def process_query(self, query, manual=False, force=False):
        # curr_log_level = self.shell.settings.get(arroyo.SettingsKey.LOG_LEVEL)
        # curr_log_level = getattr(logging, curr_log_level)
        # in_debug = curr_log_level <= logging.DEBUG

        results = self.shell.search(query)
        results = list(self.shell.filter(results, query))

        if not results:
            msg = "Looking for '{query}': no results found."
            msg = msg.format(query=query)
            self.logger.info(msg)
            return

        groups = self.shell.group(results)

        msg = "Looking for '{query}': Found {n_total} matches in {n_groups} groups."
        msg = msg.format(query=query, n_total=len(results), n_groups=len(groups))
        self.logger.info(msg)

        for (idx, (entity, srcs)) in enumerate(groups):
            entity, srcs = self.merge(entity, srcs)

            try:
                selected = self.select(entity, srcs, query,
                                       manual=manual, force=force)

            except NoCandidatesFoundError as e:
                msg = "No candidates found"
                print(msg)
                continue

            except AlreadySelectedError as e:
                msg = "Already downloading/downloaded"
                print(msg)
                continue

            except CancelSelectionError as e:
                continue

            if selected is None:
                msg = "No selection for {entity}"
                msg = format(msg, entity=str(entity))
                self.logger.info(msg)
                continue

            self.shell.download(selected)
            msg = "Downloading {src}"
            msg = msg.format(src=selected)
            print(msg)

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
            raise AlreadySelectedError()

        not_dowloading = [src for src in sources if not src.download]

        if not manual:
            return self.shell.select(not_dowloading, query)

        if not not_dowloading:
            raise NoCandidatesFoundError()

        msg = "Select one source for {entity}"
        msg = msg.format(entity=entity)
        print(msg)

        while True:
            for (idx, src) in enumerate(not_dowloading):
                msg = "{idx}. {src}"
                msg = msg.format(idx=idx+1, src=src)
                print(msg)

            try:
                n = int(input("? ")) - 1
            except KeyboardInterrupt as e:
                msg = "Canceled.\n"
                print(msg)
                raise CancelSelectionError() from e
            except (ValueError, TypeError) as e:
                msg = "Invalid selection. (control-c) to cancel selection"
                print(msg)
                continue

            if n < 0 or n >= len(not_dowloading):
                msg = "Invalid selection. (control-c) to cancel selection"
                print(msg)
                continue

            return not_dowloading[n]

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
                self.process_query(query, manual=manual, force=force)

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


class AlreadySelectedError(Exception):
    pass


class CancelSelectionError(Exception):
    pass


class NoCandidatesFoundError(Exception):
    pass


__arroyo_extensions__ = [
    DownloadConsoleCommand,
]
