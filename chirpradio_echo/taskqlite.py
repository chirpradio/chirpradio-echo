from threading import current_thread, Lock, Thread
import time
import traceback

active_tasks = {}
task_queue = []
lock = Lock()
messages = {'shutdown': False}


class Log(object):

    def info(self, msg):
        with lock:
            print '[%s] %s' % (hex(current_thread().ident), msg)

log = Log()


class Watcher(object):
    """
    Example of a watcher class.

    You can implement these methods and pass your class to
    CentralQueue.work().
    """

    def active_task_count(self, count):
        pass

    def pending_task_count(self, count):
        pass


class CentralQueue(object):
    """
    A central queue of background tasks.

    Any time a process wants to fire a task in the background it
    communicates it to the central queue. This queue manages the tasks.
    """
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
        with lock:
            task_queue.append((fn_id, args, kw))

    def work(self, num_workers=4, loop=None,
             max_worker_tasks=1000, pulse=4.0,
             WorkerProc=Thread, WatcherClass=Watcher):
        workers = []
        watch = WatcherClass()

        if not loop:
            # Loop forever.
            def loop():
                while True: yield

        def start_worker():
            p = WorkerProc(target=do_work, args=tuple(),
                           kwargs=dict(max_tasks=max_worker_tasks))
            p.start()
            workers.append(p)

        def heartbeat():
            for i in range(len(workers)):
                w = workers[i]
                if not w.is_alive():
                    workers.pop(i)
                    log.info('Restarting a dead worker')
                    start_worker()
            watch.active_task_count(sum(active_tasks.values()))
            watch.pending_task_count(len(task_queue))

        for i in range(num_workers):
            start_worker()

        try:
            for n in loop():
                time.sleep(pulse)
                heartbeat()
        except KeyboardInterrupt:
            pass

        log.info('Shutting down workers')
        with lock:
            messages['shutdown'] = True
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
    with lock:
        active_tasks.setdefault(fn_id, 0)
        active_tasks[fn_id] += 1
    fn = cq.get_task(fn_id)
    try:
        fn(*args, **kw)
    finally:
        with lock:
            active_tasks[fn_id] -= 1


def do_work(max_tasks=1000, dispatch=dispatch):
    log.info('Starting work')
    for i in range(max_tasks):
        if messages['shutdown']:
            return
        try:
            with lock:
                task = task_queue.pop(0)
        except IndexError:
            time.sleep(2)
            continue
        fn_id, args, kw = task
        try:
            dispatch(fn_id, *args, **kw)
        except:
            log.info('Exception in %s' % fn_id)
            with lock:
                traceback.print_exc()


@task
def ping():
    log.info('ping')
    pong.delay()
    time.sleep(5)


@task
def pong():
    log.info('pong')
    ping.delay()
    time.sleep(6)
