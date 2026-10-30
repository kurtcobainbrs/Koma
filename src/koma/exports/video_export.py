"""Quadros preparados uma vez, com enquadramento e duração do animatic."""

from decimal import Decimal, ROUND_HALF_UP

from PIL import Image, ImageOps, ImageDraw

from koma.ui.theme import load_theme
from koma.exports.subtitles import render_subtitle
from koma.editor.frame_format import FrameFormat
from koma.exports.drawings import paint_image


def frame_counts(frames, fps, *, durations=None):
    if fps not in (24, 25, 30, 60):
        raise ValueError('Escolha 24, 25, 30 ou 60 FPS.')
    elapsed, previous, counts = Decimal(0), 0, []
    for index, frame in enumerate(frames):
        frame.validate()
        elapsed += Decimal(str(durations[index] if durations is not None else frame.duration))*fps
        boundary = max(previous+1, int(elapsed.quantize(Decimal(1), rounding=ROUND_HALF_UP)))
        counts.append(boundary-previous)
        previous = boundary
    return counts


def timeline_frame_counts(timeline, fps):
    """Mantém o último quadro até o fim do áudio, sem editar o documento."""
    if hasattr(timeline, 'durations'):
        return frame_counts(timeline.frames, fps, durations=timeline.durations)
    counts = frame_counts(timeline.frames, fps)
    if counts:
        end = int((Decimal(str(timeline.total)) * fps).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        counts[-1] += max(0, end - sum(counts))
    return counts


class FrameComposer:
    """Prepare the node's fixed overlays once, then compose changing video frames."""
    def __init__(self, frame, size, *, include_subtitles=True):
        self.frame, self.size = frame, size
        self.colors = load_theme().colors
        self.overlay = None
        if (frame.drawing.visible and frame.drawing.strokes) or (include_subtitles and frame.subtitle.strip()):
            self.overlay = Image.new('RGBA', size)
            paint_image(self.overlay, frame.drawing)
            if include_subtitles and frame.subtitle.strip():
                self.overlay.alpha_composite(render_subtitle(frame.subtitle, size))

    def compose(self, original):
        frame, size = self.frame, self.size
        target = Image.new('RGB', size, self.colors['surface_container_low'])
        if original is not None:
            image = ImageOps.exif_transpose(original).convert('RGBA')
            if frame.image_fit == 'cover':
                image = ImageOps.fit(image, size, Image.Resampling.LANCZOS,
                    centering=((frame.crop_x + 1) / 2, (frame.crop_y + 1) / 2))
            else:
                image = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
            target.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2), image)
        else:
            ImageDraw.Draw(target).text((size[0] // 2, size[1] // 2), 'Sem imagem',
                fill=self.colors['on_surface'], anchor='mm')
        if self.overlay is not None:
            target.paste(self.overlay, (0, 0), self.overlay)
        return target


def compose_frame(frame, original, size, *, include_subtitles=True):
    return FrameComposer(frame, size, include_subtitles=include_subtitles).compose(original)


def prepare_video(frame, store, path, size, fps, count, cancelled, include_subtitles):
    from koma.exports.video_frames import StoryboardFrames
    from koma.exports.video_encoder import encode
    from koma.exports.encoding import DEFAULT_ENCODING
    source = StoryboardFrames((frame,), store, size, (count,), include_subtitles)
    return encode(source, path, fps, DEFAULT_ENCODING.quality, 0, (), cancelled, lambda event: None)

def prepare_frames(frames, store, directory, size, cancelled=lambda: False, *, include_subtitles=True,
                   fps=24, frame_durations=None):
    FrameFormat(*size).validate()
    paths = []
    counts = frame_durations if frame_durations is not None else frame_counts(frames, fps)
    for index, frame in enumerate(frames):
        if cancelled():
            return []
        if frame.active_media is not None and frame.active_media.kind == 'video':
            path = directory / f'{index:06d}.mp4'
            if not prepare_video(frame, store, path, size, fps, counts[index], cancelled, include_subtitles):
                return []
            paths.append(path)
            continue
        if frame.image:
            with Image.open(store.images/frame.image) as original:
                target = compose_frame(frame, original, size, include_subtitles=include_subtitles)
        else:
            target = compose_frame(frame, None, size, include_subtitles=include_subtitles)
        path = directory/f'{index:06d}.png'
        target.save(path, format='PNG')
        paths.append(path)
    return paths
