"""Bounded keyboard focus requests shared by editor surfaces."""
import asyncio
import logging
import flet as ft

FOCUS_TIMEOUT_SECONDS = 5
logger = logging.getLogger(__name__)


class FocusListener(ft.KeyboardListener):
    async def focus(self):
        # Flet 1.0.5's public focus method has no timeout parameter. Supplying
        # it here also lets the transport clean up expired native method waits.
        await self._invoke_method('focus', timeout=FOCUS_TIMEOUT_SECONDS)


class FocusRequests:
    def __init__(self, page):
        self.page = page
        self.connected = self.enabled = True
        self.task = self.token = self.target = None
        self.pending = None

    def request(self, target, eligible):
        if not self.connected or not self.enabled or not eligible():
            return
        if self.token is not None and self.target is target:
            return
        self.token, self.target = object(), target
        self.pending = (self.token, target, eligible)
        if self.task is None:
            self.task = self.page.run_task(self.flush)

    async def flush(self):
        try:
            while self.pending is not None and self.connected and self.enabled:
                token, target, eligible = self.pending
                self.pending = None
                try:
                    if token is self.token and eligible():
                        await target.focus()
                except TimeoutError:
                    logger.warning('O cliente não confirmou o foco do teclado no prazo.')
                except RuntimeError as exc:
                    # Flet resolves calls with this error on session closure,
                    # sometimes before the page's disconnect event runs.
                    if str(exc) == 'Session closed':
                        self.connected = False
                        self.cancel()
                    elif self.connected and self.enabled and eligible():
                        raise
                finally:
                    if token is self.token:
                        self.token = self.target = None
        except asyncio.CancelledError:
            return
        finally:
            self.task = None

    def cancel(self):
        # Invalidate queued requests. Let the single in-flight native call
        # finish within its deadline: cancelling Flet's coroutine directly
        # leaves its transport callback registered until session closure.
        self.token = self.target = self.pending = None

    def suspend(self):
        self.enabled = False
        self.cancel()

    def resume(self):
        self.enabled = True

    def disconnect(self):
        self.connected = False
        self.cancel()

    def reconnect(self):
        self.connected = True
