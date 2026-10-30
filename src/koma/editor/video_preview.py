"""Only the active animatic clip is decoded; a single pending seek replaces bursts."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from koma.documents.videos import VideoReader
import av

MAX_PREVIEW_LAG = .25


class VideoPreview:
    def __init__(self, player):
        self.player = player
        self.reader = VideoReader()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='koma-video')
        self.key = self.pending = self.latest = None
        self.generation = 0
        self.running = self.closed = False

    def request(self, frame, seconds):
        media = frame.active_media
        if self.closed or media is None or media.kind != 'video':
            self.clear()
            return
        key = (self.player.view.session, frame.id, media.id)
        if key != self.key:
            self.key = key
            self.generation += 1
        seconds = min(max(0, seconds), max(0, media.duration - 1e-6),
            max(0, frame.duration - 1 / self.player.view.board.fps))
        position = round(seconds * self.player.view.board.fps)
        request = (key, position, self.player.view.board.fps)
        if request == self.latest:
            return
        self.latest = request
        self.pending = (self.generation, key, seconds, self.player.view.store.videos / media.asset)
        if not self.running:
            self.running = True
            self.player.view.page.run_task(self.drain)

    def clear(self):
        if self.key is None and self.pending is None:
            return
        self.key = self.pending = self.latest = None
        self.generation += 1
        if not self.closed:
            self.executor.submit(self.reader.close)

    def decode(self, request):
        generation, key, seconds, path = request
        image = self.reader.read(path, seconds, cancelled=lambda: generation != self.generation or self.closed)
        if image is None:
            return None
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=85)
        return buffer.getvalue()

    async def drain(self):
        try:
            while self.pending is not None and not self.closed:
                request, self.pending = self.pending, None
                data = await asyncio.get_running_loop().run_in_executor(self.executor, self.decode, request)
                generation, key, seconds, _ = request
                player = self.player
                latest_seconds = self.latest[1] / self.latest[2] if self.latest else 0
                if (data is not None and generation == self.generation and key == self.key
                        and abs(seconds - latest_seconds) <= MAX_PREVIEW_LAG and player.opened
                        and not player.view.closing and player.preview.image is not None):
                    player.preview.image.src = data
                    player.view.page.update(player.preview.image)
        except (OSError, ValueError, RuntimeError, av.error.FFmpegError):
            if self.player.opened and not self.closed:
                self.player.view.notify('Não foi possível ler o vídeo. A prévia estática foi preservada.', 'warning')
        finally:
            self.running = False

    async def shutdown(self):
        if self.closed:
            return
        self.clear()
        self.closed = True
        self.executor.submit(self.reader.close)
        await asyncio.to_thread(self.executor.shutdown, wait=True)
