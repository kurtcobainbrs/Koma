"""Dados imutáveis das trilhas e marcadores; independentes de áudio e interface."""

from dataclasses import dataclass, field
import math
import re
from uuid import uuid4

MAX_AUDIO_TRACKS = 32
MAX_MARKERS = 2000
MAX_AUDIO_SECONDS = 3600
MAX_AUDIO_VOLUME = 2
MARKER_PREFIX = 'M'


def next_marker_title(markers):
    """Continue the numbered names in this scene, including renamed entries."""
    numbers = [len(markers)]
    for marker in markers:
        match = re.fullmatch(rf'{re.escape(MARKER_PREFIX)}([0-9]+)', marker.title)
        if match:
            numbers.append(int(match[1]))
    return f'{MARKER_PREFIX}{max(numbers) + 1}'


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{32}', value) is not None


def finite_range(value, minimum, maximum):
    return type(value) in (float, int) and math.isfinite(value) and minimum <= value <= maximum


@dataclass(frozen=True)
class AudioTrack:
    id: str = field(default_factory=lambda: uuid4().hex)
    asset: str = ''
    title: str = ''
    duration: float = 0
    start: float = 0
    scene_id: str = ''
    muted: bool = False
    volume: float = 1

    def validate(self, scenes, maximum_time):
        if not valid_id(self.id) or not isinstance(self.asset, str) or not re.fullmatch(r'[a-f0-9]{32}\.wav', self.asset):
            raise ValueError('Identificador ou arquivo de áudio inválido.')
        if not isinstance(self.title, str) or len(self.title) > 200:
            raise ValueError('Nome de áudio inválido.')
        if not finite_range(self.duration, 1 / 48000, MAX_AUDIO_SECONDS) or not finite_range(self.start, 0, maximum_time):
            raise ValueError('Duração ou posição da trilha de áudio inválida.')
        if not isinstance(self.scene_id, str) or (self.scene_id and self.scene_id not in scenes):
            raise ValueError('Cena da trilha de áudio indisponível.')
        if type(self.muted) is not bool or not finite_range(self.volume, 0, MAX_AUDIO_VOLUME):
            raise ValueError('Volume ou estado da trilha de áudio inválido.')


@dataclass(frozen=True)
class TimelineMarker:
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = f'{MARKER_PREFIX}1'
    position: float = 0
    scene_id: str = ''

    def validate(self, scenes, maximum_time):
        if not valid_id(self.id) or not isinstance(self.title, str) or not self.title.strip() or len(self.title) > 200:
            raise ValueError('Nome ou identificador de marcador inválido.')
        if (not isinstance(self.scene_id, str) or not finite_range(self.position, 0, maximum_time)
                or (self.scene_id and self.scene_id not in scenes)):
            raise ValueError('Posição ou cena do marcador inválida.')
