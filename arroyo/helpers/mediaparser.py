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


import babelfish
import guessit
from appkit.blocks import cache
from appkit import utils, Null


import arroyo
import arroyo.models


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
    ('edition', 'media.edition'),
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


class InvalidEntityTypeError(Exception):
    pass


class InvalidEntityArgumentsError(Exception):
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
    """
    This parser is a complex piece of code. I had to re-read it so many times
    to understand my own code.
    So...

    The main function is `MediaParse.parse` whichs takes a `Source` object and
    some metatags (a simple str->str dict). Note: maybe extrainfo will be a better name for metatags)

    If source.type is 'other' our work is done, it's kinda a stopper.

    For convenience I break parsing into some 'backends' based on source.type.
    Those backends take the same params as `MediaParse.parse` and should
    return:
    - An Entity
    - A dict with recognized metatags
    - A dict with unrecognized metatags

    Backend examples:
    - _guessit_parse for episodes and movies using guessit
    - _ebook_parse for ebooks
    """

    def __init__(self, logger=None):
        # app.signals.connect('sources-added-batch', self._on_source_batch)
        # app.signals.connect('sources-updated-batch', self._on_source_batch)
        self.logger = logger or Null
        self.cache = ParseCache()

    def parse_name(self, name, hints={}):
        type = hints.get('type')

        # Skip/Ignore detection
        if type in ['source', 'other']:
            entity_type_name, entity_params, metadata, other = None, {}, {}, {}

        elif type in ['episode', 'movie', None]:
            entity_type_name, entity_params, metadata, other = self._guessit_parse(name, type, metatags={})

        elif type in ['ebook']:
            # Book: parse by _book_parse
            ebook_data, meta, other = self._ebook_parse(name, metatags={})

        else:
            raise NotImplementedError()

        # Warn about leftovers
        for (key, value) in other.items():
            msg = "{name} has a non identified property {key}={value}"
            msg = msg.format(name=name, key=key, value=value)
            self.logger.warning(msg)

        return entity_type_name, entity_params, metadata, other

    def parse(self, source, metadata=None):
        hints = metadata.copy() if metadata else {}
        hints['type'] = source.type

        entity_type_name, entity_params, metadata, other = self.parse_name(source.name, hints)
        entity_model_name = ''.join([x.capitalize() for x in entity_type_name.split('-')])

        try:
            entity_model_cls = getattr(arroyo.models, entity_model_name)
        except AttributeError as e:
            err = "Invalid entity type '{entity_type_name}'"
            err = err.format(entity_type_name=entity_type_name)
            raise InvalidEntityArgumentsError(err) from e

        try:
            entity = entity_model_cls(**entity_params)
        except (TypeError, ValueError) as e:
            entity = None
            err = "Invalid parameters for entity '{entity_model_cls}': {params}"
            err = err.format(entity_model_cls=entity_model_cls,
                             params=repr(entity_params))
            raise InvalidEntityArgumentsError(err) from e

        # Warn about leftovers
        for (key, value) in other.items():
            msg = "{source} has a non identified property {key}={value}"
            msg = msg.format(source=source.name, key=key, value=value)
            self.logger.warning(msg)

        return entity, metadata

    def _ebook_parse(self, name, metadata):
        """
        """
        try:
            author = metadata.pop('ebook.author')
            title = metadata.pop('ebook.title')
        except KeyError:
            return None, {}, {}, {}

        return 'ebook', {'author': author, 'title': title}, metadata, {}

    def _guessit_parse(self, name, type, metatags):
        """
        guessit backend for episodes and movies

        This method extracts information from source using guessit but before
        converting it into models it needs to be cleaned and transformed.
        This is a bunch of hacks or fixes, yes.

        Once guessit info is ready we use another function to convert that
        information into usable models.
        """

        # Step 1:
        # Release teams ofter are shadowed by 'distributors' (eztv, rartv,
        # etc...) because guessit doesn't do a perfect job.
        # In order to fix this we made a "preprocessing" to extract (and
        # remove) known distributors from source's name and add distribution
        # field into info after processing source's name with guessit.
        distributors = set()
        for dist in KNOWN_DISTRIBUTORS:
            tag = '[' + dist + ']'
            idx = name.lower().find(tag)
            if idx == -1:
                continue

            name = (name[:idx] + name[idx+len(tag):]).strip()
            distributors.add(dist)

        # Step 2:
        # Parse name with guessit using its type as a type hint
        info = guessit.guessit(name, options={'type': type})

        # Step 3:
        # Re-introduce distributors from step 1
        if distributors:
            info['release_distributors'] = list(distributors)

        # Step 4:
        # Remove empty values
        info = {k: v for (k, v) in info.items() if v is not None}

        # Step 5:
        # Drop multiple languages and multiple episode numbers
        # FIXME: Don't drop, save
        for k in ['language', 'part']:
            if isinstance(info.get(k), list):
                msg = 'Drop multiple instances of {key} in {source}'
                msg = msg.format(source=data['name'], key=k)
                self.logger.warning(msg)
                info[k] = info[k][0]

        # Step 6a:
        # Integrate 'part' as episode in season 0
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

        # Step 6b:
        # Integrade N-of-N episodes
        if 'episode_count' in info:
            info['season'] = info.get('season', 1)

        # Step 7:
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

        # Step 8:
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
                if info['language'] == 'und':
                    errmsg = "Undefined language"
                    raise babelfish.exceptions.LanguageConvertError(errmsg)

                info['language'] = '{}-{}'.format(
                    info['language'].alpha3,
                    info['language'].alpha2)

            except (babelfish.exceptions.LanguageConvertError) as e:
                msg = "Language error in '{name}': {msg}"
                msg = msg.format(name=name, msg=e)
                self.logger.warning(msg)
                del info['language']

        # Step 9:
        # Misc fixes. Maybe this needs its own module
        # - 12 Monkeys series
        if (info.get('type', None) == 'episode' and
                info.get('series', None) == 'Monkeys' and
                data['name'].lower().startswith('12 monkeys')):
            info['series'] = '12 Monkeys'

        # After all this fixes info is ready to be transformed into modelable
        # data
        return self._guessit_transform_data(info)

    def _guessit_transform_data(self, guess_data):
        """
        Transform guessit data into arroyo standards
        """
        try:
            entity_type_name = guess_data.pop('type')
        except KeyError as e:
            err = "Detected entity type is empty"
            raise InvalidEntityTypeError(err) from e

        # Extract entity parameters using the definitions from the top of
        # this module
        entity_params = {}
        transfer_items(guess_data, entity_params,
                       ENTITY_FIELD_TRANSLATIONS[entity_type_name])

        # Transfer known metadata from guessit data
        metadata = {}
        transfer_items(guess_data, metadata,
                       META_FIELD_TRANSLATIONS)

        return entity_type_name, entity_params, metadata, guess_data


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
