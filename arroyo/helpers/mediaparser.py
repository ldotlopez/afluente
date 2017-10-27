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


from urllib import parse


import guessit
from appkit.blocks import cache
from appkit import utils, Null
from arroyo import kit

PARSEABLE_TYPES = ['']

# {
#     Entity name: (guessit key, Entity attribute, transformation)
# }
ENTITY_FIELD_TRANSLATIONS = {
    'episode': [
        ('title', 'series'),
        ('year', 'modifier', str),
        ('season', 'season'),
        ('episode', 'number', int)
    ],

    'movie': [
        ('title', 'title'),
        ('year', 'modifier', str),
    ],
}

# [
#     (guessit keu, SourceTag key, transformation)
# ]
META_FIELD_TRANSLATIONS = [
    ('audio_channels', 'audio.channels'),
    ('audio_codec', 'audio.codec'),
    ('container', 'media.container'),
    ('country', 'media.country'),
    ('date', 'media.date'),
    ('episode_title', 'episode.title'),
    ('episode_count', 'episode.count'),
    ('episode_details', 'episode.details'),
    ('format', 'video.format'),
    ('language', 'media.language'),
    ('mimetype', 'mimetype'),
    ('proper_count', 'release.proper', lambda x: int(x) > 0),
    ('other', 'guessit.other'),
    ('release_distributors', 'release.distributors'),
    ('release_group', 'release.group'),
    ('screen_size', 'video.screen-size'),
    ('streaming_service', 'streaming.service'),
    ('subtitle_language', 'media.subtitle.language'),
    ('uuid', 'guessit.uuid'),
    ('video_codec', 'video.codec'),
    ('website', 'release.website')
]

# keep lower case!!
KNOWN_DISTRIBUTORS = [
    'ethd',
    'eztv',
    'rartv',
]  


class ParseError(Exception):
    pass


class InvalidEntityError(Exception):
    pass


def transfer_items(input, output, translations):
    for translation in translations:
        if len(translation) == 3:
            orig, dest, fn = translation
        else:
            orig, dest = translation
            fn = None

        if orig in input:
            value = input.pop(orig)
            if fn:
                try:
                    value = fn(value)
                except (TypeError, ValueError):
                    # unexpected value
                    pass

            output[dest] = value


