"""Navigation state, cursor anchors and bounded commands; no manual UI testing."""
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch
import flet as ft
from koma.editor.scroll_requests import ScrollRequests
from tests import test_storyboard as fixtures


class AnimaticNavigationTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def player(self):
        with patch('koma.ui.drop_runtime.supports', return_value=True):
            view = self.view()
        fixtures.finish(view.add_frame())
        fixtures.finish(view.add_frame())
        view.player.open()
        view.player.strip.resized(Data(width=800))
        return view.player

    def test_independent_views_anchor_and_zoom_below_fit_preserve_nodes_and_history(self):
        player = self.player()
        view, strip = player.view, player.strip
        board, past, position = view.board, tuple(view.history.past), player.position
        native = strip.native_navigation
        strip.fit()
        initial = strip.scale.seconds(strip.offset + 300)
        strip.native_zoom(Data(factor=2, anchor_x=300, pixels=strip.offset, generation=strip.generation))
        self.assertAlmostEqual(strip.scale.seconds(strip.offset + 300), initial)
        self.assertEqual(native.scroll_offset, strip.offset)
        self.assertEqual(player.preview_navigation.zoom, 1)
        scale = strip.scale
        player.preview_navigation.pose(Data(zoom=3, x=-50, y=40,
            generation=player.preview_navigation.content.generation))
        self.assertEqual(player.preview_navigation.zoom, 3)
        self.assertIs(strip.scale, scale)
        strip.fit()
        fit_scale = strip.scale.pixels_per_second
        strip.zoom(.5, anchor_x=0)
        self.assertLess(strip.scale.pixels_per_second, fit_scale)
        self.assertEqual(player.preview_navigation.zoom, 3)
        before = strip.scale
        strip.native_zoom(Data(factor=10, anchor_x=0, pixels=0, generation=strip.generation - 1))
        self.assertIs(strip.scale, before)
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), past)
        self.assertEqual(player.position, position)
        self.assertEqual(view.store.load(), board)

    def test_new_timelines_start_at_global_minimum_and_fit_remains_explicit(self):
        player = self.player()
        strip = player.strip
        self.assertEqual(strip.scale.pixels_per_second, strip.zoom_limits()[0])
        self.assertEqual(strip.zoom_slider.value, 0)
        board, past = player.view.board, tuple(player.view.history.past)
        strip.resized(Data(width=1200))
        self.assertEqual(strip.scale.pixels_per_second, strip.zoom_limits()[0])
        strip.fit()
        self.assertEqual(strip.scale.pixels(player.timeline.total), strip.width)
        strip.reset()
        self.assertEqual(strip.scale.pixels_per_second, strip.zoom_limits()[0])
        self.assertIs(player.view.board, board)
        self.assertEqual(tuple(player.view.history.past), past)

    def test_track_host_uses_only_the_active_navigation_handler(self):
        player = self.player()
        self.assertIs(player.strip.track_host.content, player.strip.scroller)
        with patch('koma.ui.drop_runtime.supports', return_value=False):
            legacy = self.view().player.strip
        self.assertIsInstance(legacy.track_host.content, ft.GestureDetector)
        self.assertIs(legacy.track_host.content.content, legacy.scroller)
        self.assertEqual(legacy.track_host.content.on_scroll, legacy.wheel_zoom)

    def test_scope_fit_drawing_lock_and_preferences_are_local(self):
        player = self.player()
        view = player.view
        player.preview_navigation.activate()
        with patch.object(player.preview_navigation.content, '_invoke_method', new=AsyncMock()) as method:
            fixtures.finish(player.key_down(Data(key='f')))
            self.assertEqual(method.call_args.args[0], 'fit')
        player.preview_navigation.lock(True)
        self.assertFalse(player.preview_navigation.content.navigation_enabled)
        player.preview_navigation.lock(False)
        self.assertTrue(player.preview_navigation.content.navigation_enabled)
        board = view.board
        values = view.settings.configuration.editable()
        values['animatic'].update(preview_min_zoom=50, preview_max_zoom=800,
            timeline_min_zoom=25, timeline_pan_speed=2, timeline_tail=1)
        fixtures.finish(view.settings.configuration.commit(values))
        self.assertEqual(player.preview_navigation.content.minimum_zoom, .5)
        self.assertEqual(player.preview_navigation.content.maximum_zoom, 8)
        self.assertEqual(player.strip.native_navigation.pan_speed, 2)
        self.assertGreater(player.strip.track.width, player.strip.scale.pixels(player.timeline.total))
        self.assertIs(view.board, board)

    def test_legacy_scroll_requests_keep_only_latest_and_discard_old_scope(self):
        page, controller = Mock(), Mock()
        strip = Data(generation=0, player=Data(presenting=True, view=Data(page=page)), scroller=controller)
        requests = ScrollRequests(strip)
        calls = []
        async def invoke(name, args, timeout):
            calls.append(args['offset'])
            if args['offset'] == 10:
                requests.request(20)
                requests.request(30)
        controller._invoke_method = AsyncMock(side_effect=invoke)
        requests.request(10)
        fixtures.finish(requests.flush())
        self.assertEqual(calls, [10, 30])
        self.assertEqual(page.run_task.call_count, 1)
        self.assertFalse(requests.running)
        requests.request(100)
        strip.generation += 1
        fixtures.finish(requests.flush())
        self.assertEqual(calls, [10, 30])
