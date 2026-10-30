"""Streaming frame sources: immutable document values or prepared media files."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import math
from PIL import Image
from koma.documents.videos import VideoReader, inspect_video
from koma.editor.node_media import VIDEO_EXTENSIONS
from koma.editor.frame_format import FrameFormat
from koma.exports.video_export import FrameComposer


class FrameSource(Protocol):
    @property
    def size(self): ...
    @property
    def count(self): ...
    @property
    def assets(self): ...
    def validate(self): ...
    def pictures(self, size, fps, cancelled): ...


def validate_counts(items, counts):
    if not items or len(items) != len(counts) or any(type(n) is not int or n < 1 for n in counts):
        raise ValueError('Durações de vídeo inválidas.')


@dataclass(frozen=True)
class StoryboardFrames:
    frames: tuple
    store: object
    size: tuple
    counts: tuple
    include_subtitles: bool = True
    offsets: tuple = ()

    @property
    def count(self):
        return sum(self.counts)

    @property
    def assets(self):
        return tuple({(self.store.videos / frame.active_media.asset
            if frame.active_media and frame.active_media.kind == 'video'
            else self.store.images / frame.image) for frame in self.frames if frame.image})

    def validate(self):
        validate_counts(self.frames, self.counts)
        FrameFormat(*self.size).validate()
        for frame in self.frames:
            frame.validate()
        if self.offsets and (len(self.offsets) != len(self.frames) or any(
                type(value) not in (float, int) or not math.isfinite(value) or value < 0
                for value in self.offsets)):
            raise ValueError('Intervalo de mídia inválido.')

    def pictures(self, size, fps, cancelled):
        reader = VideoReader()
        try:
            for i, (frame, count) in enumerate(zip(self.frames, self.counts)):
                composer = FrameComposer(frame, size, include_subtitles=self.include_subtitles)
                video = frame.active_media and frame.active_media.kind == 'video'
                if not video:
                    if frame.image:
                        with Image.open(self.store.images / frame.image) as original:
                            picture = composer.compose(original)
                    else:
                        picture = composer.compose(None)
                for index in range(count):
                    if cancelled():
                        return
                    if video:
                        offset = self.offsets[i] if self.offsets else 0
                        seconds = min(offset + index / fps, max(0, frame.duration - 1 / fps))
                        original = reader.read(self.store.videos / frame.active_media.asset, seconds,
                            maximum_side=max(size), cancelled=cancelled)
                        if original is None:
                            return
                        picture = composer.compose(original)
                    yield picture
        finally:
            reader.close()


@dataclass(frozen=True)
class FileFrames:
    paths: tuple
    counts: tuple

    @property
    def size(self):
        first = Path(self.paths[0])
        if first.suffix.lower().lstrip('.') in VIDEO_EXTENSIONS:
            info, _ = inspect_video(first, decode=False)
            return info.width, info.height
        with Image.open(first) as image:
            return image.size

    @property
    def count(self):
        return sum(self.counts)

    @property
    def assets(self):
        return self.paths

    def validate(self):
        validate_counts(self.paths, self.counts)

    def pictures(self, size, fps, cancelled):
        reader = VideoReader()
        try:
            for path, count in zip(self.paths, self.counts):
                path = Path(path)
                video = path.suffix.lower().lstrip('.') in VIDEO_EXTENSIONS
                if not video:
                    with Image.open(path) as original:
                        picture = original.convert('RGB').resize(size, Image.Resampling.LANCZOS)
                for index in range(count):
                    if cancelled():
                        return
                    if video:
                        picture = reader.read(path, index / fps, maximum_side=max(size), cancelled=cancelled)
                        if picture is None:
                            return
                        picture = picture.convert('RGB').resize(size, Image.Resampling.LANCZOS)
                    yield picture
        finally:
            reader.close()
