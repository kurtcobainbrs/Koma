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


def prepare_frames(frames, store, directory, size, cancelled=lambda: False, *, include_subtitles=True):
    FrameFormat(*size).validate()
    colors = load_theme().colors
    paths = []
    for index, frame in enumerate(frames):
        if cancelled():
            return []
        target = Image.new('RGB', size, colors['surface_container_low'])
        if frame.image:
            with Image.open(store.images/frame.image) as original:
                image = ImageOps.exif_transpose(original).convert('RGBA')
                if frame.image_fit == 'cover':
                    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS,
                        centering=((frame.crop_x+1)/2, (frame.crop_y+1)/2))
                else:
                    image = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
                target.paste(image, ((size[0]-image.width)//2, (size[1]-image.height)//2), image)
        else:
            ImageDraw.Draw(target).text((size[0]//2, size[1]//2), 'Sem imagem', fill=colors['on_surface'], anchor='mm')
        paint_image(target, frame.drawing)
        if include_subtitles and frame.subtitle.strip():
            overlay = render_subtitle(frame.subtitle, size)
            target.paste(overlay, (0, 0), overlay)
        path = directory/f'{index:06d}.png'
        target.save(path, format='PNG')
        paths.append(path)
    return paths
