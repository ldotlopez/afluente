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


import asyncio
import traceback
import sys
from urllib import parse


import appkit
from appkit import utils
from appkit.blocks import cache
from appkit.libs import urilib


from arroyo import kit


class Origin:
    __slots__ = (
        'iterations',
        'provider',
        'uri')

    def __init__(self, provider, uri=None, iterations=1):
        if not isinstance(provider, kit.ProviderExtension):
            raise TypeError(provider)

        if uri is None:
            uri = provider.DEFAULT_URI
        else:
            uri = urilib.normalize(uri)

        iterations = int(iterations)
        if iterations < 0:
            raise ValueError(iterations)

        self.provider = provider
        self.uri = uri
        self.iterations = iterations

    @property
    def provider_name(self):
        return self.provider.__extension_name__


class ScanCache(cache.DiskCache):
    def __init__(self, *args, **kwargs):
        basedir = (
            kwargs.pop('basedir', None) or
            utils.user_path(utils.UserPathType.CACHE, name='scan')
        )
        delta = kwargs.pop('delta', None) or 60*60
        super().__init__(*args, basedir=basedir, delta=delta, **kwargs)

    def encode_key(self, query):
        data = query.asdict()
        data = sorted(data.items())
        key = parse.urlencode(data)
        return self.basedir / key


