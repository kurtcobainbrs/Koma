import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import windows_native as native


class NativePolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.client = self.root / 'client'
        self.client.mkdir()
        (self.client / 'flet.exe').write_bytes(b'executable')
        (self.client / 'orphan.dll').write_bytes(b'orphan')
        manifest = self.client / 'data/flutter_assets/NativeAssetsManifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"native-assets":{}}')
        policy = patch.object(native, 'UNUSED_FLET_DLLS', {'orphan.dll': hashlib.sha256(b'orphan').hexdigest()})
        policy.start()
        self.addCleanup(policy.stop)
        reader = patch.object(native, 'inspect_pe', return_value={'machine': 0x8664, 'imports': []})
        self.read_pe = reader.start()
        self.addCleanup(reader.stop)

    def prepare(self):
        return native.flet_datas(self.client, native.FLET_VERSION, self.root / 'policy.json')

    def test_unused_orphan_excluded_without_modifying_source(self):
        paths = [Path(path).name for path, _ in self.prepare()]
        self.assertNotIn('orphan.dll', paths)
        self.assertTrue((self.client / 'orphan.dll').is_file())

    def test_upstream_version_or_hash_change_requires_review(self):
        with self.assertRaises(ValueError):
            native.flet_datas(self.client, 'future', self.root / 'policy.json')
        (self.client / 'orphan.dll').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.prepare()

    def test_static_or_delay_import_blocks_exclusion(self):
        self.read_pe.return_value['imports'] = ['orphan.dll']
        with self.assertRaises(ValueError):
            self.prepare()

    def test_dynamic_filename_reference_blocks_exclusion(self):
        for data in (b'orphan.dll', 'orphan.dll'.encode('utf-16-le')):
            with self.subTest(data=data):
                (self.client / 'flet.exe').write_bytes(data)
                with self.assertRaises(ValueError):
                    self.prepare()

    def test_debug_runtime_never_accepted_from_host(self):
        self.read_pe.return_value['imports'] = ['vcruntime140d.dll']
        (self.root / 'vcruntime140d.dll').write_bytes(b'host')
        with self.assertRaisesRegex(ValueError, 'runtime de depuração'):
            native.audit_distribution(self.client, self.root / 'audit.json', self.root)

    def test_release_vc_runtime_must_be_bundled_even_when_host_has_it(self):
        self.read_pe.return_value['imports'] = ['vcruntime140.dll']
        (self.root / 'vcruntime140.dll').write_bytes(b'host')
        with self.assertRaisesRegex(ValueError, 'dependência ausente vcruntime140.dll'):
            native.audit_distribution(self.client, self.root / 'audit.json', self.root)

    def test_flutter_cannot_borrow_python_internal_runtime(self):
        dist = self.root / 'dist'
        client = dist / '_internal/desktop/flet'
        client.mkdir(parents=True)
        (client / 'flet.exe').write_bytes(b'flutter')
        (dist / '_internal/vcruntime140.dll').write_bytes(b'python-runtime')
        self.read_pe.side_effect = lambda path: {'machine': 0x8664,
            'imports': ['vcruntime140.dll'] if path.name == 'flet.exe' else []}
        with self.assertRaises(ValueError):
            native.audit_distribution(dist, self.root / 'audit.json', self.root)

    def test_x86_binary_rejected(self):
        self.read_pe.return_value['machine'] = 0x14c
        with self.assertRaisesRegex(ValueError, 'arquitetura diferente de x64'):
            native.audit_distribution(self.client, self.root / 'audit.json', self.root)
