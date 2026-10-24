"""Quadros preparados uma vez, com enquadramento e duração do animatic."""

from decimal import Decimal, ROUND_HALF_UP

from PIL import Image, ImageOps, ImageDraw

from koma.ui.theme import load_theme
from koma.exports.subtitles import render_subtitle


def frame_counts(frames, fps):
    if fps not in (24, 25, 30, 60):
        raise ValueError('Escolha 24, 25, 30 ou 60 FPS.')
    elapsed, previous, counts = Decimal(0), 0, []
    for frame in frames:
        frame.validate()
        elapsed += Decimal(str(frame.duration))*fps
        boundary = max(previous+1, int(elapsed.quantize(Decimal(1), rounding=ROUND_HALF_UP)))
        counts.append(boundary-previous)
        previous = boundary
    return counts


def prepare_frames(frames, store, directory, size, cancelled=lambda: False, *, include_subtitles=True):
    if size not in ((1920, 1080), (1280, 720)):
        raise ValueError('Resolução de animatic inválida.')
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
        if include_subtitles and frame.subtitle.strip():
            overlay = render_subtitle(frame.subtitle, size)
            target.paste(overlay, (0, 0), overlay)
        path = directory/f'{index:06d}.png'
        target.save(path, format='PNG')
        paths.append(path)
    return paths
