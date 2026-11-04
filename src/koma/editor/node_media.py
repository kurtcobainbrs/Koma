"""Immutable media choices owned by each node, independent of shot duration."""
from dataclasses import dataclass, field, replace
from uuid import uuid4
import math
import re
from koma.editor.media_animation import MediaPose, MediaKeyframe, validate_animation, evaluate_pose, animation_from_document

VIDEO_EXTENSIONS = ('mp4', 'mov', 'mkv', 'webm', 'avi', 'm4v')
MAX_MEDIA_ITEMS = 4096
MAX_VIDEO_BYTES = 512 * 1024 * 1024
MAX_VIDEO_DURATION = 3600
MAX_VIDEO_PIXELS = 40_000_000


@dataclass(frozen=True)
class MediaTransform:
    fit: str = 'cover'
    crop_x: float = 0
    crop_y: float = 0
    pose: MediaPose = field(default_factory=MediaPose)
    keyframes: tuple[MediaKeyframe, ...] = ()

    @property
    def base_signature(self):
        return self.fit, self.crop_x, self.crop_y, self.pose

    def at(self, seconds=0):
        return evaluate_pose(self.pose, self.keyframes, seconds)

    def validate(self):
        validate_animation(self.pose, self.keyframes)
        if self.fit not in ('cover', 'contain'):
            raise ValueError('Enquadramento de mídia inválido.')
        if any(type(n) not in (int, float) or not math.isfinite(n) or not -1 <= n <= 1
               for n in (self.crop_x, self.crop_y)):
            raise ValueError('Posição de mídia inválida.')


@dataclass(frozen=True)
class NodeMedia:
    id: str = field(default_factory=lambda: uuid4().hex)
    kind: str = 'image'
    asset: str = ''
    label: str = ''
    poster: str = ''
    width: int = 0
    height: int = 0
    duration: float = 0
    transform: MediaTransform = field(default_factory=MediaTransform)

    @property
    def image(self):
        return self.asset if self.kind == 'image' else self.poster

    @property
    def folder(self):
        return 'images' if self.kind == 'image' else 'videos'

    def validate(self):
        if not isinstance(self.id, str) or not re.fullmatch(r'[a-f0-9]{32}', self.id):
            raise ValueError('Identificador de mídia inválido.')
        if self.kind not in ('image', 'video') or not isinstance(self.label, str) or len(self.label) > 200:
            raise ValueError('Mídia inválida.')
        suffix = r'png' if self.kind == 'image' else '(' + '|'.join(VIDEO_EXTENSIONS) + ')'
        if not isinstance(self.asset, str) or not re.fullmatch(r'[a-f0-9]{32}\.' + suffix, self.asset):
            raise ValueError('Arquivo de mídia inválido.')
        if self.kind == 'video' and (not isinstance(self.poster, str) or not re.fullmatch(r'[a-f0-9]{32}\.png', self.poster)):
            raise ValueError('Prévia de vídeo inválida.')
        if self.kind == 'image' and self.poster:
            raise ValueError('Uma imagem não precisa de outro arquivo de prévia.')
        if any(type(n) is not int or n < 0 for n in (self.width, self.height)):
            raise ValueError('Dimensões de mídia inválidas.')
        if self.width * self.height > MAX_VIDEO_PIXELS:
            raise ValueError('A mídia ultrapassa 40 megapixels.')
        if (type(self.duration) not in (int, float) or not math.isfinite(self.duration)
                or self.duration < 0 or self.duration > MAX_VIDEO_DURATION):
            raise ValueError('Duração da mídia inválida.')
        if self.kind == 'video' and (not self.width or not self.height or self.duration <= 0):
            raise ValueError('Vídeo sem dimensões ou duração válida.')
        if not isinstance(self.transform, MediaTransform):
            raise ValueError('Enquadramento de mídia inválido.')
        self.transform.validate()

    def remap_assets(self, names):
        return replace(self, asset=names[self.folder, self.asset],
            poster=names['images', self.poster] if self.poster else '')

    @classmethod
    def from_document(cls, value):
        if not isinstance(value, dict):
            raise ValueError('Mídia de node inválida.')
        values = dict(value)
        values['transform'] = MediaTransform(**animation_from_document(values.get('transform', {})))
        return cls(**values)


def frame_assets(frame):
    assets = {(item.folder, item.asset) for item in frame.media}
    assets.update(('images', item.poster) for item in frame.media if item.poster)
    return assets


def with_image(frame, name, label=''):
    item = NodeMedia(asset=name, label=label[:200], transform=MediaTransform(fit=frame.image_fit))
    return replace(frame, media=(*frame.media, item), active_media_id=item.id)


def board_assets(board):
    assets = set()
    for frame in board.frames:
        assets.update(frame_assets(frame))
    assets.update(('audio', track.asset) for track in board.audio_tracks)
    assets.update(('images', item.asset) for item in board.references)
    return assets
