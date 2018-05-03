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


import hashlib
from urllib import parse

from arroyo import (
    Application,
    SettingsKey,
    Source
)
from arroyo.helpers.mediaparser import MediaParser


def mock_source(name, type=None, **kwargs):
    if 'provider' not in kwargs:
        kwargs['provider'] = 'mock'

    if 'uri' not in kwargs:
        kwargs['uri'] = 'magnet:?xt={urn}&dn={dn}'.format(
            urn='urn:btih:' + hashlib.sha1(name.encode('utf-8')).hexdigest(),
            dn=parse.quote_plus(name))

    return Source(name=name, type=type, **kwargs)


def analyze(src):
    mp = MediaParser()
    entity, tags = mp.parse(src)
    src.entity = entity
    src.tags = tags
    return src


def source(*args, **kwargs):
    return analyze(mock_source(*args, **kwargs))


class TestApp(Application):
    def __init__(self, settings=None):
        if settings is None:
            settings = {}

        settings[SettingsKey.DB_URI] = 'sqlite:///:memory:'
        super().__init__(settings)
