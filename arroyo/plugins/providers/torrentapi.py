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


# API docs:
# https://torrentapi.org/apidocs_v2.txt
#
# torrentapi json_extended format:
#
# {'category': 'TV Episodes',
#  'download': 'magnet:?xt=urn:btih:000000000000000000000000000000000000000000000000&dn=Westworld.S01E10.iNTERNAL.HDTV.x264-TURBO%5Brartv%5D&tr=http%3A%2F%2Ftracker.trackerfix.com%3A80%2Fannounce&tr=udp%3A%2F%2F9.rarbg.me%3A2710&tr=udp%3A%2F%2F9.rarbg.to%3A2710&tr=udp%3A%2F%2Fopen.demonii.com%3A1337%2Fannounce',
#  'episode_info': {'airdate': '2016-12-04',
#                   'epnum': '10',
#                   'imdb': 'tt0475784',
#                   'seasonnum': '1',
#                   'themoviedb': '63247',
#                   'title': 'The Bicameral Mind',
#                   'tvdb': '296762',
#                   'tvrage': '37537'},
#  'info_page': 'https://torrentapi.org/redirect_to_info.php?token=xxxxxxxxxx&p=x_x_x_x_x_x_x__xxxxxxxxxx',
#  'leechers': 6,
#  'pubdate': '2016-12-06 10:13:24 +0000',
#  'ranked': 1,
#  'seeders': 85,
#  'size': 583676381,
#  'title': 'Westworld.S01E10.iNTERNAL.HDTV.x264-TURBO[rartv]'}

# If no torrents found (but there are no errors from API) this response is send:
# {"error":"No results found", "error_code":20}


import asyncio
import json
import time
from datetime import datetime
from urllib import parse


import aiohttp
from appkit.libs import urilib


import arroyo.extensions


class TorrentAPI(arroyo.extensions.ProviderExtension):
    __extension_name__ = 'torrentapi'

    DEFAULT_URI = r'http://torrentapi.org/pubapi_v2.php?mode=list'

    URI_PATTERNS = [
        r'^http(s)?://([^.]+.)?torrentapi\.org/pubapi_v2.php\?'
    ]

    TOKEN_URL = 'http://torrentapi.org/pubapi_v2.php?get_token=get_token&app_id=arroyo'
    SEARCH_URL = r'http://torrentapi.org/pubapi_v2.php?mode=search&app_id=arroyo'

    CATEGORY_MAP = {
        'episode': '18;41;49',
        'movie': '14;48;17;44;45;47;50;51;52;42;46'
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = self.shell.logger.getChild('provider.torrentapi')
        self.last_request = None
        self.token = None
        self.token_ts = 0
        self.token_last_use = 0
        self._tz_diff = datetime.utcnow() - datetime.now()

    @asyncio.coroutine
    def throttle(self):
        now = time.time()

        if self.last_request is None:
            self.last_request = now
            return

        diff = self.last_request - now
        if diff < 2:
            yield from asyncio.sleep(2 - diff)

        self.last_request = time.time()

    @asyncio.coroutine
    def fetch(self, uri):
        yield from self.refresh_token()
        uri = urilib.alter_query_params(
            uri,
            dict(
                format='json_extended',
                limit=100,
                sort='last',
                token=self.token)
        )

        yield from self.throttle()
        return (yield from super().fetch(uri))

    @asyncio.coroutine
    def refresh_token(self):
        if time.time() - self.token_ts < 15*60:
            return

        conn = aiohttp.TCPConnector(verify_ssl=False)
        client = aiohttp.ClientSession(connector=conn)

        yield from self.throttle()
        resp = yield from client.get(self.TOKEN_URL)
        buff = yield from resp.content.read()

        yield from resp.release()
        yield from client.close()

        self.token = json.loads(buff.decode('utf-8'))['token']
        self.token_ts = time.time()
        self.token_last_use = None

    def parse(self, buff):
        def convert_data(e):
            return {
                'name': e.get('title') or e.get('filename'),
                'uri': e['download'],
                'timestamp': self.parse_timestamp(e.get('pubdate', None)),
                'seeds': e.get('seeders', None),
                'leechers': e.get('leechers', None),
                'size': e.get('size', None),
                'type': self.parse_category(e['category'])
            }

        try:
            data = json.loads(buff.decode('utf-8'))
        except json.decoder.JSONDecodeError as e:
            msg = "Error parsing json response: {e}"
            msg = msg.format(e=str(e))
            self.logger.error(msg)
            return []

        try:
            psrcs = data['torrent_results']
        except KeyError:
            if data.get('error_code', None) != 20:
                msg = "Invalid response, missing torrent_results key. Data: {data}"
                msg = msg.format(data=repr(data))
                self.logger.error(msg)

            return []

        ret = [convert_data(x) for x in psrcs]
        return ret

    def get_query_uri(self, query):
        try:
            querystr = str(query)
        except arroyo.exc.QueryConversionError as e:
            err = "Incomprehensible query"
            raise arroyo.exc.IncompatibleQueryError(err) from e

        qs = dict(search_string=querystr)
        try:
            qs['category'] = self.CATEGORY_MAP[query.type]
        except AttributeError:
            err = "Unclassifiable type '{type}'"
            err = err.format(type=query.type)
            raise kit.IncompatibleQueryError(err)

        return self.SEARCH_URL + "&" + parse.urlencode(qs)

    @classmethod
    def parse_category(cls, category):
        """
        Categories from torrentapi can be confusing: can be are 'Episodes/TV'
        or 'Movies/TV-UHD-Episodes'.
        For this reason we check for 'movie' or 'episode' in the category or
        in the subcategory using 'checks'
        """
        if not category:
            return None

        category = category.lower()
        try:
            checks = reversed(category.split('/', 1))
        except ValueError:
            checks = [category]

        for check in checks:
            if 'movie' in check:
                return 'movie'

            elif 'episodes' in check:
                return 'episode'

        return None

    def parse_timestamp(self, timestamp):
        """
        timestamp: '2017-09-06 14:50:59 +0000'

        From API docs:
        > All api times are returned in UTC.

        Good boy torrentapi, good boy.
        """
        if not timestamp:
            return None

        timestamp, tz = timestamp[0:19], timestamp[-5:]
        if tz != '+0000':
            msg = "Unexpected tz: {tz}"
            msg = msg.format(tz=tz)
            self.logger.warning(msg)
            return None

        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        dt = dt - self._tz_diff

        return int(time.mktime(datetime.timetuple(dt)))


__arroyo_extensions__ = (TorrentAPI,)
