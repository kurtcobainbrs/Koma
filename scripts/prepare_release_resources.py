"""Recursos de marca e avisos de terceiros para o build Windows."""

import gzip
from importlib.metadata import distribution
from pathlib import Path
from io import BytesIO
import shutil
import tomllib

from packaging.requirements import Requirement
from PIL import Image, ImageDraw, ImageFont


def prepare(root):
    root = Path(root).resolve()
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    assets = root / 'src/koma/assets'
    image = Image.new('RGBA', (512, 512))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, 496, 496), radius=100, fill='#202020')
    draw.rounded_rectangle((66, 66, 446, 446), radius=32, outline='#707070', width=12)
    font = ImageFont.truetype(str(assets / 'fonts/Archivo-SemiBold.ttf'), 316)
    draw.text((256, 258), 'K', font=font, anchor='mm', fill='#F2F2F2', stroke_width=1)
    icon = assets / 'koma.ico'
    encoded = BytesIO()
    image.save(encoded, format='ICO', sizes=[(size, size) for size in (16, 20, 24, 32, 48, 64, 128, 256)])
    if not icon.exists() or icon.read_bytes() != encoded.getvalue():
        icon.write_bytes(encoded.getvalue())
    preview = root / 'build/release'
    preview.mkdir(parents=True, exist_ok=True)
    image.save(preview / 'koma-icon.png')
    client_icon = root / 'flutter/client/windows/runner/resources/app_icon.ico'
    if not client_icon.exists() or client_icon.read_bytes() != icon.read_bytes():
        shutil.copy2(icon, client_icon)
    # O cliente tem versão própria. Uma mudança apenas no Python não exige
    # recompilar Flutter só para atualizar os metadados do processo auxiliar.
    return project


def third_party_notices(root, destination, client):
    root, destination = Path(root), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    pending = ['flet', 'flet-desktop', 'platformdirs', 'reportlab', 'pillow', 'miniaudio', 'av']
    seen, notices = set(), []
    while pending:
        name = pending.pop()
        package = distribution(name)
        normalized = package.metadata['Name'].lower().replace('_', '-')
        if normalized in seen:
            continue
        seen.add(normalized)
        notices.append(f'\n{"=" * 72}\n{package.metadata["Name"]} {package.version}\n')
        for requirement in package.requires or ():
            dependency = Requirement(requirement)
            if dependency.marker is None or dependency.marker.evaluate({'extra': ''}):
                pending.append(dependency.name)
        for entry in package.files or ():
            path = Path(str(entry))
            if any(word in path.name.lower() for word in ('license', 'copying', 'notice')) and path.suffix.lower() not in ('.py', '.pyc'):
                source = package.locate_file(entry)
                if source.is_file():
                    notices.append(f'\n--- {entry} ---\n' + source.read_text(encoding='utf-8', errors='replace'))
    notices.append('\n' + (root / 'src/koma/assets/fonts/OFL.txt').read_text(encoding='utf-8'))
    (destination / 'Python-and-fonts.txt').write_text('\n'.join(notices), encoding='utf-8')
    with gzip.open(Path(client) / 'data/flutter_assets/NOTICES.Z', 'rt', encoding='utf-8') as incoming:
        (destination / 'Flutter-and-plugins.txt').write_text(incoming.read(), encoding='utf-8')


if __name__ == '__main__':
    prepare(Path(__file__).resolve().parents[1])
