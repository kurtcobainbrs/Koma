import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from koma.ui import drop_runtime


class DropRuntimeTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.client = Path(directory.name)
        files = {}
        for name in ('flet.exe', 'flutter_windows.dll', 'data/app.so',
                     'data/flutter_assets/fonts/MaterialIcons-Regular.otf'):
            path = self.client / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.manifest = dict(protocol=1, flet='1.0.5', files=files)
        self.write_manifest()
        self.addCleanup(setattr, drop_runtime, '_enabled', False)

    def write_manifest(self):
        (self.client / 'koma-client.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_valid_client_enables_widgets_and_uses_exact_verified_directory(self):
        with patch.dict('os.environ', {'KOMA_FLET_CLIENT': str(self.client), 'KOMA_EXTERNAL_DROP': '1'}):
            self.assertTrue(drop_runtime.configure())
            self.assertTrue(drop_runtime.enabled())
            import os
            self.assertEqual(Path(os.environ['FLET_VIEW_PATH']), self.client)

    def test_modified_or_missing_binary_does_not_enable_custom_widgets(self):
        (self.client / 'flet.exe').write_bytes(b'altered')
        with patch.dict('os.environ', {'KOMA_FLET_CLIENT': str(self.client), 'KOMA_EXTERNAL_DROP': '1'}):
            self.assertFalse(drop_runtime.configure())
            self.assertFalse(drop_runtime.enabled())

    def test_client_without_material_icons_is_rejected(self):
        del self.manifest['files']['data/flutter_assets/fonts/MaterialIcons-Regular.otf']
        self.write_manifest()
        with self.assertRaises(ValueError):
            drop_runtime.validate_client(self.client)

    def test_wrong_protocol_and_path_traversal_are_rejected(self):
        self.manifest['protocol'] = 99
        self.write_manifest()
        with self.assertRaises(ValueError):
            drop_runtime.validate_client(self.client)
        self.manifest['protocol'] = 1
        self.manifest['files']['../outside'] = 'bad'
        self.write_manifest()
        with self.assertRaises(ValueError):
            drop_runtime.validate_client(self.client)

    def test_disabled_receiver_leaves_standard_editor_available(self):
        with patch.dict('os.environ', {'KOMA_EXTERNAL_DROP': '0'}):
            self.assertFalse(drop_runtime.configure())
            self.assertFalse(drop_runtime.enabled())
