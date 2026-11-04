"""Bounded PCM mixing with sample-accurate placement, trims and volume."""
from array import array
from contextlib import ExitStack
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import math
import sys
import wave
import av
from koma.documents.audio import SAMPLE_RATE, CHANNELS, validate_audio
from koma.editor.media_models import MAX_AUDIO_TRACKS
from koma.editor.models import MAX_CARDS

AUDIO_BLOCK_SAMPLES = 1024
AUDIO_BIT_RATE = 192000


@dataclass(frozen=True)
class AudioInput:
    path: Path
    start: float
    volume: float
    offset: float = 0
    duration: float | None = None

    def validate(self):
        values = (self.start, self.volume, self.offset)
        if (any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values)
                or self.volume > 2 or (self.duration is not None and
                    (type(self.duration) not in (int, float) or not math.isfinite(self.duration) or self.duration <= 0))):
            raise ValueError('Trilha de áudio de exportação inválida.')
        validate_audio(self.path)

    @classmethod
    def parse(cls, value):
        try:
            return cls(**(value | {'path': Path(value['path'])}))
        except (TypeError, KeyError) as exc:
            raise ValueError('Trilha de áudio de exportação inválida.') from exc


class AudioMixer:
    def __init__(self, tracks, samples):
        if len(tracks) > MAX_AUDIO_TRACKS * MAX_CARDS or len({track.path for track in tracks}) > MAX_AUDIO_TRACKS:
            raise ValueError('Há trilhas demais para exportar.')
        self.tracks, self.samples = tracks, samples

    def blocks(self, cancelled):
        with ExitStack() as resources:
            tracks = []
            sources = {}
            for track in self.tracks:
                if track.volume == 0:
                    continue
                source = sources.get(track.path)
                if source is None:
                    source = sources[track.path] = resources.enter_context(wave.open(str(track.path), 'rb'))
                offset = min(source.getnframes(), round(track.offset * SAMPLE_RATE))
                length = source.getnframes() - offset
                if track.duration is not None:
                    length = min(length, round(track.duration * SAMPLE_RATE))
                tracks.append((track, source, round(track.start * SAMPLE_RATE), offset, length))
            for position in range(0, self.samples, AUDIO_BLOCK_SAMPLES):
                if cancelled():
                    return
                count = min(AUDIO_BLOCK_SAMPLES, self.samples - position)
                planes = [array('f', [0]) * count for _ in range(CHANNELS)]
                for track, source, start, offset, length in tracks:
                    first, end = max(position, start), min(position + count, start + length)
                    if first >= end:
                        continue
                    source.setpos(offset + first - start)
                    data = array('h')
                    data.frombytes(source.readframes(end - first))
                    if sys.byteorder != 'little':
                        data.byteswap()
                    if len(data) != (end - first) * CHANNELS:
                        raise ValueError('Uma trilha de áudio foi truncada durante a exportação.')
                    gain = track.volume / 32768
                    for index in range(end - first):
                        target = first - position + index
                        for channel in range(CHANNELS):
                            planes[channel][target] += data[index * CHANNELS + channel] * gain
                frame = av.AudioFrame(format='fltp', layout='stereo', samples=count)
                frame.sample_rate, frame.time_base, frame.pts = SAMPLE_RATE, Fraction(1, SAMPLE_RATE), position
                for output, samples in zip(frame.planes, planes):
                    output.update(array('f', (max(-1, min(1, value)) for value in samples)).tobytes())
                yield frame
