"""Targeted draft persistence and form integration; no native UI interaction."""
import json
from unittest.mock import patch
from koma.preference_catalog import CATEGORIES, defaults, validated
from koma.preference_draft import PreferenceDraft
from koma.ui.preferences_panel import PreferencesPanel
from tests import test_storyboard as fixtures


class PreferencesPanelTests(fixtures.unittest.TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_draft_roundtrip_validation_and_legacy_settings_are_independent(self):
        view = self.view()
        view.settings.save()
        settings = view.settings.path.read_bytes()
        document = view.board
        store = PreferenceDraft(view.settings.directory)
        values = defaults()
        values['identity']['scene_prefix'] = 'Scenes_'
        values['timeline']['seconds_decimals'] = 2
        store.write(values)
        self.assertEqual(store.read(), values)
        self.assertEqual(view.settings.path.read_bytes(), settings)
        self.assertIs(view.board, document)
        with self.assertRaises(ValueError):
            validated({'timeline': {'seconds_decimals': float('nan')}})
        with self.assertRaises(ValueError):
            validated({'identity': {'scene_digits': 1.5}})
        store.path.write_text(json.dumps({'version': 900, 'values': values}), encoding='utf-8')
        self.assertEqual(store.read(), defaults())
        store.path.write_text(json.dumps({'version': 1, 'values': {
            'numbers': {'seconds_decimals': 5, 'counter_digits': 6},
            'timeline': {'unit': 'Frames'}}}), encoding='utf-8')
        migrated = store.read()
        self.assertEqual(migrated['timeline']['seconds_decimals'], 5)
        self.assertEqual(migrated['timeline']['counter_digits'], 6)
        self.assertEqual(migrated['timeline']['unit'], 'Frames')
        self.assertNotIn('numbers', migrated)
        store.path.write_text(json.dumps({'version': 2, 'values': {
            'recovery': {'interval': 5, 'restore': False},
            'performance': {'cache': 1024, 'quality': 'Alta'}}}), encoding='utf-8')
        migrated = store.read()
        self.assertEqual(migrated['system']['interval'], 5)
        self.assertFalse(migrated['system']['restore'])
        self.assertEqual(migrated['system']['cache'], 1024)
        self.assertEqual(migrated['system']['quality'], 'Alta')
        self.assertNotIn('recovery', migrated)
        self.assertNotIn('performance', migrated)

    def test_all_categories_render_cancel_discards_and_apply_restores_settings(self):
        view = self.view()
        view.page.width, view.page.height = 1280, 800
        panel = PreferencesPanel(view)
        fixtures.finish(panel.open())
        for category in CATEGORIES:
            panel.select(category)
            expected = set(view.keymap.actions) if category.presentation == 'shortcuts' else {field.key for field in category.fields}
            self.assertEqual(set(panel.controls), expected)
        panel.select(CATEGORIES[0])
        panel.controls['scene_prefix'].value = 'Scenes_'
        panel.changed()
        self.assertIn('Scenes_01', panel.group_examples['scene_prefix'].value)
        self.assertIn('shot_0001', panel.group_examples['shot_prefix'].value)
        self.assertIsNot(panel.group_examples['scene_prefix'], panel.group_examples['shot_prefix'])
        panel.cancel()
        self.assertFalse(panel.store.path.exists())
        panel = PreferencesPanel(view)
        fixtures.finish(panel.open())
        panel.controls['scene_prefix'].value = 'Scenes_'
        fixtures.finish(panel.save())
        reopened = PreferencesPanel(view)
        fixtures.finish(reopened.open())
        self.assertEqual(reopened.controls['scene_prefix'].value, 'Scenes_')
        reopened.reset()
        self.assertEqual(reopened.controls['scene_prefix'].value, 'Scene_')
        reopened.controls['scene_digits'].entry.value = '0'
        with patch.object(reopened.store, 'write') as write:
            fixtures.finish(reopened.save())
            write.assert_not_called()
        self.assertIsNotNone(reopened.controls['scene_digits'].error_text)

    def test_color_picker_confirmation_cancel_and_numeric_controls(self):
        from types import SimpleNamespace as Data
        from koma.ui.color_input import ColorInput
        view = self.view()
        view.page.width, view.page.height = 1280, 800
        panel = PreferencesPanel(view)
        fixtures.finish(panel.open())
        panel.select(next(category for category in CATEGORIES if category.key == 'appearance'))
        color = panel.controls['preview']
        self.assertIsInstance(color, ColorInput)
        color.open()
        color.picker.select('#FF0000')
        color.picker.cancel(None)
        self.assertEqual(panel.values['appearance']['preview'], '#101010')
        color.open()
        color.picker.select('#FF0000')
        color.picker.apply(None)
        self.assertEqual(panel.values['appearance']['preview'], '#FF0000')
        self.assertEqual(color.swatch.bgcolor, '#FF0000')
        panel.select(next(category for category in CATEGORIES if category.key == 'subtitles'))
        opacity = panel.controls['opacity']
        from koma.ui.choice_input import ChoiceInput
        from koma.ui.form_layout import FORM_LAYOUT
        for key in ('font', 'align', 'position'):
            choice = panel.controls[key]
            self.assertIsInstance(choice, ChoiceInput)
            self.assertEqual(choice.button.height, FORM_LAYOUT.row_height)
            self.assertEqual(choice.button.content.height, FORM_LAYOUT.row_height)
        panel.controls['align'].button.items[0].on_click(None)
        self.assertEqual(panel.values['subtitles']['align'], 'Esquerda')
        self.assertIn(opacity.slider, opacity.content.controls)
        self.assertIn(opacity.entry, opacity.content.controls)
        self.assertEqual(opacity.entry.height, opacity.slider.height)
        self.assertIs(panel.fields.controls[-1], panel.preview)
        self.assertLessEqual(panel.preview.height, 64)
        opacity.slider.value = 30
        opacity.slid(Data(control=opacity.slider))
        self.assertEqual(panel.values['subtitles']['opacity'], 30)
        panel.select(CATEGORIES[0])
        digits = panel.controls['scene_digits']
        digits.adjust(1)
        self.assertEqual(panel.values['identity']['scene_digits'], 3)
        self.assertIn('Scene_001', panel.group_examples['scene_prefix'].value)
