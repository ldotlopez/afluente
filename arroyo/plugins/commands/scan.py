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


class ScanConsoleCommand(kit.ConsoleCommandExtension):
    __extension_name__ = 'scan'

    HELP = 'Scan sources (i.e. websites)'
    PARAMETERS = (
        kit.Parameter(
            'provider',
            type=str,
            default=None,
            help='Provider to use. Guessed from uri by default'),
        kit.Parameter(
            'uri',
            abbr='u',
            type=str,
            default=None,
            help='Base URI to scan'),
        kit.Parameter(
            'iterations',
            abbr='i',
            type=int,
            default=1,
            help=('Iterations to run over base URI (Think about pages in a '
                  'website)')),
        kit.Parameter(
            'type',
            abbr='t',
            type=str,
            help='Override type of found sources'),
        kit.Parameter(
            'language',
            abbr='l',
            type=str,
            help='Override language of found sources'),
        kit.Parameter(
            'from-config',
            action='store_true',
            default=False,
            help='Import from the origins defined in the configuration file')
    )

    def main(self, provider=None, uri=None, iterations=1, type=None,
             language=None, from_config=True):
        super().main()


# TODO: Disable extensions for now. This command may be irrelevant in arroyo 2
#
# __arroyo_extensions__ = [
#     ScanConsoleCommand
# ]
