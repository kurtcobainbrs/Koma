import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from koma.exports.video_runner import VideoRunner

class VideoRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
    async def run_case(self, mode):
        image = self.root/'image.png'
        image.write_bytes(b'original image')
        destination = self.root/'video.mp4'
        destination.write_bytes(b'previous video')
        runner = VideoRunner(self.root/'logs')
        process = Mock(returncode=1 if mode == 'failed' else 0)
        process.wait = AsyncMock(return_value=process.returncode)
        process.stdout.readline = AsyncMock(side_effect=[b'KOMA_VIDEO_FINISHED\n', b''])
        async def create(*command, **kwargs):
            self.assertIn('--factory-startup', command)
            self.assertIn('--disable-autoexec', command)
            self.assertFalse(any(part.endswith('.blend') for part in command))
            request = json.loads(Path(command[-1]).read_text(encoding='utf-8'))
            Path(request['output']).write_bytes(b'\x00\x00\x00\x20ftypisom' + b'0'*64)
            if mode == 'cancelled':
                runner.cancel()
            if mode == 'changed':
                image.write_bytes(b'externally changed')
            return process
        with patch('koma.exports.video_runner.asyncio.create_subprocess_exec', side_effect=create):
            if mode in ('failed', 'changed'):
                with self.assertRaises(ValueError):
                    await runner.run(Path(sys.executable), [image], destination, 23.976, 'HIGH', 1920, Mock())
            else:
                result = await runner.run(Path(sys.executable), [image], destination, 24, 'HIGH', 1920, Mock())
                self.assertEqual(result, destination if mode == 'success' else None)
        self.assertFalse(runner.running)
        self.assertFalse(list(self.root.glob('.koma-video-*')))
        if mode == 'success':
            self.assertIn(b'ftyp', destination.read_bytes())
        else:
            self.assertEqual(destination.read_bytes(), b'previous video')
        if mode != 'changed':
            self.assertEqual(image.read_bytes(), b'original image')

    async def test_success_publishes_only_completed_video(self):
        await self.run_case('success')

    async def test_cancel_preserves_existing_video(self):
        await self.run_case('cancelled')

    async def test_encoder_failure_preserves_existing_video(self):
        await self.run_case('failed')

    async def test_images_changed_during_encoding_are_detected(self):
        await self.run_case('changed')