class MediaParser:
    def __init__(self, logger=None):
        # app.signals.connect('sources-added-batch', self._on_source_batch)
        # app.signals.connect('sources-updated-batch', self._on_source_batch)
        self.logger = logger or Null
        self.cache = ParseCache()

    def parse(self, source, metatags=None):
        type = source.type
        entity, metatags, other = None, metatags or {}, {}

        # Skip detection
        if type == 'other':
            pass

        elif type in ['episode', 'movie', None]:
            # Episode, Movies: parse by guessit
            entity, meta, other = self._guessit_parse(source, metatags={})

        elif type in ['ebook']:
            # Book: parse by _book_parse
            ebook_data, meta, other = self._ebook_parse(source, metatags={})

        # Warn about leftovers
        for (key, value) in other.items():
            msg = "{source} has a non identified property {key}={value}"
            msg = msg.format(source=source.name, key=key, value=value)
            self.logger.warning(msg)

        return entity, meta

    def _ebook_parse(self, source, metatags):
        try:
            return (
                None,
                {
                    'author': metatags['ebook.author'],
                    'title': metatags['ebook.title'],
                },
                {})
        except KeyError:
            return None, {}, {}

    def _guessit_parse(self, source, metatags):
        # Release teams ofter are shadowed by 'distributors' (eztv, rartv,
        # etc...) because guessit doesn't do a perfect job.
        # In order to fix this we made a "preprocessing" to extract (and
        # remove) known distributors from source's name and add distribution
        # field into info after processing source's name with guessit.

        name = source.name
        type = source.type

        distributors = set()

        for dist in KNOWN_DISTRIBUTORS:
            tag = '[' + dist + ']'
            idx = name.lower().find(tag)
            if idx == -1:
                continue

            name = (name[:idx] + name[idx+len(tag):]).strip()
            distributors.add(dist)

        info = guessit.guessit(name, options={'type': type})

        # Save distributors into info
        if distributors:
            info['release_distributors'] = list(distributors)

        # Cleanup info
        info = {k: v for (k, v) in info.items() if v is not None}

        # FIXME: Don't drop, save
        # Drop multiple languages and multiple episode numbers
        for k in ['language', 'part']:
            if isinstance(info.get(k), list):
                msg = 'Drop multiple instances of {key} in {source}'
                msg = msg.format(source=data['name'], key=k)
                self.logger.warning(msg)
                info[k] = info[k][0]

        # Integrate part as episode in season 0
        if 'part' in info:
            if info.get('type') == 'movie':
                msg = "Movie '{source}' has 'part'"
                msg = msg.format(source=data['name'])
                self.logger.warning(msg)

            elif info.get('type') == 'episode':
                if 'season' in info:
                    msg = ("Episode '{source}' has 'part' and 'season'")
                    msg = msg.format(
                        source=data['name'], type=info.get('type') or '(None)'
                    )
                    self.logger.warning(msg)
                else:
                    info['season'] = 0
                    info['episode'] = info.pop('part')

            else:
                msg = ("Source '{source}' has 'part' and an unknow "
                       "type: '{type}'")
                msg = msg.format(
                    source=data['name'], type=info.get('type') or '(None)'
                )
                self.logger.warning(msg)

        # Reformat date as episode number for episodes if needed
        if info.get('type', None) == 'episode' and \
           'date' in info:

            # Fix season
            if not info.get('season', None):
                info['season'] = 0

            # Reformat episode number
            if not info.get('episode', None):
                info['episode'] = '{year}{month:0>2}{day:0>2}'.format(
                    year=info['date'].year,
                    month=info['date'].month,
                    day=info['date'].day)

        # Reformat language as 3let-2let code
        # Note that info also contains a country property but doesn't
        # satisfy our needs: info's country refers to the country where the
        # episode/movie was produced.
        # Example:
        # "Sherlock (US) - 1x01.mp4" vs "Sherlock (UK) - 1x01.mp4"
        # For now only the 3+2 letter code is used.
        #
        # Other sources like 'game of thrones 1x10 multi.avi' are parsed as
        # multilingual (babelfish <Language [mul]>) but throw an exception when
        # alpha2 property is accessed.

        if 'language' in info:
            try:
                info['language'] = '{}-{}'.format(
                    info['language'].alpha3,
                    info['language'].alpha2)
            except babelfish.exceptions.LanguageConvertError as e:
                msg = "Language error in '{source}': {msg}"
                msg = msg.format(source=data['name'], msg=e)
                self.logger.warning(msg)
                del info['language']

        # else:
        #     info['language'] = self.default_language_from_provider(
        #         data.provider)

        # Misc fixes. Maybe this needs its own module
        # - 12 Monkeys series
        if (info.get('type', None) == 'episode' and
                info.get('series', None) == 'Monkeys' and
                data['name'].lower().startswith('12 monkeys')):
            info['series'] = '12 Monkeys'

        entity, tags, other = self._guessit_transform_data(info)

        return entity, tags, other

    def _guessit_transform_data(self, guess_data):
        # Force limits with some introspection
        type = guess_data.pop('type')
        entity_cls_name = ''.join(x.capitalize()
                                  for x in type.split('_'))
        entity_cls = getattr(kit, entity_cls_name)
        entity_params = {}

        transfer_items(guess_data, entity_params,
                       ENTITY_FIELD_TRANSLATIONS[type])

        try:
            entity = entity_cls(**entity_params)
        except (TypeError, ValueError) as e:
            entity = None
            msg = 'Invalid parameters for entity: {params}'
            msg = msg.format(params=repr(entity_params))
            self.logger.warning(msg)

        # Process meta
        tags = {}
        transfer_items(guess_data, tags,
                       META_FIELD_TRANSLATIONS)
        tags = [kit.SourceTag(key=k, value=v)
                for (k, v) in
                tags.items()]

        return entity, tags, guess_data


class ParseCache(cache.DiskCache):
    def __init__(self, *args, **kwargs):
        basedir = (
            kwargs.pop('basedir', None) or
            utils.user_path(utils.UserPathType.CACHE, name='mediaparse')
        )
        delta = kwargs.pop('delta', None) or 60*60*24*7  # 5 days
        super().__init__(*args, basedir=basedir, delta=delta, **kwargs)

    def encode_key(self, source):
        return self.basedir / parse.quote_plus(source.name)
