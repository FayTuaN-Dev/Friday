import time

from friday.app.stall_watch import StallWatch


def test_writes_thread_stacks_once_per_stuck_request(tmp_path):
    since = [None]
    watch = StallWatch(lambda: since[0], tmp_path, limit=1.0, every=3600)
    assert watch.check() is None  # rien en attente
    since[0] = time.monotonic() - 0.5
    assert watch.check() is None  # pas encore trop long
    since[0] = time.monotonic() - 5
    report = watch.check()
    assert report is not None and "test_stall_watch.py" in report.read_text(encoding="utf-8")
    assert watch.check() is None  # la même demande n'est signalée qu'une fois
