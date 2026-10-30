"""Reproducible, source-checked overlay isolation for Flet 1.0.5 / Flutter 3.44.8.

Avoid orphaned Windows accessibility nodes from Tooltip/Slider OverlayPortals.
The upstream package cache and Flutter SDK remain unchanged.
See flutter/flutter#182444 and #190357. Remove after the pinned SDK fixes both.
"""
import hashlib
import os
from pathlib import Path
import shutil

VERSION = '1.0.5'
SOURCES = {
    'lib/src/controls/base_controls.dart': '60467718ed47200631c2a000d48c7744d48d7d9f87cb1a3dde3ff2c1bdf6e86e',
    'lib/src/controls/slider.dart': '1dde0d65ef71e65dcec20829783f72b0ca4f289714e732cd4ba43f1219405a28',
    'lib/src/controls/container.dart': '0b79bba5c58286695351ddfb8dbb8b0d6e3d8d088949da3aff760ee8887c8e31',
}


def prepare(root, source=None):
    root = Path(root)
    cache = Path(os.environ.get('PUB_CACHE', Path.home() / 'AppData/Local/Pub/Cache'))
    source = Path(source) if source else cache / 'hosted/pub.dev' / f'flet-{VERSION}'
    destination = root / 'build/flet-compat'
    verified = {}
    for name, digest in SOURCES.items():
        data = (source / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f'Fonte Flet incompatível com a correção de acessibilidade: {name}')
        verified[name] = data.decode('utf-8')
    if not (destination / 'pubspec.yaml').is_file():
        shutil.copytree(source, destination, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.dart_tool', 'build', '.git'))
    helper = (root / 'flutter/compat/overlay_boundary.dart').read_text(encoding='utf-8')
    (destination / 'lib/src/utils/koma_overlay.dart').write_text(helper, encoding='utf-8', newline='\n')
    for name, content in verified.items():
        if name.endswith('container.dart'):
            old = 'if (ignoreInteractions) {\n      container = IgnorePointer(child: container);\n    }'
            new = 'container = IgnorePointer(ignoring: ignoreInteractions, child: container);'
        elif name.endswith('base_controls.dart'):
            content = "import '../utils/koma_overlay.dart';\n" + content
            old = 'return parseTooltip(control.get("tooltip"), context, widget) ?? widget;'
            new = ('final tooltip = parseTooltip(control.get("tooltip"), context, widget);\n'
                '  return tooltip == null ? widget : isolateTooltip(tooltip);')
        else:
            content = "import '../utils/koma_overlay.dart';\n" + content
            old = 'return LayoutControl(control: widget.control, child: slider);'
            new = 'return LayoutControl(control: widget.control, child: isolateOverlay(slider));'
        if content.count(old) != 1:
            raise ValueError(f'Contrato da correção Flet alterado: {name}')
        path = destination / name
        updated = content.replace(old, new)
        if path.read_text(encoding='utf-8') != updated:
            path.write_text(updated, encoding='utf-8', newline='\n')
    return destination
