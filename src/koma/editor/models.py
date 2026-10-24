"""Documento imutável; a ordem dos quadros é a ordem da apresentação e do PDF."""

import re
import math
from dataclasses import dataclass, field, replace
from uuid import uuid4
from koma.editor.node_types import node_type

MAX_CARDS = 500
TEXT_LIMIT = 20000
MAX_POSITION = 100000
SUBTITLE_LIMIT = 500


@dataclass(frozen=True)
class StoryLink:
    source: str
    target: str


@dataclass(frozen=True)
class StoryGroup:
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = 'Cena'
    members: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoryFrame:
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = ''
    image: str = ''
    action: str = ''
    audio: str = ''
    notes: str = ''
    x: float | None = None
    y: float | None = None
    duration: float = 2.0
    image_fit: str = 'cover'
    crop_x: float = 0.0
    crop_y: float = 0.0
    kind: str = 'frame'
    scene_color: str = ''
    subtitle: str = ''
    muted: bool = False

    @property
    def node_type(self):
        return node_type(self.kind)

    def validate(self):
        node_type(self.kind)
        if type(self.muted) is not bool:
            raise ValueError('Estado de mute inválido.')
        if not isinstance(self.subtitle, str) or len(self.subtitle) > SUBTITLE_LIMIT:
            raise ValueError(f'A legenda aceita até {SUBTITLE_LIMIT} caracteres.')
        if not isinstance(self.scene_color, str) or (self.scene_color and not re.fullmatch(r'#[a-fA-F0-9]{6}', self.scene_color)):
            raise ValueError('Cor de cena inválida.')
        if type(self.duration) not in (int, float) or not math.isfinite(self.duration) or not .1 <= self.duration <= 3600:
            raise ValueError('Informe uma duração entre 0,1 e 3600 segundos.')
        if self.image_fit not in ('cover', 'contain'):
            raise ValueError('Enquadramento de imagem inválido.')
        for value in (self.crop_x, self.crop_y):
            if type(value) not in (int, float) or not math.isfinite(value) or not -1 <= value <= 1:
                raise ValueError('Posição da imagem inválida.')
        if not isinstance(self.id, str) or not re.fullmatch(r'[a-f0-9]{32}', self.id):
            raise ValueError('Identificador de quadro inválido.')
        for key in ('title', 'image', 'action', 'audio', 'notes'):
            value = getattr(self, key)
            if not isinstance(value, str) or len(value) > TEXT_LIMIT:
                raise ValueError('Texto de quadro inválido ou muito longo.')
        if self.image and not re.fullmatch(r'[a-f0-9]{32}\.png', self.image):
            raise ValueError('Imagem do storyboard inválida.')
        if (self.x is None) != (self.y is None):
            raise ValueError('Posição de quadro incompleta.')
        for value in (self.x, self.y):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)
                                      or not -MAX_POSITION <= value <= MAX_POSITION):
                raise ValueError('Posição de quadro inválida.')


@dataclass(frozen=True)
class Storyboard:
    title: str = 'Storyboard'
    frames: tuple[StoryFrame, ...] = ()
    links: tuple[StoryLink, ...] = ()
    groups: tuple[StoryGroup, ...] = ()

    def validate(self):
        if not isinstance(self.title, str) or len(self.title) > 200:
            raise ValueError('Título do storyboard inválido.')
        if len(self.frames) > MAX_CARDS:
            raise ValueError(f'O storyboard aceita até {MAX_CARDS} quadros.')
        for frame in self.frames:
            frame.validate()
        if len({frame.id for frame in self.frames}) != len(self.frames):
            raise ValueError('Há identificadores de quadros repetidos.')
        identifiers = {frame.id for frame in self.frames}
        outgoing, incoming = {}, set()
        if len(self.links) > len(self.frames):
            raise ValueError('Há ligações demais para uma sequência.')
        for link in self.links:
            if link.source not in identifiers or link.target not in identifiers or link.source == link.target:
                raise ValueError('Ligação inválida: escolha dois quadros diferentes do storyboard.')
            if link.source in outgoing or link.target in incoming:
                raise ValueError('Cada quadro aceita apenas uma entrada e uma saída.')
            outgoing[link.source] = link.target
            incoming.add(link.target)
        blocked = {frame.id for frame in self.frames if not frame.node_type.accepts_input}
        if blocked & incoming:
            raise ValueError('O Node Principal inicia a cena e não pode receber uma entrada.')
        checked = set()
        for identifier in identifiers:
            path = set()
            while identifier in outgoing and identifier not in checked:
                if identifier in path:
                    raise ValueError('A ligação criaria um ciclo na sequência.')
                path.add(identifier)
                identifier = outgoing[identifier]
            checked.update(path)
        grouped, group_ids = set(), set()
        for group in self.groups:
            if not isinstance(group.id, str) or not re.fullmatch(r'[a-f0-9]{32}', group.id) or group.id in group_ids:
                raise ValueError('Identificador de grupo inválido ou repetido.')
            if not isinstance(group.title, str) or not group.title.strip() or len(group.title) > 200:
                raise ValueError('Informe um nome de cena com até 200 caracteres.')
            members = set(group.members)
            if not members or not members <= identifiers or len(members) != len(group.members) or members & grouped:
                raise ValueError('Os grupos precisam ter quadros válidos, sem membros repetidos.')
            grouped.update(members)
            group_ids.add(group.id)

    def change(self, identifier, **values):
        if not any(frame.id == identifier for frame in self.frames):
            raise ValueError('O quadro não está mais no storyboard.')
        updated = replace(self, frames=tuple(replace(frame, **values) if frame.id == identifier else frame
                                            for frame in self.frames))
        updated.validate()
        return updated

    def move(self, identifier, target=None):
        """Move antes do destino; destino vazio significa o final da sequência."""
        if identifier == target:
            return self
        frames = list(self.frames)
        source = next((frame for frame in frames if frame.id == identifier), None)
        if source is None or (target and not any(frame.id == target for frame in frames)):
            raise ValueError('Não foi possível localizar o quadro arrastado.')
        frames.remove(source)
        index = next((i for i, frame in enumerate(frames) if frame.id == target), len(frames))
        frames.insert(index, source)
        return replace(self, frames=tuple(frames))
