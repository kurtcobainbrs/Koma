import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from koma.diagnostics import check


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

    async def test_mp4_diagnostic_runs_without_external_programs(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / 'diagnostics.json'
            with patch('asyncio.create_subprocess_exec', side_effect=AssertionError('External process')):
                self.assertEqual(await check(report, video=True), 0)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(data['ok'])
            self.assertEqual(data['checks']['mp4'], 'passed')
            self.assertTrue((Path(data['artifacts']) / 'exemplo.mp4').is_file())


    async def test_codec_failure_produces_an_error_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / 'diagnostics.json'
            with patch('koma.diagnostics.VideoRunner.run', new=AsyncMock(side_effect=ValueError('Falha no codec'))):
                self.assertEqual(await check(report, video=True), 1)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertFalse(data['ok'])
            self.assertIn('Falha no codec', data['error'])
