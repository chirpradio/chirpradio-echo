from contextlib import contextmanager
from multiprocessing import (current_process, Manager, Lock, Pipe, Pool,
                             Process, Queue)
import Queue as _Queue
import time

mgr = Manager()
queue = mgr.Queue(maxsize=0)
active_jobs = mgr.dict()
queue_timeout = 10


_lock = mgr.Lock()
@contextmanager
def lock():
    _lock.acquire()
    try:
        yield
    finally:
        _lock.release()


_sema = None
def set_task_sema(set_value):
    global _sema
    _sema = mgr.BoundedSemaphore(value=set_value)


@contextmanager
def task_sema():
    _sema.acquire()
    try:
        yield
    finally:
        _sema.release()


class Log(object):

    def info(self, msg):
        proc = current_process()
        with lock():
            print '[p:%s] %s' % (proc.pid, msg)

log = Log()


class ManagedQueue(object):
    msg_types = {'apply_async': 1}
    registry = {}
    _ids = {'count': 0}

    def register(self, fn):
        self._ids['count'] += 1
        id = '%s-%s' % (fn.__name__, self._ids['count'])
        self.registry[id] = fn
        return id

    def apply_async(self, fn_id, args, kw):
        return queue.put([self.msg_types['apply_async'],
                          fn_id, args, kw])

    def work(self, concurrent_tasks=4):
        set_task_sema(concurrent_tasks)
        while still_working():
            try:
                msg = queue.get(False, queue_timeout)
            except _Queue.Empty:
                continue

            typ = msg.pop(0)
            if typ not in self.msg_types.values():
                raise ValueError('Unknown msg type: %s' % typ)
            if typ == self.msg_types['apply_async']:
                self.unpack_apply_async(msg)
            else:
                raise NotImplementedError('No handler yet for type %r' % typ)
            time.sleep(0.1)

    def unpack_apply_async(self, msg):
        # Unpack a message that looks like this:
        # [fn_id, args, kw]
        fn_id = msg.pop(0)
        args = msg.pop(0)
        kw = msg.pop(0)

        # Add magic arg for dispatch.
        args = list(args)
        args.insert(0, fn_id)

        p = Process(target=dispatch, args=args, kwargs=kw)
        p.start()

managed_q = ManagedQueue()


class Task(object):

    def __init__(self, id):
        self.id = id

    def delay(self, *args, **kw):
        managed_q.apply_async(self.id, args, kw)


def task(fn):
    id = managed_q.register(fn)
    return Task(id)


def dispatch(fn_id, *args, **kw):
    with task_sema():
        with lock():
            active_jobs.setdefault(fn_id, 0)
            active_jobs[fn_id] += 1
        fn = managed_q.registry[fn_id]
        try:
            fn(*args, **kw)
        finally:
            with lock():
                active_jobs[fn_id] -= 1


def still_working():
    if len(active_jobs) == 0:
        # No jobs have started yet.
        return True
    return any(count > 0 for count in active_jobs.values())
