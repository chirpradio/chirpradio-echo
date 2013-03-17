import optparse
import os
import tempfile
import time
import traceback

from pyechonest import config as echonest_conf
from pyechonest import song
import requests

from .taskqlite import log, central_q, task

# Set a chunk size of roughly 908K.
# This is about 40 seconds for 128kbps, give or take.
# The mp3 stream's bitrate is not validated!
file_size = 926343
tmp_prefix = 'echoplex_'
stream_url = 'http://chirpradio.org/stream'
chirpradio_api = ('https://chirpradio.appspot.com/api/current_playlist'
                  '?src=chirpradio-echo')


@task
def listen():
    try:
        run_gc()
        res = requests.get(stream_url, stream=True, timeout=10)
        log.info('Opening %s' % stream_url)
        log.info('Writing temp files to %s/%s*.mp3' % (tempfile.gettempdir(),
                                                       tmp_prefix))

        dest = None
        bufsize = 0
        for chunk in res.iter_content(chunk_size=2048):
            if not dest:
                dest = tempfile.NamedTemporaryFile(delete=False,
                                                   prefix=tmp_prefix,
                                                   suffix='.mp3')
            dest.write(chunk)
            bufsize += len(chunk)
            if bufsize >= file_size:
                bufsize = 0
                dest.close()
                ask_chirpradio.delay(dest.name)
                dest = None
    except Exception, exc:
        traceback.print_exc()
        log.info('Caught: %s. Restarting.' % exc)
        time.sleep(3)
        listen.delay()


@task
def ask_chirpradio(filename):
    log.info('Ask chirpradio about %s' % os.path.split(filename)[1])
    try:
        # This is a best effort guess at what's currently playing.
        # The CHIRP stream is buffered and DJs are sometimes slow to
        # update the track data. YMMV.
        res = requests.get(chirpradio_api, headers={'Accept-Encoding': 'gzip'})
        track_data = res.json()['now_playing']
        log.info('%s: CHIRP says: %s: %s (%s)' % (os.path.split(filename)[1],
                                                  track_data['artist'],
                                                  track_data['track'],
                                                  track_data['release']))
        ask_echonest.delay(track_data, filename)
    except:
        os.unlink(filename)
        raise


@task
def ask_echonest(chirpradio_id, filename):
    log.info('Ask echonest about %s' % os.path.split(filename)[1])
    try:
        set_up_echonest()

        fp = song.util.codegen(filename)
        if len(fp) and "code" in fp[0]:
            result = song.identify(query_obj=fp, version="4.12")
            if len(result):
                data = {'match': {'artist_name': result[0].artist_name,
                                  'artist_id': result[0].artist_id,
                                  'title': result[0].title,
                                  'title_id': result[0].id}}
            else:
                data = {'match': None,
                        'reason': 'This track may not be in the database yet.'}
        else:
            data = {'match': None,
                    'reason': 'Could not read or decode file %s' % filename}
        log.info('%s: echonest: %s' % (os.path.split(filename)[1], data))
    finally:
        os.unlink(filename)


def run_gc():
    """
    Clean up any lingering temp files (probably from crashes)
    """
    expiry = 60 * 3
    tmp = tempfile.gettempdir()
    for fn in os.listdir(tmp):
        if not fn.startswith(tmp_prefix):
            continue
        path = os.path.join(tmp, fn)
        if os.stat(path).st_mtime < (time.time() - expiry):
            os.unlink(path)


_e_setup = False
def set_up_echonest():
    global _e_setup
    if not _e_setup:
        echonest_conf.ECHO_NEST_API_KEY = os.environ['ECHO_NEST_API_KEY']
        p = '/usr/local/bin/echoprint-codegen'
        echonest_conf.CODEGEN_BINARY_OVERRIDE = p
        _e_setup = True


@task
def foo():
    log.info('foo')
    bar.delay()
    time.sleep(5)


@task
def bar():
    log.info('bar')
    foo.delay()
    time.sleep(10)


def main():
    p = optparse.OptionParser(usage='%prog [options]')
    p.add_option('-s', '--qsize', type=int, default=4,
                 help='Max number of concurrent tasks. '
                      'Each worker gets its own process. '
                      'Default: %default')
    (opt, args) = p.parse_args()
    listen.delay()
    #foo.delay()
    central_q.work(num_workers=opt.qsize)


if __name__ == '__main__':
    main()
