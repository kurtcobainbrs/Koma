import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from koma.diagnostics import check
from koma.exports.processes import external_dll_search, external_environment


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_check_produces_portable_document_pdf_and_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / 'diagnostics.json'
            self.assertEqual(await check(report), 0)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(data['ok'])
            self.assertEqual(data['checks']['mp4'], 'not_requested')
            work = Path(data['artifacts'])
            self.assertTrue((work / 'exemplo.koma').is_file())
            self.assertTrue((work / 'exemplo.pdf').read_bytes().startswith(b'%PDF-'))

    async def test_missing_blender_is_a_failed_check_with_error_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / 'diagnostics.json'
            self.assertEqual(await check(report, Path(temporary) / 'missing.exe'), 1)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertFalse(data['ok'])
            self.assertIn('error', data)


class ExternalProcessEnvironmentTests(unittest.TestCase):
    def test_child_path_excludes_bundle_but_parent_environment_is_preserved(self):
        import os
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child = root / 'bundle/extra'
            outside = root / 'blender'
            path = os.pathsep.join((str(child), str(outside)))
            with patch('sys.frozen', True, create=True), patch('sys._MEIPASS', str(root / 'bundle'), create=True), patch.dict(os.environ, {'PATH': path}):
                self.assertEqual(external_environment()['PATH'], str(outside))
                self.assertEqual(os.environ['PATH'], path)

    @unittest.skipUnless(__import__('sys').platform == 'win32', 'API Windows')
    def test_dll_directory_is_restored_even_if_launch_fails(self):
        kernel = Mock()
        def get_directory(length, buffer):
            if buffer is not None:
                buffer.value = 'C:\\bundle'
            return 9
        kernel.GetDllDirectoryW.side_effect = get_directory
        kernel.SetDllDirectoryW.return_value = 1
        with patch('sys.frozen', True, create=True), patch('ctypes.WinDLL', return_value=kernel):
            with self.assertRaises(OSError), external_dll_search():
                raise OSError('launch failed')
        self.assertEqual([call.args for call in kernel.SetDllDirectoryW.call_args_list], [(None,), ('C:\\bundle',)])
