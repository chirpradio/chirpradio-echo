from contextlib import contextmanager
from multiprocessing import current_process, Manager, Process
import time
import traceback

mgr = Manager()
queue = mgr.Queue(maxsize=0)
active_jobs = mgr.dict()
job_queue = mgr.list()


_lock = mgr.Lock()
@contextmanager
def lock():
    _lock.acquire()
    try:
        yield
    finally:
        _lock.release()


class Log(object):

    def info(self, msg):
        proc = current_process()
        with lock():
            print '[p:%s] %s' % (proc.pid, msg)

log = Log()


class CentralQueue(object):
    """
    A central queue of background tasks.

    Any time a process wants to fire a task in the background it
    communicates it to the central queue. This queue manages the tasks.
    """
    registry = {}
    _ids = {'count': 0}

    def register(self, fn):
        self._ids['count'] += 1
        id = '%s-%s' % (fn.__name__, self._ids['count'])
        self.registry[id] = fn
        return id

    def apply_async(self, fn_id, args, kw):
        # Tell the central queue (in the main process) to schedule a task.
        return queue.put([fn_id, args, kw])

    def work(self, num_workers=4, forever=True):
        log.info('Workers started: %s' % num_workers)
        workers = []

        def start_worker():
            p = Process(target=worker)
            p.start()
            workers.append(p)

        for i in range(num_workers):
            start_worker()

        while forever:
            msg = queue.get()
            # Append a job to the stack for the next worker to pick up.
            fn_id, args, kw = msg
            job_queue.append((fn_id, args, kw))

            for i in range(len(workers)):
                w = workers[i]
                if not w.is_alive():
                    workers.pop(i)
                    log.info('Restarting a dead worker')
                    start_worker()



central_q = CentralQueue()


def worker():
    while 1:
        try:
            job = job_queue.pop(0)
        except IndexError:
            time.sleep(2)
            continue
        fn_id, args, kw = job
        try:
            dispatch(fn_id, *args, **kw)
        except KeyboardInterrupt:
            raise
        except:
            log.info('Exception in %s' % fn_id)
            traceback.print_exc()


def task(fn):
    """
    Decorator that turns a function into a background task.

    The task interface is like that of celery's task queue.
    The implementation uses multiprocessing.
    """
    id = central_q.register(fn)

    def delay(*args, **kw):
        central_q.apply_async(id, args, kw)

    fn.delay = delay
    return fn


def dispatch(fn_id, *args, **kw):
    with lock():
        active_jobs.setdefault(fn_id, 0)
        active_jobs[fn_id] += 1
    fn = central_q.registry[fn_id]
    try:
        fn(*args, **kw)
    finally:
        with lock():
            active_jobs[fn_id] -= 1


def still_working():
    """
    Returns True if tasks are still running.
    """
    if len(active_jobs) == 0:
        # No jobs have started yet.
        return True
    return any(count > 0 for count in active_jobs.values())
