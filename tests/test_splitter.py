"""Divider gestures send only changed sizes and preserve the release position."""
import unittest
from types import SimpleNamespace as Data
from unittest.mock import Mock

import flet as ft

from koma.ui.design import DRAG_INTERVAL_MS
from koma.ui.splitter import Splitter


def pointer(x, y=0):
    return Data(global_position=Data(x=x, y=y))


class SplitterTests(unittest.TestCase):
    def test_reverse_drag_coalesces_sizes_and_applies_release(self):
        page = Mock(width=1000, height=800)
        target = ft.Container(width=300)
        splitter = Splitter(page, target, reverse=True, minimum=240)
        self.assertEqual(splitter.content.drag_interval, DRAG_INTERVAL_MS)
        splitter.begin(pointer(500))
        splitter.move(pointer(480))
        self.assertEqual(target.width, 320)
        splitter.move(pointer(479.8))
        page.update.assert_called_once_with(target)
        splitter.end(pointer(470))
        self.assertEqual(target.width, 330)
        self.assertEqual(page.update.call_count, 2)
        self.assertTrue(splitter.user_resized)
        splitter.move(pointer(450))
        self.assertEqual(target.width, 330)

    def test_clamped_moves_and_cancel_do_not_repeat_updates(self):
        page = Mock(width=800, height=800)
        target = ft.Container(width=300)
        splitter = Splitter(page, target, minimum=240, maximum=600)
        splitter.begin(pointer(0))
        splitter.move(pointer(-100))
        self.assertEqual(target.width, 240)
        splitter.move(pointer(-200))
        self.assertEqual(page.update.call_count, 1)
        splitter.move(pointer(500))
        self.assertEqual(target.width, 520)
        splitter.cancel(Data())
        splitter.end(pointer(700))
        self.assertEqual(page.update.call_count, 2)
        self.assertIsNone(splitter.origin)

    def test_horizontal_resize_preserves_fixed_height_and_noop_gesture(self):
        page = Mock(width=1000, height=800)
        target = ft.Container(height=300, expand=False)
        splitter = Splitter(page, target, horizontal=True)
        splitter.begin(pointer(0, 100))
        splitter.end(pointer(0, 100))
        page.update.assert_not_called()
        self.assertFalse(splitter.user_resized)
        splitter.begin(pointer(0, 100))
        splitter.end(pointer(0, 150))
        self.assertEqual(target.height, 350)
        self.assertIs(target.expand, False)
        page.update.assert_called_once_with(target)
