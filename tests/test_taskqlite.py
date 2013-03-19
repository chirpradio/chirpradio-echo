import unittest

from mock import patch, Mock

from chirpradio_echo import taskqlite
from chirpradio_echo.taskqlite import (active_tasks, dispatch, CentralQueue,
                                       do_work, messages, task_queue, task)


class TestCase(unittest.TestCase):

    def setUp(self):
        CentralQueue._registry.clear()
        task_queue[:] = []
        active_tasks.clear()
        messages['shutdown'] = False

        self.patches = []
        self.addCleanup(self.stop_patches)

        self.time = Mock()
        p = patch.object(taskqlite, 'time', self.time)
        p.start()
        self.patches.append(p)

    def stop_patches(self):
        for p in self.patches:
            p.stop()


class TestWork(TestCase):

    def setUp(self):
        super(TestWork, self).setUp()
        self.dispatch = Mock()

    def work(self, **_kw):
        kw = dict(max_tasks=1, dispatch=self.dispatch)
        kw.update(_kw)
        return do_work(**kw)

    def test_no_jobs(self):
        self.work()
        assert not self.dispatch.called, 'No jobs should be worked on'

    def test_work(self):
        args = ['foo']
        kw = {'bar': 1}
        task_queue.append(('fn-id', args, kw))
        self.work()
        self.dispatch.assert_called_with('fn-id', *args, **kw)

    def test_more_work(self):
        task_queue.append(('one', [], {}))
        task_queue.append(('two', [], {}))
        self.work(max_tasks=2)
        self.assertEquals(self.dispatch.mock_calls[0][1][0], 'one')
        self.assertEquals(self.dispatch.mock_calls[1][1][0], 'two')

    def test_catch_exceptions(self):
        task_queue.append(('fn-id', [], {}))
        self.dispatch.side_effect = RuntimeError
        self.work()  # exception not raised

    def test_shutdown(self):
        task_queue.append(('fn-id', [], {}))
        messages['shutdown'] = True
        self.work()
        assert not self.dispatch.called, 'Worker should have shut down'


class TestDispatch(TestCase):

    def setUp(self):
        super(TestDispatch, self).setUp()
        self.cq = Mock()
        self.task = Mock()
        self.cq.get_task.return_value = self.task

    def dispatch(self, *args, **kw):
        kw['_central_q'] = self.cq
        return dispatch(*args, **kw)

    def test_call(self):
        self.dispatch('fn')
        assert self.task.called

    def test_task_count(self):
        def check():
            self.assertEqual(active_tasks['fn'], 1)
        self.task.side_effect = check
        self.dispatch('fn')
        assert self.task.called
        self.assertEqual(active_tasks['fn'], 0)

    def test_task_fail(self):
        self.task.side_effect = ValueError
        with self.assertRaises(ValueError):
            self.dispatch('fn')
        assert self.task.called
        # Count was decremented on fail.
        self.assertEqual(active_tasks['fn'], 0)


class TestTasks(TestCase):

    def setUp(self):
        super(TestTasks, self).setUp()
        self.cq = Mock()

    def task(self, fn):
        return task(fn, central_q=self.cq)

    def test_register(self):
        @self.task
        def some_task():
            pass
        self.cq.register.assert_called_with(some_task)

    def test_delay(self):
        self.cq.register.return_value = 'id'
        @self.task
        def some_task():
            pass
        args = ('foo',)
        kw = {'bar': 1}
        some_task.delay(*args, **kw)
        self.cq.run_task.assert_called_with('id', args, kw)


class TestCentralQueue(TestCase):

    def setUp(self):
        super(TestCentralQueue, self).setUp()
        self.cq = CentralQueue()

    def work(self, **_kw):
        def once():
            yield
        kw = dict(loop=once, num_workers=2, max_worker_tasks=1)
        kw.update(_kw)
        self.cq.work(**kw)

    def task(self, fn):
        return task(fn, central_q=self.cq)

    def test_register_and_get(self):
        def foo():
            pass
        fn_id = self.cq.register(foo)
        self.assertEquals(self.cq.get_task(fn_id), foo)

    def test_work(self):
        data = {'one': 0, 'two': 0}

        @self.task
        def one():
            data['one'] += 1

        @self.task
        def two():
            data['two'] += 1

        one.delay()
        two.delay()
        self.work()

        self.assertEquals(data['one'], 1)
        self.assertEquals(data['two'], 1)

    def test_rebirth(self):
        proc = Mock()
        proc.is_alive.return_value = False
        wp = Mock(return_value=proc)

        self.work(WorkerProc=wp, num_workers=1)

        assert len(proc.start.mock_calls) == 2, (
                    'Dead worker should have been restarted')

    def test_watch_pending(self):
        watch = Mock()
        wc = Mock(return_value=watch)

        task_queue.append(('one', [], {}))
        self.work(WorkerProc=Mock(), WatcherClass=wc)

        watch.pending_task_count.assert_called_with(1)

    def test_watch_active(self):
        watch = Mock()
        wc = Mock(return_value=watch)

        active_tasks['one'] = 2
        active_tasks['two'] = 1
        self.work(WorkerProc=Mock(), WatcherClass=wc)

        watch.active_task_count.assert_called_with(3)
