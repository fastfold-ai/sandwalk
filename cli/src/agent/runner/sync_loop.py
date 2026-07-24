"""SyncLoopMixin: blocking event-loop bridge and Ctrl+C/interrupt handling for AgentRunner.

Split out of ``agent/runner.py`` (package conversion) to keep files under the
project line-count limit. All symbols used here (``asyncio``, ``os``, ``select``,
``signal``, ``sys``, ``threading``) are stdlib singleton modules, so patches like
``agent.runner.asyncio.run_coroutine_threadsafe`` keep working regardless of
which file defines the calling code.
"""

from __future__ import annotations

import asyncio
import logging
import os
import select
import signal
import sys
import threading
import time
from contextlib import suppress

logger = logging.getLogger("runner")


class SyncLoopMixin:
    """Run the async query loop synchronously with graceful Ctrl+C handling."""

    def _run_coro_sync(self, coro):
        """Run async coroutine with SDK interrupt before force cancel."""
        loop = asyncio.new_event_loop()
        task = loop.create_task(coro)
        with self._active_client_lock:
            self._active_loop = loop
            self._active_task = task
        is_main_thread = threading.current_thread() is threading.main_thread()
        interrupt_deadline_at: float | None = None
        last_interrupt_at = 0.0
        sent_soft_interrupt = False
        tty_state = self._ensure_sigint_tty_mode() if is_main_thread else None
        stdin_watch_stop = threading.Event()
        stdin_watch_thread: threading.Thread | None = None
        previous_sigint_handler = None
        sigint_handler_overridden = False

        def _watch_stdin_for_ctrl_c() -> None:
            """Fallback: convert raw ^C bytes into SIGINT while query runs.

            Some terminal/input modes can deliver Ctrl+C as a byte (0x03)
            instead of raising KeyboardInterrupt. This watcher ensures we still
            trigger the normal SIGINT path in those cases.
            """
            if self._headless or os.name != "posix":
                return
            try:
                fd = sys.stdin.fileno()
            except Exception:
                return
            while not stdin_watch_stop.is_set():
                try:
                    ready, _, _ = select.select([fd], [], [], 0.15)
                except Exception:
                    return
                if fd not in ready:
                    continue
                try:
                    chunk = os.read(fd, 1)
                except Exception:
                    return
                if chunk == b"\x03":
                    with suppress(Exception):
                        os.kill(os.getpid(), signal.SIGINT)

        if not self._headless and is_main_thread:
            stdin_watch_thread = threading.Thread(
                target=_watch_stdin_for_ctrl_c,
                daemon=True,
                name="ct-stdin-ctrlc-watch",
            )
            stdin_watch_thread.start()
        try:
            if threading.current_thread() is threading.main_thread():
                with suppress(Exception):
                    previous_sigint_handler = signal.getsignal(signal.SIGINT)
                    signal.signal(signal.SIGINT, signal.default_int_handler)
                    sigint_handler_overridden = True
            asyncio.set_event_loop(loop)
            while True:
                try:
                    if interrupt_deadline_at is None:
                        return loop.run_until_complete(task)
                    remaining_s = interrupt_deadline_at - time.time()
                    if remaining_s <= 0:
                        raise TimeoutError
                    return loop.run_until_complete(
                        asyncio.wait_for(asyncio.shield(task), timeout=remaining_s)
                    )
                except KeyboardInterrupt:
                    now = time.time()
                    second_tap = (now - last_interrupt_at) < 1.0
                    last_interrupt_at = now

                    # First Ctrl+C while a foreground SDK query is active:
                    # request graceful SDK interrupt and let the stream settle.
                    if not second_tap and not sent_soft_interrupt and not task.done():
                        interrupted = loop.run_until_complete(self._interrupt_active_query())
                        if interrupted:
                            sent_soft_interrupt = True
                            interrupt_deadline_at = now + self._interrupt_drain_timeout_s
                            if not self._headless:
                                self.session.console.print(
                                    "  [dim]Interrupt requested. Press Ctrl+C again to force stop.[/dim]"
                                )
                            continue

                    self._cancel_loop_tasks(loop)
                    raise
                except TimeoutError:
                    # SDK interrupt was requested, but stream did not settle in time.
                    self._cancel_loop_tasks(loop)
                    raise KeyboardInterrupt
                except asyncio.CancelledError:
                    self._cancel_loop_tasks(loop)
                    raise KeyboardInterrupt
        finally:
            t_shutdown = time.time()
            stdin_watch_stop.set()
            if stdin_watch_thread is not None:
                stdin_watch_thread.join(timeout=0.25)
            if sigint_handler_overridden:
                with suppress(Exception):
                    signal.signal(signal.SIGINT, previous_sigint_handler)
            with self._active_client_lock:
                if self._active_loop is loop:
                    self._active_loop = None
                if self._active_task is task:
                    self._active_task = None
            self._cancel_loop_tasks(loop)
            self._restore_tty_mode(tty_state)
            asyncio.set_event_loop(None)
            with suppress(Exception):
                loop.close()
            logger.info(
                "[perf] runner loop shutdown %.2fs", time.time() - t_shutdown
            )

    def request_interrupt(self, force: bool = False) -> bool:
        """Request interrupt from another thread (interactive prompt while running)."""
        with self._active_client_lock:
            loop = self._active_loop
            task = self._active_task
            client = self._active_client

        if loop is None or not loop.is_running():
            return False

        if force:
            if task is None or task.done():
                return False
            with suppress(Exception):
                loop.call_soon_threadsafe(task.cancel)
                return True
            return False

        if client is None:
            if task is not None and not task.done():
                with suppress(Exception):
                    loop.call_soon_threadsafe(task.cancel)
                    return True
            return False

        try:
            future = asyncio.run_coroutine_threadsafe(client.interrupt(), loop)
            future.result(timeout=2.0)
            return True
        except Exception:
            logger.debug("Cross-thread interrupt request failed", exc_info=True)
            if task is not None and not task.done():
                with suppress(Exception):
                    loop.call_soon_threadsafe(task.cancel)
                    return True
            return False

    def _ensure_sigint_tty_mode(self):
        """Ensure Ctrl+C emits SIGINT while foreground query is running."""
        if os.name != "posix":
            return None
        import termios

        try:
            fd = sys.stdin.fileno()
            attrs = termios.tcgetattr(fd)
        except Exception:
            return None

        new_attrs = [x[:] if isinstance(x, list) else x for x in attrs]
        changed = False

        # Local flags: ensure ISIG enabled so VINTR produces SIGINT and
        # disable canonical mode so stdin watcher can observe control bytes
        # immediately on terminals that emit literal ^C instead of SIGINT.
        lflag = int(new_attrs[3])
        if not (lflag & termios.ISIG):
            new_attrs[3] = lflag | termios.ISIG
            changed = True
            lflag = int(new_attrs[3])
        if lflag & termios.ICANON:
            new_attrs[3] = lflag & ~termios.ICANON
            changed = True

        # Control chars: ensure VINTR maps to Ctrl+C.
        cc = list(new_attrs[6])
        vintr = cc[termios.VINTR]
        if isinstance(vintr, bytes):
            desired = b"\x03"
            if vintr != desired:
                cc[termios.VINTR] = desired
                changed = True
            if termios.VMIN < len(cc) and cc[termios.VMIN] != b"\x01":
                cc[termios.VMIN] = b"\x01"
                changed = True
            if termios.VTIME < len(cc) and cc[termios.VTIME] != b"\x00":
                cc[termios.VTIME] = b"\x00"
                changed = True
        else:
            desired = 3
            if int(vintr) != desired:
                cc[termios.VINTR] = desired
                changed = True
            if termios.VMIN < len(cc) and int(cc[termios.VMIN]) != 1:
                cc[termios.VMIN] = 1
                changed = True
            if termios.VTIME < len(cc) and int(cc[termios.VTIME]) != 0:
                cc[termios.VTIME] = 0
                changed = True
        new_attrs[6] = cc

        if changed:
            with suppress(Exception):
                termios.tcsetattr(fd, termios.TCSANOW, new_attrs)
        return (fd, attrs)

    def _restore_tty_mode(self, tty_state) -> None:
        """Restore tty mode changed by _ensure_sigint_tty_mode."""
        if not tty_state:
            return
        import termios

        fd, attrs = tty_state
        with suppress(Exception):
            termios.tcsetattr(fd, termios.TCSANOW, attrs)

    def _cancel_loop_tasks(self, loop: asyncio.AbstractEventLoop) -> None:
        """Best-effort shutdown for a loop after interruption/cancellation."""
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for pending_task in pending:
            pending_task.cancel()
        if pending:
            with suppress(Exception):
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        with suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
        with suppress(Exception):
            loop.run_until_complete(loop.shutdown_default_executor())
