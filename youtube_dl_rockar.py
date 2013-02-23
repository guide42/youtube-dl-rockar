#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import urllib.request
import html.parser

from youtube_dl import FileDownloader
from youtube_dl.InfoExtractors import YoutubeSearchIE, YoutubeIE
from youtube_dl.PostProcessor import FFmpegExtractAudioPP

__authors__ = ('Juan M Martínez')
__license__ = 'Public Domain'
__version__ = '2013-02-23'

BASE_URL = 'http://www.rock.com.ar'
FILE_FORMAT = '%02d - %s'


class HTMLParser(html.parser.HTMLParser):
    def __init__(self, url=None):
        html.parser.HTMLParser.__init__(self)

        self._url = url
        self._html = None
        self._request = None

    @property
    def pattern(self):
        raise NotImplementedError

    @property
    def url(self):
        if self._url is None:
            self._url = self.pattern
        return self._url

    @property
    def html(self):
        if self._html is None:
            try:
                self._request = urllib.request.urlopen(BASE_URL + self.url)
                self._html = self._request.read().decode('latin-1')
            except urllib.error.HTTPError:
                self._request = False
                self._html = ''
        return self._html

    @property
    def found(self):
        return self.html is not ''

    def parse(self):
        self.feed(self.html)

class Artist(HTMLParser):
    PATTERN = '/artistas/%s.shtml'

    def __init__(self, name, url=None):
        HTMLParser.__init__(self, url)

        self.name = name
        self.albums = []

        self._parse_albums = False
        self._parse_albums_data = []

    @property
    def pattern(self):
        return self.PATTERN % self.name.lower().replace(' ', '-')

    def parse(self):
        HTMLParser.parse(self)

        for albumattrs in self._parse_albums_data:
            album = Album(albumattrs[1], albumattrs[2], albumattrs[0])
            self.albums.append(album)

    def handle_data(self, data):
        data = " ".join(data.split())
        if not data or data == '\\n':
            return
        if data.startswith('Discograf'):
            self._parse_albums = -1
        elif self._parse_albums is not False:
            self._parse_albums_data[self._parse_albums].append(data)

    def handle_starttag(self, tag, attrs):
        if self._parse_albums is not False:
            if tag == 'b':
                self._parse_albums = False
            elif tag == 'a':
                dictattrs = {}
                dictattrs.update(attrs)
                self._parse_albums += 1
                self._parse_albums_data.append([dictattrs['href']])

    def get_album(self, albumname):
        for album in self.albums:
            if album.name == albumname:
                return album

    def __str__(self):
        return '<Artist %s>' % self.name


class Album(HTMLParser):
    PATTERN = '/discos/%s.shtml'

    def __init__(self, name, year, url=None):
        HTMLParser.__init__(self, url)

        self.name = name
        self.year = year
        self.songs = []

        self._parse_songs = False

    def parse(self):
        HTMLParser.parse(self)

    def handle_data(self, data):
        data = " ".join(data.split())
        data = data.strip('\\n')
        if not data or data == '\\n':
            return
        if data.startswith('La lista de temas'):
            self._parse_songs = True
        elif self._parse_songs:
            self.songs.append(data)

    def handle_endtag(self, tag):
        if self._parse_songs and tag == 'ol':
            self._parse_songs = False

    def __str__(self):
        return '<Album %s>' % self.name


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('artista')
    parser.add_argument('disco', nargs='?')

    return parser.parse_args()


def main():
    ns = parse_args()

    fd = FileDownloader({
        'quiet': True,
        'outtmpl': '%(title).%(ext)s',
    })

    fd.add_info_extractor(YoutubeSearchIE())
    fd.add_info_extractor(YoutubeIE())

    fd.add_post_processor(FFmpegExtractAudioPP())

    artist = Artist(ns.artista)

    if not artist.found:
        print('ERROR: %s no existe' % ns.artista)
        return 1

    print('Obteniendo información de %s...' % ns.artista)
    artist.parse()

    if not os.path.exists(ns.artista):
        os.mkdir(ns.artista)

    if ns.disco is None:
        albums = artist.albums
    else:
        album = artist.get_album(ns.disco)

        if album is None or not album.found:
            print('ERROR: %s no tiene un disco %s' % (ns.artista, ns.disco))
            return 1

        albums = [album]

    for album in albums:
        if not album.found:
            print('Ignorando %s' % album.name)
            continue

        if ns.disco is None:
            print('%s:' % album.name)
        else:
            print('Obteniendo lista de temas...')

        album.parse()

        for song in album.songs:
            fpath = os.path.join(ns.artista, album.name)
            fname = FILE_FORMAT % (album.songs.index(song) + 1, song)

            print(' %s' % fname)

            if not os.path.exists(fpath):
                os.mkdir(fpath)

            fd.params['outtmpl'] = os.path.join(fpath, fname + '.%(ext)s')
            fd.download(['ytsearch:%s %s' % (ns.artista, song)])

    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit('\nERROR: Lo interrupiste vos')