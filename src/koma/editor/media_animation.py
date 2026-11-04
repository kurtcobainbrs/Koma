"""Immutable, normalized media animation independent from UI and renderers."""
from bisect import bisect_right
from dataclasses import dataclass, replace
import math

MAX_KEYFRAMES = 2048
MAX_KEYFRAME_TIME = 3600
MAX_TRANSLATION = 10
MIN_SCALE = .01
MAX_SCALE = 100
MAX_ROTATION = 36000
INTERPOLATIONS = {'linear': 'Linear', 'hold': 'Constante'}


@dataclass(frozen=True)
class MediaPose:
    x: float = 0
    y: float = 0
    scale: float = 1
    rotation: float = 0

    def validate(self):
        for value, low, high in ((self.x, -MAX_TRANSLATION, MAX_TRANSLATION),
                (self.y, -MAX_TRANSLATION, MAX_TRANSLATION), (self.scale, MIN_SCALE, MAX_SCALE),
                (self.rotation, -MAX_ROTATION, MAX_ROTATION)):
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('Transformação da mídia fora dos limites.')


@dataclass(frozen=True)
class MediaKeyframe:
    time: float
    pose: MediaPose
    interpolation: str = 'linear'

    def validate(self):
        if type(self.time) not in (int, float) or not math.isfinite(self.time) or not 0 <= self.time <= MAX_KEYFRAME_TIME:
            raise ValueError('Tempo do keyframe inválido.')
        if not isinstance(self.pose, MediaPose) or self.interpolation not in INTERPOLATIONS:
            raise ValueError('Keyframe de mídia inválido.')
        self.pose.validate()


def validate_animation(pose, keys):
    if not isinstance(pose, MediaPose) or not isinstance(keys, tuple) or len(keys) > MAX_KEYFRAMES:
        raise ValueError(f'A mídia aceita até {MAX_KEYFRAMES} keyframes.')
    pose.validate()
    previous = -1
    for key in keys:
        if not isinstance(key, MediaKeyframe):
            raise ValueError('Keyframe de mídia inválido.')
        key.validate()
        if key.time <= previous:
            raise ValueError('Os keyframes devem ter tempos distintos e estar em ordem.')
        previous = key.time


def evaluate_pose(pose, keys, seconds):
    if not keys:
        return pose
    index = bisect_right(keys, seconds, key=lambda key: key.time)
    if index == 0:
        return keys[0].pose
    left = keys[index - 1]
    if index == len(keys) or left.interpolation == 'hold':
        return left.pose
    right = keys[index]
    ratio = (seconds - left.time) / (right.time - left.time)
    return MediaPose(*(getattr(left.pose, name) + (getattr(right.pose, name) - getattr(left.pose, name)) * ratio
        for name in ('x', 'y', 'scale', 'rotation')))


def key_time(seconds, fps):
    return max(0, min(MAX_KEYFRAME_TIME, round(seconds * fps) / fps))


def update_pose(transform, pose, seconds, fps, *, auto_key=False, interpolation='linear'):
    """Write a key only when explicitly requested; otherwise edit the base pose."""
    pose.validate()
    if not auto_key:
        return replace(transform, pose=pose)
    time = key_time(seconds, fps)
    keys = tuple(key for key in transform.keyframes if abs(key.time - time) > 1e-8)
    if not transform.keyframes and time > 0:
        keys = (MediaKeyframe(0, transform.pose, interpolation),)
    result = replace(transform, keyframes=tuple(sorted((*keys, MediaKeyframe(time, pose, interpolation)), key=lambda key: key.time)))
    result.validate()
    return result


def animation_from_document(raw):
    if not isinstance(raw, dict):
        raise ValueError('Transformação de mídia inválida.')
    values = dict(raw)
    values['pose'] = MediaPose(**values.get('pose', {}))
    keys = values.get('keyframes', [])
    if not isinstance(keys, list) or len(keys) > MAX_KEYFRAMES:
        raise ValueError('Lista de keyframes inválida.')
    values['keyframes'] = tuple(MediaKeyframe(key['time'], MediaPose(**key['pose']), key.get('interpolation', 'linear')) for key in keys)
    return values


def retime_keyframe(transform, old_time, seconds, fps, duration, *, allow_outside=False):
    time = key_time(seconds, fps)
    if not allow_outside:
        time = min(time, max(0, (round(duration * fps) - 1) / fps))
    keys = tuple(replace(key, time=time) if abs(key.time - old_time) < 1e-8 else key for key in transform.keyframes)
    times = [key.time for key in keys]
    if len(set(times)) != len(times):
        raise ValueError('Já existe um keyframe nesse frame.')
    result = replace(transform, keyframes=tuple(sorted(keys, key=lambda key: key.time)))
    result.validate()
    return result, time


def remove_keyframe(transform, seconds):
    """Deleting animation never writes the media's base pose."""
    return replace(transform, keyframes=tuple(key for key in transform.keyframes if abs(key.time - seconds) > 1e-8))
