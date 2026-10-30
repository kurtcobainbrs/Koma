"""Background encoding and atomic publication, independent of external programs."""
import asyncio
import math
import os
import tempfile
from pathlib import Path
from threading import Event
from uuid import uuid4
from koma.exports.encoding import QUALITY_OPTIONS, SIZE_OPTIONS
from koma.exports.video_audio import AudioInput
from koma.exports.video_encoder import encode
from koma.exports.video_frames import FrameSource


def destination_stamp(path):
    try:
        info = Path(path).stat()
        return info.st_size, info.st_mtime_ns
    except FileNotFoundError:
        return None


class VideoRunner:
    def __init__(self, logs):
        self.logs = Path(logs)
        self.running = False
        self.cancelled = Event()
        self.task = None

    def cancel(self):
        self.cancelled.set()

    async def shutdown(self):
        self.cancel()
        if self.task and self.task is not asyncio.current_task():
            await asyncio.shield(self.task)

    async def run(self, source: FrameSource, destination, fps, quality, max_size, notify, *,
                  expected_destination_stamp=Ellipsis, audio_tracks=None):
        if self.running:
            raise ValueError('Uma exportação já está em andamento.')
        self.running = True
        self.cancelled.clear()
        self.task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        def progress(event):
            if not self.cancelled.is_set():
                loop.call_soon_threadsafe(notify, event)
        worker = asyncio.create_task(asyncio.to_thread(self.write, source, destination, fps, quality,
            max_size, progress, expected_destination_stamp, audio_tracks))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            self.cancel()
            await asyncio.shield(worker)
            raise
        finally:
            self.running, self.task = False, None

    def write(self, source, destination, fps, quality, max_size, notify,
              expected_destination_stamp=Ellipsis, audio_tracks=None):
        """Entire transaction runs on a worker; only progress crosses to the UI."""
        if type(fps) not in (float, int) or not math.isfinite(fps) or not 1 <= fps <= 240:
            raise ValueError('Escolha um FPS entre 1 e 240.')
        if quality not in QUALITY_OPTIONS or max_size not in SIZE_OPTIONS:
            raise ValueError('Configurações de vídeo inválidas.')
        source.validate()
        tracks = tuple(AudioInput.parse(track) for track in (audio_tracks or ()))
        for track in tracks:
            track.validate()
        tracks = tuple(track for track in tracks if track.volume > 0)
        destination = Path(destination).expanduser().resolve()
        if destination.suffix.lower() != '.mp4' or not destination.parent.is_dir():
            raise ValueError('Escolha um destino MP4 em uma pasta existente.')
        assets = {Path(path).resolve() for path in source.assets} | {track.path.resolve() for track in tracks}
        if destination in assets:
            raise ValueError('O destino não pode substituir uma mídia de origem.')
        initial = destination_stamp(destination)
        if expected_destination_stamp is not Ellipsis and initial != expected_destination_stamp:
            raise ValueError('O destino mudou após a confirmação; o vídeo existente foi preservado.')
        stamps = {path: destination_stamp(path) for path in assets}
        if any(stamp is None for stamp in stamps.values()):
            raise ValueError('Uma mídia de origem está indisponível.')
        self.logs.mkdir(parents=True, exist_ok=True)
        log = self.logs / f'video-{uuid4().hex}.log'
        try:
            with tempfile.TemporaryDirectory(prefix='.koma-video-', dir=destination.parent) as temporary:
                output = Path(temporary) / 'video.mp4'
                if self.cancelled.is_set() or not encode(source, output, fps, quality, max_size, tracks,
                        self.cancelled.is_set, notify):
                    return None
                if self.cancelled.is_set():
                    return None
                if destination_stamp(destination) != initial:
                    raise ValueError('O destino mudou durante a exportação; o vídeo existente foi preservado.')
                if any(destination_stamp(path) != stamp for path, stamp in stamps.items()):
                    raise ValueError('Uma mídia mudou durante a exportação. Tente novamente.')
                with output.open('r+b') as handle:
                    os.fsync(handle.fileno())
                os.replace(output, destination)
            return destination
        except Exception as exc:
            # Never log project paths, frames, subtitles, audio or codec payloads.
            log.write_text(f'MP4 failure: {type(exc).__name__}; fps={fps}; frames={source.count}\n', encoding='utf-8')
            raise
