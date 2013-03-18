from contextlib import contextmanager
from multiprocessing import current_process, Manager, Process
import time
import traceback

mgr = Manager()
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
    # Note that these act as static variables and will be copied
    # into new processes but that's ok.
    _registry = {}
    _ids = {'count': 0}

    def register(self, fn):
        self._ids['count'] += 1
        # Here are a couple things to note:
        # - the register method is called at import time
        # - each process should have a copy of the registry
        id = '%s-%s' % (fn.__name__, self._ids['count'])
        self._registry[id] = fn
        return id

    def get_task(self, fn_id):
        return self._registry[fn_id]

    def run_task(self, fn_id, args, kw):
        job_queue.append((fn_id, args, kw))

    def work(self, num_workers=4, forever=True,
             max_worker_tasks=1000, heartbeat=4.0,
             WorkerProc=Process):
        workers = []

        def start_worker():
            p = WorkerProc(target=do_work, args=tuple(),
                           kwargs=dict(max_tasks=max_worker_tasks))
            p.start()
            workers.append(p)

        def rebirth():
            for i in range(len(workers)):
                w = workers[i]
                if not w.is_alive():
                    workers.pop(i)
                    log.info('Restarting a dead worker')
                    start_worker()

        for i in range(num_workers):
            start_worker()

        while forever:
            time.sleep(heartbeat)
            rebirth()

        if not forever:
            rebirth()
            log.info('Shutting down workers')
            for w in workers:
                w.join()



central_q = CentralQueue()


def task(fn, central_q=central_q):
    """
    Decorator that turns a function into a background task.

    The task interface is like that of celery's task queue.
    The implementation uses multiprocessing.
    """
    id = central_q.register(fn)

    def delay(*args, **kw):
        central_q.run_task(id, args, kw)

    fn.delay = delay
    return fn


def dispatch(fn_id, *args, **kw):
    cq = kw.pop('_central_q', central_q)
    with lock():
        active_jobs.setdefault(fn_id, 0)
        active_jobs[fn_id] += 1
    fn = cq.get_task(fn_id)
    try:
        fn(*args, **kw)
    finally:
        with lock():
            active_jobs[fn_id] -= 1


def do_work(max_tasks=1000, dispatch=dispatch):
    log.info('Starting work')
    for i in range(max_tasks):
        try:
            job = job_queue.pop(0)
        except IndexError:
            time.sleep(2)
            continue
        fn_id, args, kw = job
        try:
            dispatch(fn_id, *args, **kw)
        except:
            log.info('Exception in %s' % fn_id)
            traceback.print_exc()


def still_working():
    """
    Returns True if tasks are still running.
    """
    if len(active_jobs) == 0:
        # No jobs have started yet.
        return True
    return any(count > 0 for count in active_jobs.values())
