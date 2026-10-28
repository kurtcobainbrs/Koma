"""Shared picker updates stay local; native slider state is not echoed back."""
import unittest
from types import SimpleNamespace as Data
from unittest.mock import Mock

from koma.ui.color_picker import ColorPicker
from koma.ui.design import DRAG_INTERVAL_MS


class ColorPickerTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock()
        self.applied, self.previewed = Mock(), Mock()
        self.picker = ColorPicker(self.page, 'Cor', '#FF0000', self.applied, self.previewed)

    def test_wheel_updates_only_marker_and_sample_with_bounded_event_rate(self):
        picker = self.picker
        self.assertEqual(picker.wheel.drag_interval, DRAG_INTERVAL_MS)
        event = Data(local_position=Data(x=picker.WHEEL_SIZE / 2, y=picker.WHEEL_SIZE))
        picker.wheel.on_pan_update(event)
        self.assertEqual(self.page.update.call_args.args, (picker.marker, picker.preview))
        self.assertAlmostEqual(picker.hue, .25)
        self.assertEqual(picker.saturation, 1)
        self.assertEqual(picker.marker.bgcolor, picker.value)
        self.previewed.assert_called_once_with(picker.value)
        picker.wheel.on_pan_update(event)
        self.assertEqual(self.page.update.call_count, 1)
        self.applied.assert_not_called()
        picker.wheel.on_pan_end(Data(local_position=Data(x=0, y=picker.WHEEL_SIZE / 2)))
        self.assertAlmostEqual(picker.hue, .5)
        self.assertEqual(picker.value, '#00FFFF')

    def test_brightness_uses_native_thumb_without_sending_slider_patch(self):
        picker = self.picker
        picker.value_slider.value = 25
        picker.value_slider.on_change(Data(control=picker.value_slider))
        self.assertEqual(picker.brightness, .25)
        self.assertEqual(self.page.update.call_args.args, (picker.marker, picker.preview))
        self.assertEqual(picker.value_slider.value, 25)
        self.assertEqual(picker.value, '#400000')

    def test_palette_updates_slider_only_when_brightness_changes(self):
        picker = self.picker
        picker.select('#000080')
        self.assertEqual(self.page.update.call_args.args, (picker.marker, picker.preview, picker.value_slider))
        self.assertAlmostEqual(picker.value_slider.value, 128 / 255 * 100)
        self.assertEqual(picker.value, '#000080')

    def test_queued_events_after_apply_or_cancel_cannot_modify_selection(self):
        picker = self.picker
        picker.apply(None)
        self.applied.assert_called_once_with('#FF0000')
        self.page.update.reset_mock()
        picker.pick(Data(local_position=Data(x=10, y=10)))
        picker.change_value(Data(control=Data(value=10)))
        picker.select('#000000')
        self.assertEqual(picker.value, '#FF0000')
        self.page.update.assert_not_called()
