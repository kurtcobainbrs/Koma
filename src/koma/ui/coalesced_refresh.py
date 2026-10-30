"""Collapse bursts of layout notifications into one bounded UI refresh."""
import asyncio
from koma.ui.design import DRAG_INTERVAL_MS


class CoalescedRefresh:
    def __init__(self, page, callback, *, interval=DRAG_INTERVAL_MS):
        self.page, self.callback, self.interval = page, callback, interval
        self.token = self.task = None

    def request(self):
        if self.token is None:
            self.token = object()
            self.task = self.page.run_task(self.flush, self.token)

    async def flush(self, token):
        try:
            await asyncio.sleep(self.interval / 1000)
        except asyncio.CancelledError:
            return
        if token is not self.token:
            return
        self.token = self.task = None
        self.callback()

    def cancel(self):
        task = self.task
        self.token = self.task = None
        if task is not None:
            task.cancel()
