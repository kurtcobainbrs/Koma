import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile

from scripts.publish_windows_package import publish
from scripts.prepare_windows_validation import prepare


class PublicationTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.staged = self.root / 'build/staging/Koma'
        self.staged.mkdir(parents=True)
        (self.staged / 'Koma.exe').write_bytes(b'new-package')
        self.audit = dict(errors=[], native_files=[dict(file='Koma.exe',
            sha256=hashlib.sha256(b'new-package').hexdigest())])
        (self.root / 'build/windows-native-audit.json').write_text(json.dumps(self.audit))
        self.destination = self.root / 'dist/Koma'
        self.destination.mkdir(parents=True)
        (self.destination / 'Koma.exe').write_bytes(b'previous-package')
        validation = patch('scripts.publish_windows_package.validate_client')
        validation.start()
        self.addCleanup(validation.stop)

    def test_update_preserves_previous_package(self):
        publish(self.root, self.staged)
        self.assertEqual((self.destination / 'Koma.exe').read_bytes(), b'new-package')
        old = list((self.root / 'dist').glob('previous-*/Koma/Koma.exe'))
        self.assertEqual(len(old), 1)
        self.assertEqual(old[0].read_bytes(), b'previous-package')

    def test_failed_promotion_restores_previous_package(self):
        rename = Path.rename
        def fail_staging(path, target):
            if path == self.staged:
                raise OSError('Falha simulada')
            return rename(path, target)
        with patch.object(Path, 'rename', fail_staging):
            with self.assertRaises(OSError):
                publish(self.root, self.staged)
        self.assertEqual((self.destination / 'Koma.exe').read_bytes(), b'previous-package')

    def test_changed_package_is_not_published(self):
        (self.staged / 'Koma.exe').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            publish(self.root, self.staged)
        self.assertEqual((self.destination / 'Koma.exe').read_bytes(), b'previous-package')

    def test_validation_kit_preserves_old_zip_and_hashes_every_entry(self):
        publish(self.root, self.staged)
        for relative in ('scripts/validate_clean_windows.ps1', 'scripts/new_validation_sandbox.ps1', 'docs/CLEAN_WINDOWS.md'):
            path = self.root / relative
            path.parent.mkdir(exist_ok=True)
            path.write_text('validation support')
        client = self.destination / '_internal/desktop/flet'
        client.mkdir(parents=True)
        (client / 'koma-client.json').write_text('{"protocol":1}')
        archive = self.root / 'dist/Koma-windows-x64-validation.zip'
        archive.write_bytes(b'previous-zip')
        with patch('scripts.prepare_windows_validation.validate_client', return_value=client):
            prepare(self.root)
        previous = list((self.root / 'dist/previous').glob('*/Koma-windows-x64-validation.zip'))
        self.assertEqual(previous[0].read_bytes(), b'previous-zip')
        with ZipFile(archive) as package:
            manifest = json.loads(package.read('SHA256.json'))
            for entry in manifest:
                self.assertEqual(hashlib.sha256(package.read(entry['path'])).hexdigest(), entry['sha256'])
            self.assertIn('koma-client.json', package.namelist())
