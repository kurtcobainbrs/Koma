"""Validated local video imports and one bounded, reusable frame decoder."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import math
import shutil
import av

from koma.editor.node_media import NodeMedia, VIDEO_EXTENSIONS, MAX_VIDEO_BYTES, MAX_VIDEO_DURATION, MAX_VIDEO_PIXELS
from koma.documents.images import import_image_bytes

VIDEO_PREVIEW_SIDE = 1280
VIDEO_POSTER_SIDE = 2560
SEQUENTIAL_SEEK_WINDOW = 1.0
DECODE_THREADS = 2


def open_video(path):
    return av.open(str(path), options={'protocol_whitelist': 'file,pipe'})


def frame_image(frame, maximum_side):
    scale = min(1, maximum_side / max(frame.width, frame.height))
    image = frame.to_image(width=max(1, round(frame.width * scale)), height=max(1, round(frame.height * scale)))
    rotation = round(frame.rotation) % 360
    return image.rotate(rotation, expand=True) if rotation else image


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration: float


def inspect_video(path, *, decode=True):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_VIDEO_BYTES:
        raise ValueError('Escolha um vídeo de até 512 MB.')
    try:
        with open_video(path) as container:
            if not container.streams.video:
                raise ValueError('O arquivo não contém vídeo.')
            stream = container.streams.video[0]
            stream.codec_context.thread_count = DECODE_THREADS
            width, height = stream.codec_context.width, stream.codec_context.height
            duration = float(stream.duration * stream.time_base) if stream.duration is not None else (
                container.duration / av.time_base if container.duration is not None else 0)
            if (width <= 0 or height <= 0 or width * height > MAX_VIDEO_PIXELS
                    or not math.isfinite(duration) or not 0 < duration <= MAX_VIDEO_DURATION):
                raise ValueError('Use um vídeo válido de até uma hora e 40 megapixels.')
            if not decode:
                return VideoInfo(width, height, duration), None
            first = next(container.decode(stream), None)
            if first is None or first.time is None:
                raise ValueError('Não foi possível ler os frames do vídeo.')
            poster = frame_image(first, VIDEO_POSTER_SIDE)
            if round(first.rotation) % 180:
                width, height = height, width
            return VideoInfo(width, height, duration), poster
    except av.error.FFmpegError as exc:
        raise ValueError('Vídeo inválido ou formato não suportado.') from exc


def import_video(source, store):
    source = Path(source)
    suffix = source.suffix.lower().lstrip('.')
    if suffix not in VIDEO_EXTENSIONS:
        raise ValueError('Escolha um vídeo MP4, MOV, MKV, WebM, AVI ou M4V.')
    store.videos.mkdir(parents=True, exist_ok=True)
    target = store.videos / f'{uuid4().hex}.{suffix}'
    poster_name = None
    try:
        if not source.is_file() or not 0 < source.stat().st_size <= MAX_VIDEO_BYTES:
            raise ValueError('Escolha um vídeo de até 512 MB.')
        shutil.copyfile(source, target)
        info, poster = inspect_video(target)
        buffer = BytesIO()
        poster.save(buffer, format='PNG')
        poster_name, data = import_image_bytes(buffer.getvalue(), store)
        item = NodeMedia(kind='video', asset=target.name, poster=poster_name, label=source.name[:200],
            width=info.width, height=info.height, duration=info.duration)
        item.validate()
        return item, data
    except Exception:
        target.unlink(missing_ok=True)
        if poster_name:
            (store.images / poster_name).unlink(missing_ok=True)
            (store.thumbnails / poster_name).unlink(missing_ok=True)
        raise


class VideoReader:
    """One active clip; forward playback reuses decoding, seeking stays bounded."""
    def __init__(self):
        self.path = self.container = self.stream = self.decoder = None
        self.current = self.buffered = None
        self.timestamp = 0.0
        self.duration = 0.0

    def close(self):
        if self.container is not None:
            self.container.close()
        self.path = self.container = self.stream = self.decoder = None
        self.current = self.buffered = None

    def read(self, path, seconds, *, maximum_side=VIDEO_PREVIEW_SIDE, cancelled=lambda: False):
        path = Path(path)
        if path != self.path:
            self.close()
            self.container = open_video(path)
            self.stream = self.container.streams.video[0]
            self.stream.codec_context.thread_count = DECODE_THREADS
            self.path = path
            self.duration = float(self.stream.duration * self.stream.time_base) if self.stream.duration is not None else (
                self.container.duration / av.time_base)
            self.decoder = iter(self.container.decode(self.stream))
        seconds = min(max(0, seconds), max(0, self.duration - 1e-6))
        if self.current is not None and (seconds < self.timestamp or seconds - self.timestamp > SEQUENTIAL_SEEK_WINDOW):
            offset = int(seconds / self.stream.time_base) + (self.stream.start_time or 0)
            self.container.seek(offset, stream=self.stream, backward=True)
            self.decoder = iter(self.container.decode(self.stream))
            self.current = self.buffered = None
        start = float((self.stream.start_time or 0) * self.stream.time_base)
        while not cancelled():
            if self.buffered is None:
                self.buffered = next(self.decoder, None)
            if self.buffered is None:
                break
            timestamp = max(0, float(self.buffered.time or 0) - start)
            if self.current is not None and timestamp > seconds + 1e-8:
                break
            self.current, self.buffered = self.buffered, None
            self.timestamp = timestamp
        if cancelled() or self.current is None:
            return None
        return frame_image(self.current, maximum_side)