class Scanner:
    def __init__(self, logger=None, providers=None):
        if providers is None:
            msg = "No providers supplied"
            raise ValueError(providers, msg)

        self.logger = logger or appkit.Null
        self.cache = ScanCache()
        self.providers = providers

    def scan(self, query):
        # def _scan(origins_data):
        #     for source in origins_data:
        #         try:
        #             entity, meta = self.app.mediainfo.ng_parse(source)
        #         except mediainfo.ParseError as e:
        #             msg = "Unable to parse mediainfo for {source}"
        #             msg = msg.format(source=source.name)
        #             self.logger.warning(msg)
        #             continue

        #         yield source._replace(
        #             entity=entity,
        #             meta=meta)

        try:
            ret = self.cache.get(query)
            msg = "Scan data found in cache"
            self.logger.debug(msg)
            return ret
        except KeyError:
            msg = "Scan data missing from cache"
            self.logger.debug(msg)

        # Get origins for query
        origins = self.origins_for_query(query)

        origins_data = self.process(*origins)

        # ret = list(_scan(origins_data))
        ret = [
            (kit.Source(**x), None)
            for x in origins_data
        ]

        self.cache.set(query, ret)
        return ret

    def origins_for_query(self, query):
        """Get autogenerated origins for a selector.QuerySpec object.

        One query can produce zero or more or plugin.Origins from the activated
        origin extensions.

        Returned origins are configured with one iteration.
        """

        msg = "Discovering origins for {query!r}"
        msg = msg.format(query=query)
        self.logger.info(msg)

        exts_and_uris = []

        for (name, ext) in self.providers:
            uri = ext.get_query_uri(query)
            if uri:
                msg = " Found compatible origin '{name}'"
                msg = msg.format(name=name)
                self.logger.info(msg)
                exts_and_uris.append((ext, uri))

        if not exts_and_uris:
            msg = "No compatible origins found for {query!r}"
            msg = msg.format(query=query)
            self.logger.error(msg)
            return []

        origins = [Origin(p, uri=uri) for (p, uri) in exts_and_uris]
        return origins

    def process(self, *origins):
        def _process(origins_data):
            for (origin, uri, data) in origins_data:
                provider_name = origin.provider.__extension_name__

                try:
                    data['provider'] = provider_name
                    yield data
                    # yield coretypes.Source(
                    #     provider=provider_name,
                    #     **data)

                except ValueError as e:
                    msg = "Error from {provider}: {e}"
                    msg = msg.format(provider=provider_name, e=str(e))
                    self.logger.warning(msg)

        origins_data = self.get_data_from_origins(*origins)
        return list(_process(origins_data))

    def get_data_from_origins(self, *origins):
        results = []

        @asyncio.coroutine
        def collect(origin):
            res = yield from self.get_buffers_from_origin(origin)
            results.extend(res)

        tasks = [collect(o) for o in origins]
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*tasks))

        data = []
        for (origin, uri, res) in results:
            if isinstance(res, Exception) or res is None or res == '':
                continue

            try:
                res = origin.provider.parse(res)

            # except arroyo.exc.OriginParseError as e:
            #     msg = "Error parsing «{uri}»: {e}"
            #     msg = msg.format(uri=uri, e=e)
            #     self.logger.error(msg)
            #     continue

            except Exception as e:
                print(traceback.format_exc(), file=sys.stderr)
                msg = "Unhandled exception {type}: {e}"
                msg = msg.format(type=type(e), e=e)
                self.logger.critical(msg)
                continue

            if res is None:
                msg = ("Incorrect API usage in {origin}, return None is not "
                       "allowed. Raise an Exception or return [] if no "
                       "sources are found")
                msg = msg.format(origin=origin)
                self.logger.critical(msg)
                continue

            if not isinstance(res, list):
                msg = "Invalid data type for URI «{uri}»: '{type}'"
                msg = msg.format(uri=uri, type=res.__class__.__name__)
                self.logger.critical(msg)
                continue

            if len(res) == 0:
                msg = "No sources found in «{uri}»"
                msg = msg.format(uri=uri)
                self.logger.warning(msg)
                continue

            data.extend([(origin, uri, x) for x in res])

            msg = "{n} sources found at {uri}"
            msg = msg.format(n=len(res), uri=uri)
            self.logger.info(msg)

        return data

    @asyncio.coroutine
    def get_buffers_from_origin(self, origin):
        """ Get all buffers from origin.

        An Origin can have several 'pages' or iterations.
        This methods is responsable to generate all URIs needed from origin
        and Importer.get_buffer_from_uri from each of them.

        Arguments:
          origin - The origin to process.
        Return:
          A list of tuples for each URI, see Importer.get_buffer_from_uri for
          information about those tuples.
        """
        g = origin.provider.paginate(origin.uri)
        iterations = max(1, origin.iterations)

        # Generator can raise StopIteration before iterations is reached.
        # We use a for loop instead of a comprehension expression to catch
        # gracefully this situation.
        tasks = []
        for i in range(iterations):
            try:
                uri = next(g)
                tasks.append(self.get_buffer_from_uri(origin, uri))
            except StopIteration:
                msg = ("{provider} has stopped the pagination after "
                       "iteration #{index}")
                msg = msg.format(provider=origin.provider, index=i)
                self.logger.warning(msg)
                break

        ret = yield from asyncio.gather(*tasks)
        return ret

    @asyncio.coroutine
    def get_buffer_from_uri(self, origin, uri):
        """ Get buffer (read) from URI using origin.

        In the 99% of the cases this means fetch some data from network

        Return:
          A tuple (origin, uri, result) where:
          - origin is the original origin argument
          - uri is the original uri argument
          - result is a bytes object with the content from uri or an Exception
            if something goes wrong
        """
        try:
            result = yield from origin.provider.fetch(uri)

        except (asyncio.CancelledError,
                asyncio.TimeoutError) as e:
                # aiohttp.errors.ClientOSError,
                # aiohttp.errors.ClientResponseError,
                # aiohttp.errors.ServerDisconnectedError) as e:
            msg = "Error fetching «{uri}»: {msg}"
            msg = msg.format(
                uri=uri, type=e.__class__.__name__,
                msg=str(e) or 'no reason')
            self.logger.error(msg)
            result = e

        except Exception as e:
            print(traceback.format_exc(), file=sys.stderr)
            msg = "Unhandled exception {type}: {e}"
            msg = msg.format(type=type(e), e=e)
            self.logger.critical(msg)
            result = e

        if (not isinstance(result, Exception) and
                (result is None or result == '')):
            msg = "Empty or None buffer for «{uri}»"
            msg = msg.format(uri=uri)
            self.logger.error(msg)

        return (origin, uri, result)