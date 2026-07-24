"""
Thread-safe bot runner and stats refresher.
"""

import threading
import time
from collections import deque
from datetime import datetime
from utils.constants import STATS_REFRESH_INTERVAL


class BotRunner:
    """Manages bot execution in a background thread with thread-safe state."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._stop_requested = False
        self._log_lines = deque(maxlen=200)
        self._results = None
        self._error = None
        self._progress = {"completed": 0, "total": 0}
        self._start_time = None

    @property
    def running(self):
        with self._lock:
            return self._running

    @property
    def stop_requested(self):
        with self._lock:
            return self._stop_requested

    def start(self, bot_func, *args, **kwargs):
        """Start bot in background thread."""
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stop_requested = False
            self._log_lines = deque(maxlen=200)
            self._results = None
            self._error = None
            self._progress = {"completed": 0, "total": 0}
            self._start_time = time.time()

        def run():
            try:
                kwargs['stop_check'] = lambda: self.stop_requested
                def log_callback(line):
                    with self._lock:
                        self._log_lines.append(line)
                kwargs['log_callback'] = log_callback
                def progress_callback(completed, total):
                    with self._lock:
                        self._progress = {"completed": completed, "total": total}
                kwargs['progress_callback'] = progress_callback
                results = bot_func(*args, **kwargs)
                with self._lock:
                    self._results = results
            except Exception as e:
                with self._lock:
                    self._error = str(e)
            finally:
                with self._lock:
                    self._running = False

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """Request bot to stop."""
        with self._lock:
            self._stop_requested = True

    def get_logs(self):
        """Get current log lines (thread-safe)."""
        with self._lock:
            return list(self._log_lines)

    def get_progress(self):
        """Get current progress (thread-safe)."""
        with self._lock:
            return self._progress.copy()

    def get_elapsed_seconds(self):
        """Get elapsed seconds since bot started."""
        with self._lock:
            if self._start_time is None:
                return 0
            return time.time() - self._start_time

    def get_results(self):
        """Get bot results (thread-safe)."""
        with self._lock:
            return self._results

    def get_error(self):
        """Get error message (thread-safe)."""
        with self._lock:
            return self._error

    def clear(self):
        """Clear all state."""
        with self._lock:
            self._running = False
            self._stop_requested = False
            self._log_lines = deque(maxlen=200)
            self._results = None
            self._error = None


class StatsRefresher:
    """Polls Bluesky in the background to keep dashboard stats fresh."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()
        self._last_updated = None
        self._auth_expired = False
        self._pending_stats = None

    @property
    def last_updated(self):
        with self._lock:
            return self._last_updated

    @property
    def auth_expired(self):
        with self._lock:
            return self._auth_expired

    def consume_pending_stats(self):
        """Main thread calls this to pick up fresh stats. Returns None if nothing pending."""
        with self._lock:
            stats = self._pending_stats
            self._pending_stats = None
            return stats

    def start(self, handle, client, get_stats_func):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._auth_expired = False

        def run():
            while not self._stop.is_set():
                self._stop.wait(STATS_REFRESH_INTERVAL)
                if self._stop.is_set():
                    break
                try:
                    stats = get_stats_func(handle, client)
                    with self._lock:
                        self._pending_stats = stats
                        self._last_updated = datetime.now()
                except Exception as e:
                    err = str(e).lower()
                    if "auth" in err or "invalid" in err or "expired" in err or "unauthorized" in err:
                        with self._lock:
                            self._auth_expired = True
                        break

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()


def any_bot_running():
    """Check if any bot is currently running."""
    import streamlit as st
    return (st.session_state.like_runner.running or
            st.session_state.follow_runner.running or
            st.session_state.unfollow_runner.running)


def get_running_bot_name():
    """Get the name of the currently running bot."""
    import streamlit as st
    if st.session_state.like_runner.running:
        return "LIKE"
    elif st.session_state.follow_runner.running:
        return "FOLLOW"
    elif st.session_state.unfollow_runner.running:
        return "UNFOLLOW"
    return None
