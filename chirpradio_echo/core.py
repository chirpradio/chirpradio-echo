from multiprocessing import (current_process, Manager, Lock, Pipe, Pool,
                             Process, Queue)
import optparse
import time

from .taskqlite import log, central_q, still_working, task


@task
def slicer(*args, **kw):
    log.info('slicing...')
    nested.delay()
    time.sleep(5)
    log.info('done')


@task
def nested(*args, **kw):
    log.info('nested')


def main():
    p = optparse.OptionParser(usage='%prog [options]')
    p.add_option('-s', '--qsize', type=int, default=10,
                 help='Max number of concurrent tasks. '
                      'Default: %default')
    (opt, args) = p.parse_args()
    log.info('Starting workers')
    for i in range(10):
        slicer.delay()
    central_q.work(concurrent_tasks=opt.qsize)


if __name__ == '__main__':
    main()
