"""Documento imutável; a ordem dos quadros é a ordem da apresentação e do PDF."""

import re
import math
from dataclasses import dataclass, field, replace, fields, MISSING
from uuid import uuid4
from koma.editor.frame_format import FrameFormat
from koma.editor.node_types import node_type
from koma.editor.media_models import AudioTrack, TimelineMarker, MAX_AUDIO_TRACKS, MAX_MARKERS
from koma.editor.drawing_models import DrawingLayer
from koma.editor.sequence_models import SequenceState
from koma.editor.node_media import NodeMedia, MediaTransform, MAX_MEDIA_ITEMS
from koma.editor.reference_models import ReferenceImage, MAX_REFERENCES
from koma.editor.camera_models import CameraMotion

MAX_CARDS = 500
TEXT_LIMIT = 20000
MAX_POSITION = 100000
SUBTITLE_LIMIT = 500
SUPPORTED_FPS = (24, 25, 30, 60)
MIN_DURATION = 1 / 60
MAX_DURATION = 3600


@dataclass(frozen=True)
class StoryLink:
    source: str
    target: str


@dataclass(frozen=True)
class StoryGroup:
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = 'Cena'
    members: tuple[str, ...] = ()


@dataclass(frozen=True, init=False)
class StoryFrame:
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = ''
    action: str = ''
    audio: str = ''
    notes: str = ''
    x: float | None = None
    y: float | None = None
    duration: float = 2.0
    kind: str = 'frame'
    scene_color: str = ''
    subtitle: str = ''
    muted: bool = False
    drawing: DrawingLayer = field(default_factory=DrawingLayer)
    sequence: SequenceState | None = None
    media: tuple[NodeMedia, ...] = ()
    active_media_id: str = ''
    image_defaults: MediaTransform = field(default_factory=MediaTransform)
    camera: CameraMotion = field(default_factory=CameraMotion)

    def __init__(self, **values):
        # Old constructors and replace(..., image/crop_*=...) remain adapters;
        # only canonical node-owned media fields are serialized or stored.
        image_given = 'image' in values
        image = values.pop('image', '')
        active_given = 'active_media_id' in values
        transform_values = {('fit' if key == 'image_fit' else key): values.pop(key)
            for key in ('image_fit', 'crop_x', 'crop_y') if key in values}
        for item in fields(type(self)):
            if item.name in values:
                value = values.pop(item.name)
            elif item.default is not MISSING:
                value = item.default
            else:
                value = item.default_factory()
            object.__setattr__(self, item.name, value)
        if values:
            raise TypeError(f'Propriedades de node desconhecidas: {", ".join(values)}')
        media = self.media
        active = self.active_media_id
        if image_given:
            if not image:
                media, active = (), ''
            else:
                existing = next((entry for entry in media if entry.image == image), None)
                if existing is None:
                    previous = next((entry for entry in media if entry.id == active), None)
                    stem = image.removesuffix('.png') if isinstance(image, str) else ''
                    existing = NodeMedia(id=stem if re.fullmatch(r'[a-f0-9]{32}', stem) else uuid4().hex,
                        asset=image, transform=previous.transform if previous else self.image_defaults)
                    media = (*media, existing)
                active = existing.id
        elif media and not active_given:
            active = media[0].id
        selected = next((entry for entry in media if isinstance(entry, NodeMedia) and entry.id == active), None)
        if transform_values:
            if selected is not None:
                selected = replace(selected, transform=replace(selected.transform, **transform_values))
                media = tuple(selected if entry.id == active else entry for entry in media)
            else:
                object.__setattr__(self, 'image_defaults', replace(self.image_defaults, **transform_values))
        object.__setattr__(self, 'media', media)
        object.__setattr__(self, 'active_media_id', active)
        object.__setattr__(self, '_active_media', selected)

    @property
    def active_media(self):
        return self._active_media

    @property
    def image(self):
        return self.active_media.image if self.active_media else ''

    @property
    def image_fit(self):
        return (self.active_media.transform if self.active_media else self.image_defaults).fit

    @property
    def crop_x(self):
        return (self.active_media.transform if self.active_media else self.image_defaults).crop_x

    @property
    def crop_y(self):
        return (self.active_media.transform if self.active_media else self.image_defaults).crop_y

    @property
    def node_type(self):
        return node_type(self.kind)

    def validate(self):
        if not isinstance(self.camera, CameraMotion):
            raise ValueError('Indicação de câmera inválida.')
        self.camera.validate()
        spec = node_type(self.kind)
        if (not isinstance(self.media, tuple) or len(self.media) > MAX_MEDIA_ITEMS
                or any(not isinstance(entry, NodeMedia) for entry in self.media)):
            raise ValueError('Lista de mídias inválida.')
        if len({entry.id for entry in self.media}) != len(self.media):
            raise ValueError('Mídias repetidas no node.')
        if (bool(self.media) != bool(self.active_media) or (not self.media and self.active_media_id)):
            raise ValueError('Mídia ativa inválida.')
        if not isinstance(self.image_defaults, MediaTransform):
            raise ValueError('Enquadramento padrão inválido.')
        self.image_defaults.validate()
        for entry in self.media:
            entry.validate()
        if spec.contains_frames != (self.sequence is not None):
            raise ValueError('A composição deve pertencer a um node de sequência.')
        if self.sequence is not None:
            if not isinstance(self.sequence, SequenceState):
                raise ValueError('Composição de sequência inválida.')
            self.sequence.validate()
        if not isinstance(self.drawing, DrawingLayer):
            raise ValueError('Camada de desenho inválida.')
        self.drawing.validate()
        if type(self.muted) is not bool:
            raise ValueError('Estado de mute inválido.')
        if not isinstance(self.subtitle, str) or len(self.subtitle) > SUBTITLE_LIMIT:
            raise ValueError(f'A legenda aceita até {SUBTITLE_LIMIT} caracteres.')
        if not isinstance(self.scene_color, str) or (self.scene_color and not re.fullmatch(r'#[a-fA-F0-9]{6}', self.scene_color)):
            raise ValueError('Cor de cena inválida.')
        if type(self.duration) not in (int, float) or not math.isfinite(self.duration) or not MIN_DURATION <= self.duration <= MAX_DURATION:
            raise ValueError('Informe uma duração entre 1/60 e 3600 segundos.')
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
    fps: int = 24
    audio_tracks: tuple[AudioTrack, ...] = ()
    markers: tuple[TimelineMarker, ...] = ()
    frame_format: FrameFormat = field(default_factory=FrameFormat)
    references: tuple[ReferenceImage, ...] = ()
    media_filter: str = 'none'

    def validate(self):
        from koma.media_filters import selected_filter
        selected_filter(self.media_filter)
        if not isinstance(self.references, tuple) or len(self.references) > MAX_REFERENCES:
            raise ValueError(f'O projeto aceita até {MAX_REFERENCES} referências.')
        if any(not isinstance(item, ReferenceImage) for item in self.references):
            raise ValueError('Referência inválida.')
        for item in self.references:
            item.validate()
        if len({item.id for item in self.references}) != len(self.references):
            raise ValueError('Referências repetidas no projeto.')
        if not isinstance(self.frame_format, FrameFormat):
            raise ValueError('Formato do projeto inválido.')
        self.frame_format.validate()
        if type(self.fps) is not int or self.fps not in SUPPORTED_FPS:
            raise ValueError('Escolha 24, 25, 30 ou 60 FPS.')
        if not isinstance(self.title, str) or len(self.title) > 200:
            raise ValueError('Título do storyboard inválido.')
        if len(self.frames) > MAX_CARDS:
            raise ValueError(f'O storyboard aceita até {MAX_CARDS} quadros.')
        for frame in self.frames:
            frame.validate()
        if sum(len(frame.media) for frame in self.frames) > MAX_MEDIA_ITEMS:
            raise ValueError(f'O projeto aceita até {MAX_MEDIA_ITEMS} itens de mídia.')
        if len({frame.id for frame in self.frames}) != len(self.frames):
            raise ValueError('Há identificadores de quadros repetidos.')
        scenes = {frame.id for frame in self.frames if frame.node_type.starts_scene}
        for collection, limit in ((self.audio_tracks, MAX_AUDIO_TRACKS), (self.markers, MAX_MARKERS)):
            if len(collection) > limit or len({item.id for item in collection}) != len(collection):
                raise ValueError('Trilhas ou marcadores repetidos ou em excesso.')
            for item in collection:
                item.validate(scenes, MAX_CARDS * MAX_DURATION)
        if len({track.scene_id for track in self.audio_tracks}) != len(self.audio_tracks):
            raise ValueError('O projeto e cada cena aceitam uma trilha de áudio própria. Substitua a trilha existente.')
        identifiers = {frame.id for frame in self.frames}
        from koma.editor.sequences import SequenceIndex
        hierarchy = SequenceIndex(self)
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
        hierarchy.validate_flow()
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
