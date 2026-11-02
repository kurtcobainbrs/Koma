"""At most one legacy scroll call in flight; only the most recent target is kept."""
from flet.controls.exceptions import FletException
class ScrollRequests:
    def __init__(self, strip):
        self.strip = strip
        self.pending = None
        self.running = False

    def request(self, offset):
        self.pending = (self.strip.generation, offset)
        if not self.running:
            self.running = True
            self.strip.player.view.page.run_task(self.flush)

    async def flush(self):
        try:
            while self.pending is not None:
                (generation, offset), self.pending = self.pending, None
                if generation == self.strip.generation and self.strip.player.presenting:
                    try:
                        await self.strip.scroller._invoke_method('scroll_to', {'offset': offset, 'duration': 0}, timeout=5)
                    except (TimeoutError, RuntimeError, FletException):
                        self.pending = None
        finally:
            self.running = False
