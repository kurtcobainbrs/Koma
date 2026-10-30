"""Pacote .koma: manifesto e PNGs, validados antes da troca de sessão."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile, BadZipFile, ZIP_STORED

from PIL import Image, ImageOps

from koma.documents.images import IMAGE_LIMIT
from koma.documents.store import document, parse_document
from koma.editor.models import MAX_CARDS
from koma.editor.media_models import MAX_AUDIO_TRACKS
from koma.documents.audio import validate_audio, MAX_AUDIO_BYTES
from koma.editor.node_media import board_assets, MAX_MEDIA_ITEMS, MAX_VIDEO_BYTES

EXTENSION = '.koma'
MAX_IMAGE_BYTES = 80_000_000
MAX_MANIFEST_BYTES = 64_000_000
MAX_BUNDLE_BYTES = 2_000_000_000


def destination_stamp(path):
    path = Path(path)
    try:
        with path.open('rb') as source:
            info = os.fstat(source.fileno())
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        return info.st_size, info.st_mtime_ns, digest
    except FileNotFoundError:
        return None


def validate_image(path):
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_IMAGE_BYTES:
        raise ValueError('Uma imagem está ausente, vazia ou é muito grande.')
    try:
        with Image.open(path) as image:
            if image.format != 'PNG' or image.width * image.height > IMAGE_LIMIT:
                raise ValueError('Imagem inválida no documento Koma.')
            image.verify()
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError(f'Imagem corrompida: {path.name}') from exc


def thumbnail(source, destination):
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert('RGBA')
        image.thumbnail((640, 640), Image.Resampling.LANCZOS)
        image.save(destination, format='PNG')


def export_bundle(board, store, destination, *, expected_stamp=Ellipsis):
    board.validate()
    destination = Path(destination).expanduser().resolve().with_suffix(EXTENSION)
    initial = destination_stamp(destination)
    if expected_stamp is not Ellipsis and initial != expected_stamp:
        raise ValueError('O arquivo mudou fora do Koma. Use Salvar como para preservar as duas versões.')
    assets = board_assets(board)
    images = {name for kind, name in assets if kind == 'images'}
    videos = {name for kind, name in assets if kind == 'videos'}
    from koma.documents.videos import inspect_video
    for name in videos:
        inspect_video(store.videos / name, decode=False)
    for name in images:
        validate_image(store.images / name)
    audio = {track.asset for track in board.audio_tracks}
    for track in board.audio_tracks:
        validate_audio(store.audio / track.asset, track.duration)
    manifest = json.dumps(document(board, store.document_id), ensure_ascii=False).encode('utf-8')
    if len(manifest) > MAX_MANIFEST_BYTES or (sum((store.images / name).stat().st_size for name in images)
            + sum((store.audio / name).stat().st_size for name in audio)
            + sum((store.videos / name).stat().st_size for name in videos) + len(manifest)) > MAX_BUNDLE_BYTES:
        raise ValueError('O documento ultrapassa os limites do formato Koma (2 GB).')
    temporary = destination.with_name(f'.{uuid4().hex}.tmp')
    backup_tmp = destination.with_name(f'.{uuid4().hex}.bak.tmp')
    try:
        with temporary.open('w+b') as output:
            with ZipFile(output, 'w', compression=ZIP_STORED) as archive:
                archive.writestr('manifest.json', manifest)
                for name in sorted(images):
                    archive.write(store.images / name, f'images/{name}')
                for name in sorted(audio):
                    archive.write(store.audio / name, f'audio/{name}')
                for name in sorted(videos):
                    archive.write(store.videos / name, f'videos/{name}')
            if output.tell() > MAX_BUNDLE_BYTES:
                raise ValueError('O pacote Koma ultrapassa 2 GB.')
            output.flush()
            os.fsync(output.fileno())
        if destination_stamp(destination) != initial:
            raise ValueError('O destino mudou durante o salvamento; o arquivo existente foi preservado.')
        if initial is not None:
            with destination.open('rb') as source, backup_tmp.open('wb') as backup:
                shutil.copyfileobj(source, backup)
                backup.flush()
                os.fsync(backup.fileno())
            backup_tmp.replace(destination.with_suffix('.koma.bak'))
        if destination_stamp(destination) != initial:
            raise ValueError('O destino mudou durante o salvamento; o arquivo existente foi preservado.')
        temporary.replace(destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
        backup_tmp.unlink(missing_ok=True)


def restore_bundle(source, store):
    """O chamador fornece um store novo; nunca escreve na sessão ativa."""
    store.images.mkdir(parents=True, exist_ok=True)
    store.thumbnails.mkdir(exist_ok=True)
    store.audio.mkdir(exist_ok=True)
    store.videos.mkdir(exist_ok=True)
    try:
        with ZipFile(source) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)) or len(names) > MAX_MEDIA_ITEMS * 2 + MAX_AUDIO_TRACKS + 1:
                raise ValueError('Arquivos duplicados ou em excesso no documento.')
            if sum(entry.file_size for entry in entries) > MAX_BUNDLE_BYTES:
                raise ValueError('O documento ultrapassa 2 GB.')
            manifest = archive.getinfo('manifest.json')
            if manifest.file_size > MAX_MANIFEST_BYTES:
                raise ValueError('Manifesto Koma muito grande.')
            board, identifier = parse_document(json.loads(archive.read(manifest)))
            assets = board_assets(board)
            images = {name for kind, name in assets if kind == 'images'}
            videos = {name for kind, name in assets if kind == 'videos'}
            audio = {track.asset for track in board.audio_tracks}
            if set(names) != {'manifest.json', *(f'images/{name}' for name in images),
                    *(f'audio/{name}' for name in audio), *(f'videos/{name}' for name in videos)}:
                raise ValueError('O documento contém arquivos inesperados ou imagens ausentes.')
            for name in images:
                info = archive.getinfo(f'images/{name}')
                if not 0 < info.file_size <= MAX_IMAGE_BYTES:
                    raise ValueError('Imagem vazia ou muito grande no documento.')
                target = store.images / name
                with archive.open(info) as incoming, target.open('xb') as output:
                    shutil.copyfileobj(incoming, output)
                validate_image(target)
                thumbnail(target, store.thumbnails / name)
            for name in audio:
                info = archive.getinfo(f'audio/{name}')
                if not 0 < info.file_size <= MAX_AUDIO_BYTES:
                    raise ValueError('Áudio vazio ou muito grande no documento.')
                target = store.audio / name
                with archive.open(info) as incoming, target.open('xb') as output:
                    shutil.copyfileobj(incoming, output)
                for track in board.audio_tracks:
                    if track.asset == name:
                        validate_audio(target, track.duration)
            from koma.documents.videos import inspect_video
            for name in videos:
                info = archive.getinfo(f'videos/{name}')
                if not 0 < info.file_size <= MAX_VIDEO_BYTES:
                    raise ValueError('Vídeo vazio ou muito grande no documento.')
                target = store.videos / name
                with archive.open(info) as incoming, target.open('xb') as output:
                    shutil.copyfileobj(incoming, output)
                inspect_video(target, decode=False)
        store.document_id = identifier
        store.save(board)
        return board
    except (BadZipFile, KeyError, NotImplementedError, RuntimeError, SyntaxError, UnicodeError) as exc:
        raise ValueError(f'Documento Koma inválido: {exc}') from exc
