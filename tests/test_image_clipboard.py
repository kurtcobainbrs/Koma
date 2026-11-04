"""Clipboard contracts and Win32 ownership without changing the user's clipboard."""
import asyncio
import ctypes
from io import BytesIO
import sys
from unittest import TestCase, skipUnless
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image
from flet.controls.exceptions import FletUnsupportedPlatformException
from koma.image_clipboard import copy_image
from koma.windows_clipboard import WindowsClipboard, image_formats, CF_DIBV5
from tests import test_storyboard as fixtures


class ImageClipboardTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp

    def test_windows_fallback_copies_image_formats_when_flet_rejects_desktop(self):
        clipboard = AsyncMock()
        clipboard.set_image.side_effect = FletUnsupportedPlatformException('unsupported')
        with patch('koma.image_clipboard.ft.Clipboard', return_value=clipboard), patch(
                'koma.image_clipboard.sys.platform', 'win32'), patch(
                'koma.windows_clipboard.WindowsClipboard') as native:
            asyncio.run(copy_image(self.source))
        formats = native.return_value.write.call_args.args[0]
        self.assertEqual(formats[0], ('PNG', self.original))
        self.assertEqual(formats[1][0], CF_DIBV5)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_supported_flet_platform_does_not_use_native_clipboard(self):
        clipboard = AsyncMock()
        with patch('koma.image_clipboard.ft.Clipboard', return_value=clipboard), patch(
                'koma.windows_clipboard.WindowsClipboard') as native:
            asyncio.run(copy_image(self.source))
        native.assert_not_called()
        clipboard.set_image.assert_awaited_once_with(self.original)

    def test_dib_preserves_pixel_orientation_and_transparency(self):
        image = Image.new('RGBA', (2, 2))
        image.putdata([(255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 64), (1, 2, 3, 0)])
        source = BytesIO()
        image.save(source, format='PNG')
        formats = image_formats(source.getvalue())
        with Image.open(BytesIO(formats[1][1])) as bitmap:
            self.assertEqual(bitmap.convert('RGBA').tobytes(), image.tobytes())

    def backend(self):
        backend = WindowsClipboard.__new__(WindowsClipboard)
        backend.user = Mock()
        backend.kernel = Mock()
        backend.user.RegisterClipboardFormatW.return_value = 50000
        backend.user.CreateWindowExW.return_value = 123
        backend.user.OpenClipboard.return_value = True
        backend.user.EmptyClipboard.return_value = True
        backend.user.SetClipboardData.return_value = 100
        backend.allocate = Mock(side_effect=[0x100000001, 0x100000002])
        return backend

    def test_transferred_memory_is_owned_by_windows_and_resources_close(self):
        backend = self.backend()
        backend.write((('PNG', b'png'), (CF_DIBV5, b'dib')))
        backend.kernel.GlobalFree.assert_not_called()
        backend.user.OpenClipboard.assert_called_once_with(123)
        backend.user.CloseClipboard.assert_called_once()
        backend.user.DestroyWindow.assert_called_once_with(123)

    def test_failure_frees_only_memory_that_was_not_transferred(self):
        backend = self.backend()
        backend.user.SetClipboardData.side_effect = [0x100000001, 0]
        with self.assertRaises(OSError):
            backend.write((('PNG', b'png'), (CF_DIBV5, b'dib')))
        backend.kernel.GlobalFree.assert_called_once_with(0x100000002)
        backend.user.CloseClipboard.assert_called_once()
        backend.user.DestroyWindow.assert_called_once_with(123)

    def test_busy_clipboard_preserves_contents_and_frees_prepared_memory(self):
        backend = self.backend()
        backend.user.OpenClipboard.side_effect = [False, False]
        with patch('koma.windows_clipboard.OPEN_ATTEMPTS', 2), patch('koma.windows_clipboard.sleep'), self.assertRaises(OSError):
            backend.write((('PNG', b'png'), (CF_DIBV5, b'dib')))
        backend.user.EmptyClipboard.assert_not_called()
        self.assertEqual(backend.kernel.GlobalFree.call_count, 2)
        backend.user.CloseClipboard.assert_not_called()

    @skipUnless(sys.platform == 'win32', 'Win32 ABI')
    def test_windows_api_handles_use_pointer_width(self):
        backend = WindowsClipboard()
        self.assertEqual(ctypes.sizeof(backend.user.SetClipboardData.restype), ctypes.sizeof(ctypes.c_void_p))
        self.assertEqual(ctypes.sizeof(backend.kernel.GlobalAlloc.restype), ctypes.sizeof(ctypes.c_void_p))
