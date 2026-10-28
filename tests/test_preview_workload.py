"""Fast navigation keeps a single subtitle worker and the latest request."""
import unittest
from types import SimpleNamespace as Data
from unittest.mock import AsyncMock, Mock

from koma.editor.frame_format import FrameFormat
from koma.editor.subtitle_preview import SubtitlePreview
from tests.test_storyboard import finish


class PreviewWorkloadTests(unittest.TestCase):
    def test_rapid_subtitle_changes_replace_pending_work_instead_of_queuing(self):
        page = Mock()
        player = Data(view=Data(page=page, board=Data(frame_format=FrameFormat())))
        preview = SubtitlePreview(player)
        preview.prepare = AsyncMock()
        for text in ('First', 'Second', 'Latest'):
            preview.set_text(text)
        page.run_task.assert_called_once_with(preview.drain)
        finish(preview.drain())
        preview.prepare.assert_awaited_once_with('Latest', 3, FrameFormat().preview_size())
        self.assertFalse(preview.preparing)
        preview.set_text('Discard')
        preview.clear()
        finish(preview.drain())
        self.assertEqual(preview.prepare.await_count, 1)
