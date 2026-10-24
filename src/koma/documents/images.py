"""Importação fora da interface: cópias de apresentação e miniaturas, sem alterar fontes."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff']
IMAGE_LIMIT = 40_000_000


def import_image(source: Path, store):
    if source.suffix.lower().lstrip('.') not in IMAGE_EXTENSIONS:
        raise ValueError('Escolha uma imagem PNG, JPEG, WebP, BMP ou TIFF.')
    return _import(source, store, source.name)


def import_image_bytes(data: bytes, store):
    if not isinstance(data, bytes) or not data or len(data) > 80_000_000:
        raise ValueError('Imagem da área de transferência vazia ou muito grande.')
    return _import(BytesIO(data), store, 'área de transferência')


def _import(source, store, label):
    name = f'{uuid4().hex}.png'
    store.images.mkdir(parents=True, exist_ok=True)
    store.thumbnails.mkdir(parents=True, exist_ok=True)
    target, thumbnail = store.images / name, store.thumbnails / name
    try:
        with Image.open(source) as original:
            if original.width * original.height > IMAGE_LIMIT:
                raise ValueError('A imagem ultrapassa 40 megapixels. Use uma cópia menor para o storyboard.')
            image = ImageOps.exif_transpose(original).convert('RGBA')
            image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
            image.save(target, format='PNG')
            image.thumbnail((640, 640), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            data = buffer.getvalue()
            thumbnail.write_bytes(data)
        return name, data
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        target.unlink(missing_ok=True)
        thumbnail.unlink(missing_ok=True)
        raise ValueError(f'Não foi possível importar {label}: {exc}') from exc


def load_thumbnails(board, store):
    thumbnails = {}
    for frame in board.frames:
        if frame.image and frame.image not in thumbnails:
            try:
                thumbnails[frame.image] = (store.thumbnails / frame.image).read_bytes()
            except OSError:
                from koma.documents.bundle import validate_image, thumbnail
                source = store.images / frame.image
                validate_image(source)
                store.thumbnails.mkdir(parents=True, exist_ok=True)
                thumbnail(source, store.thumbnails / frame.image)
                thumbnails[frame.image] = (store.thumbnails / frame.image).read_bytes()
    return thumbnails
