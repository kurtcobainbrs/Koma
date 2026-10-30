"""Composite nodes retain owned data through grouping, storage and clipboard."""
from dataclasses import replace
import json
from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch
import flet as ft

from koma.documents.images import import_image
from koma.documents.session import DocumentSession
from koma.documents.store import document, parse_document
from koma.documents.bundle import export_bundle, restore_bundle
from koma.documents.store import StoryboardStore
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.sequence_models import SequenceState
from koma.editor.sequences import SequenceIndex
from koma.editor.timeline import Timeline
from koma.editor.shortcuts import Action
from koma.editor import graph
from koma.editor.node_clipboard import NodeClipboard, capture_selection
from koma.editor.view import StoryboardView
from koma.editor.drawing_models import DrawingLayer, DrawingStroke
from koma.exports.sequence import ExportSequence
from koma.preferences import AppPreferences
from tests import test_storyboard as fixtures


class SequenceTests(TestCase):
    def setUp(self):
        fixtures.StoryboardTests.setUp(self)
        camera = patch('koma.editor.canvas.StoryboardCanvas.restore_camera', new_callable=AsyncMock)
        self.restore_camera = camera.start()
        self.addCleanup(camera.stop)
    view = fixtures.StoryboardTests.view

    def project(self):
        view = self.view()
        name, data = import_image(self.source, view.store)
        root = StoryFrame(kind='main', title='Cena', x=0, y=600)
        a = StoryFrame(title='A', image=name, notes='Preserve', duration=1.5, x=350, y=600,
            drawing=DrawingLayer((DrawingStroke(((.1, .2), (.4, .5)), '#FF0000', .01),)))
        b = StoryFrame(title='B', image=name, duration=2, x=700, y=600)
        c = StoryFrame(title='C', duration=3, x=1050, y=600)
        frames = root, a, b, c
        board = Storyboard(frames=frames, links=tuple(StoryLink(x.id, y.id) for x, y in zip(frames, frames[1:])))
        view.thumbnails[name] = data
        view.changed(board)
        view.refresh()
        fixtures.finish(view.persist())
        return view, root, a, b, c

    def create(self, view, *members):
        previous = set(view.cards)
        view.workspace.navigation.apply_selection({frame.id for frame in members})
        fixtures.finish(view.add_node('sequence'))
        return next(frame for frame in view.board.frames if frame.sequence and frame.id not in previous)

    def test_composition_collapses_visuals_without_changing_playback_or_export(self):
        view, root, a, b, c = self.project()
        before = view.board
        sequence = self.create(view, a, b)
        self.assertEqual(sequence.sequence.members, (a.id, b.id))
        self.assertFalse(view.cards[a.id].content.visible)
        self.assertFalse(view.cards[b.id].content.visible)
        self.assertTrue(view.cards[c.id].content.visible)
        self.assertEqual(view.sequences.index.total(sequence.id), 3.5)
        for frame in before.frames:
            self.assertIs(view.sequences.index.nodes[frame.id], frame)
        self.assertEqual(Timeline(view.board, root.id).frames, (a, b, c))
        self.assertEqual(ExportSequence.from_project(view.board).frames, (a, b, c))
        self.assertEqual(view.workspace.links.port(a.id, False), view.workspace.links.port(sequence.id, False))
        self.assertNotIn(StoryLink(a.id, b.id), view.workspace.links.cache)
        self.assertIn(StoryLink(root.id, sequence.id), view.workspace.links.highlighted)
        fixtures.finish(view.sequences.toggle(sequence.id))
        self.assertTrue(view.cards[a.id].content.visible)
        self.assertIn(StoryLink(a.id, b.id), view.workspace.links.cache)
        self.assertFalse(view.cards[root.id].content.visible)
        self.assertFalse(view.cards[sequence.id].content.visible)
        self.assertFalse(view.cards[c.id].content.visible)
        self.assertNotIn(StoryLink(root.id, a.id), view.workspace.links.cache)
        self.assertNotIn(StoryLink(b.id, c.id), view.workspace.links.cache)
        self.assertIs(view.board.frames[0], before.frames[0])
        fixtures.finish(view.workspace.scope.back())
        self.assertFalse(view.cards[a.id].content.visible)

    def test_duration_is_derived_and_serialization_preserves_node_layers(self):
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        fixtures.finish(view.set_frame_properties(a.id, duration=4))
        self.assertEqual(view.sequences.index.total(sequence.id), 6)
        self.assertIn('144 f', view.cards[sequence.id].duration.value)
        encoded = json.loads(json.dumps(document(view.board, view.store.document_id)))
        restored, _ = parse_document(encoded)
        self.assertEqual(restored, view.board)
        self.assertEqual(SequenceIndex(restored).nodes[a.id].drawing, a.drawing)
        self.assertEqual(view.store.load(), view.board)
        legacy = json.loads(json.dumps(document(Storyboard(frames=(a,)), view.store.document_id)))
        legacy['version'] = 4
        legacy['frames'][0].pop('sequence')
        self.assertEqual(parse_document(legacy)[0].frames, (a,))
        target = export_bundle(view.board, view.store, self.root / 'Sequence.koma')
        restored_store = StoryboardStore(self.root / 'restored-sequence')
        restored_board = restore_bundle(target, restored_store)
        self.assertEqual(restored_board, view.board)
        self.assertTrue((restored_store.images / a.image).is_file())

    def test_duplicate_and_delete_remap_members_and_preserve_external_flow(self):
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        fixtures.finish(view.duplicate_frames({sequence.id}))
        other = next(frame for frame in view.board.frames if frame.sequence and frame.id != sequence.id)
        self.assertTrue(set(other.sequence.members).isdisjoint(sequence.sequence.members))
        self.assertEqual(len(other.sequence.members), 2)
        self.assertEqual(view.sequences.index.leaves((other.id,))[0].notes, a.notes)
        self.assertEqual([(frame.x, frame.y) for frame in view.sequences.index.leaves((other.id,))],
            [(a.x, a.y), (b.x, b.y)])
        fixtures.finish(view.graph.undo())
        view.confirm_remove_frames({sequence.id}, preserve_flow=True)
        self.assertEqual({frame.id for frame in view.board.frames}, {root.id, c.id})
        self.assertEqual(view.board.links, (StoryLink(root.id, c.id),))
        fixtures.finish(view.graph.undo())
        self.assertIn(a.id, view.sequences.index.nodes)

    def test_cross_project_clipboard_owns_assets_and_remaps_composition(self):
        source, root, a, b, c = self.project()
        sequence = self.create(source, a, b)
        payload = fixtures.finish(capture_selection(source.board, source.store, {sequence.id}))
        session = DocumentSession(self.root / 'destination')
        self.addCleanup(session.close)
        target = StoryboardView(Mock(), session, AppPreferences(self.root / 'destination'))
        fixtures.finish(target.activate())
        clipboard = NodeClipboard()
        clipboard.payload, clipboard.token = payload, 'sequence-copy'
        with patch.object(ft.Clipboard, 'get', new=AsyncMock(return_value=clipboard.token)):
            fixtures.finish(clipboard.paste(target))
        self.assertEqual(len(target.board.frames), 3)
        composite = next(frame for frame in target.board.frames if frame.sequence)
        children = target.sequences.index.leaves((composite.id,))
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0].drawing, a.drawing)
        self.assertEqual(children[0].notes, a.notes)
        self.assertEqual([(frame.x, frame.y) for frame in children], [(a.x, a.y), (b.x, b.y)])
        self.assertNotEqual(children[0].image, a.image)
        self.assertTrue((target.store.images / children[0].image).is_file())
        self.assertTrue({frame.id for frame in target.board.frames}.isdisjoint(frame.id for frame in source.board.frames))

    def test_empty_sequence_add_access_dissolve_and_nested_validation(self):
        view = self.view()
        fixtures.finish(view.add_node('sequence'))
        sequence = view.board.frames[0]
        self.assertEqual(view.sequences.index.total(sequence.id), 0)
        fixtures.finish(view.sequences.add_frame(sequence.id))
        node = view.sequences.index.nodes[sequence.id]
        self.assertTrue(node.sequence.collapsed)
        child = view.sequences.index.nodes[node.sequence.members[0]]
        fixtures.finish(view.sequences.access(sequence.id))
        self.assertEqual(view.workspace.scope.active, sequence.id)
        self.assertTrue(view.cards[child.id].content.visible)
        fixtures.finish(view.sequences.dissolve(sequence.id))
        self.assertEqual(view.board.frames, (child,))
        fixtures.finish(view.graph.undo())
        self.assertEqual(len(view.board.frames), 2)
        recursive = replace(node, sequence=SequenceState((node.id,)))
        with self.assertRaises(ValueError):
            replace(view.board, frames=(recursive, child)).validate()

    def test_group_movement_cancellation_and_nested_sequences_preserve_members(self):
        view, root, a, b, c = self.project()
        inner = self.create(view, a, b)
        outer = self.create(view, inner, c)
        self.assertEqual(view.sequences.index.total(outer.id), 6.5)
        self.assertEqual(view.sequences.index.representative(a.id), outer.id)
        fixtures.finish(view.sequences.access(outer.id))
        self.assertTrue(view.cards[inner.id].content.visible)
        self.assertFalse(view.cards[a.id].content.visible)
        ws = view.workspace
        fixtures.finish(ws.scope.back())
        ws.snap_enabled = False
        ws.navigation.select_node(outer.id)
        from types import SimpleNamespace as Data
        start = Data(global_position=Data(x=0, y=0))
        moved = Data(global_position=Data(x=48, y=48))
        before = view.board
        members = {outer.id}
        ws.begin_drag(outer.id, start)
        self.assertEqual(set(ws.drag.positions), members)
        ws.update_drag(outer.id, moved)
        ws.cancel_drag(outer.id)
        self.assertIs(view.board, before)
        ws.begin_drag(outer.id, start)
        ws.update_drag(outer.id, moved)
        fixtures.finish(ws.end_drag(outer.id))
        previous = {frame.id: frame for frame in before.frames}
        for frame in view.board.frames:
            expected = previous[frame.id]
            delta = 48 if frame.id in members else 0
            self.assertEqual((frame.x, frame.y), (expected.x + delta, expected.y + delta))
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)

    def test_internal_navigation_double_click_nested_path_and_escape_preserve_document(self):
        view, root, a, b, c = self.project()
        inner = self.create(view, a, b)
        outer = self.create(view, inner, c)
        ws = view.workspace
        board, history = view.board, tuple(view.history.past)
        cards = dict(view.cards)
        fixtures.finish(view.cards[outer.id].handle.on_double_tap(None))
        self.assertEqual(ws.scope.path, (outer.id,))
        self.assertEqual(ws.scope.visible, {inner.id, c.id})
        fixtures.finish(view.cards[inner.id].handle.on_double_tap(None))
        self.assertEqual(ws.scope.path, (outer.id, inner.id))
        self.assertEqual(ws.scope.visible, {a.id, b.id})
        ws.navigation.apply_selection({a.id, b.id})
        self.assertEqual(ws.navigation.selection.ids, {a.id, b.id})
        self.assertEqual(set(ws.links.cache).intersection(view.board.links), {StoryLink(a.id, b.id)})
        self.assertEqual(len(ws.sequence_ports.controls()), 2)
        fixtures.finish(ws.navigation.commands.execute(Action.CANCEL))
        self.assertEqual(ws.scope.active, outer.id)
        fixtures.finish(ws.scope.content.controls[0].on_click(None))
        self.assertIsNone(ws.scope.active)
        self.assertEqual(ws.scope.visible, {root.id, outer.id})
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), history)
        self.assertTrue(all(view.cards[key] is card for key, card in cards.items()))

    def test_add_duplicate_and_nested_group_inside_sequence_use_same_history_and_storage(self):
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        ws = view.workspace
        fixtures.finish(ws.scope.show(sequence.id))
        before = view.board
        fixtures.finish(view.add_frame())
        added = next(frame for frame in view.board.frames if frame.id not in {item.id for item in before.frames})
        self.assertEqual(view.sequences.index.parents[added.id], sequence.id)
        self.assertIn(StoryLink(b.id, added.id), view.board.links)
        self.assertIn(StoryLink(sequence.id, c.id), view.board.links)
        self.assertEqual(view.sequences.index.nodes[sequence.id].sequence.exit, added.id)
        self.assertTrue(view.cards[added.id].content.visible)
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertEqual(view.sequences.index.parents[added.id], sequence.id)
        fixtures.finish(view.duplicate_frames({added.id}))
        copy = next(frame for frame in view.board.frames if frame.id not in {item.id for item in before.frames} | {added.id})
        self.assertEqual(view.sequences.index.parents[copy.id], sequence.id)
        ws.navigation.apply_selection({a.id, b.id})
        fixtures.finish(view.add_node('sequence'))
        nested = next(frame for frame in view.board.frames if frame.sequence and frame.id != sequence.id)
        self.assertEqual(view.sequences.index.parents[nested.id], sequence.id)
        fixtures.finish(ws.scope.show(nested.id))
        self.assertEqual(ws.scope.visible, {a.id, b.id})
        fixtures.finish(view.graph.undo())
        self.assertEqual(ws.scope.active, sequence.id)
        self.assertEqual(view.store.load(), view.board)

    def test_organize_inside_sequence_preserves_outside_positions_and_media(self):
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        fixtures.finish(view.workspace.scope.show(sequence.id))
        before = view.board
        fixtures.finish(view.graph.organize())
        for frame in before.frames:
            changed = view.sequences.index.nodes[frame.id]
            if frame.id not in {a.id, b.id}:
                self.assertIs(changed, frame)
            self.assertEqual(changed.media, frame.media)
            self.assertEqual(changed.drawing, frame.drawing)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)

    def test_paste_inside_sequence_attaches_nodes_and_preserves_external_flow(self):
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        fixtures.finish(view.workspace.scope.show(sequence.id))
        payload = fixtures.finish(capture_selection(view.board, view.store, {c.id}))
        before, history = view.board, len(view.history.past)
        fixtures.finish(NodeClipboard().insert(view, payload))
        added = next(frame for frame in view.board.frames if frame.id not in {item.id for item in before.frames})
        self.assertEqual(view.sequences.index.parents[added.id], sequence.id)
        self.assertEqual(view.workspace.navigation.selected, added.id)
        self.assertIn(StoryLink(b.id, added.id), view.board.links)
        self.assertIn(StoryLink(sequence.id, c.id), view.board.links)
        self.assertEqual(view.sequences.index.nodes[sequence.id].sequence.exit, added.id)
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        self.assertTrue(view.cards[a.id].content.visible)

    def test_timeline_sequence_bands_and_properties_path_follow_owned_hierarchy(self):
        from types import SimpleNamespace as Data
        view, root, a, b, c = self.project()
        inner = self.create(view, a, b)
        outer = self.create(view, inner, c)
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        strip, timeline = player.strip, player.timeline
        lane = strip.sequence_lane
        self.assertEqual(lane.spans, ((inner.id, 0, 2), (outer.id, 2, 3)))
        inner_box, outer_box = lane.boxes[inner.id, 0], lane.boxes[outer.id, 2]
        self.assertEqual(inner_box.content.value, inner.title)
        self.assertIn(outer.title, inner_box.tooltip)
        self.assertAlmostEqual(inner_box.width, strip.scale.pixels(a.duration + b.duration))
        self.assertAlmostEqual(outer_box.left, inner_box.width)
        self.assertTrue(strip.sequence_label.visible)
        self.assertEqual(strip.audio_lane.content.top, strip.frames_top + strip.style.track_height)
        self.assertGreaterEqual(player.layout.timeline.height, strip.track.height)
        player.select_node(a.id)
        self.assertEqual(view.properties.scene_info.value, f'Scene_01 · Cena > {outer.title} > {inner.title} > shot_0001 · A')
        before, history = view.board, tuple(view.history.past)
        strip.zoom(2)
        player.position = 1
        player.render_position()
        self.assertIs(lane.boxes[inner.id, 0], inner_box)
        self.assertAlmostEqual(inner_box.width, strip.scale.pixels(a.duration + b.duration))
        self.assertIs(view.board, before)
        self.assertEqual(tuple(view.history.past), history)
        fixtures.finish(view.set_frame_properties(inner.id, title='Detalhes'))
        self.assertEqual(inner_box.content.value, 'Detalhes')
        self.assertIn('Detalhes > shot_0001 · A', view.properties.scene_info.value)
        fixtures.finish(view.graph.undo())
        self.assertEqual(inner_box.content.value, inner.title)

    def test_sequence_band_tracks_duration_preview_cancel_and_commit_without_rebuilding_membership(self):
        from types import SimpleNamespace as Data
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        strip, lane = player.strip, player.strip.sequence_lane
        band = lane.boxes[sequence.id, 0]
        width, source, before = band.width, lane.source, view.board
        token = player.duration_editor.begin(a.id, 0, strip.scale, ripple=True)
        player.duration_editor.move(token, strip.scale.pixels(.5))
        self.assertGreater(band.width, width)
        self.assertEqual(lane.source, source)
        self.assertIs(view.board, before)
        player.duration_editor.cancel()
        self.assertAlmostEqual(band.width, width)
        token = player.duration_editor.begin(a.id, 0, strip.scale, ripple=True)
        player.duration_editor.move(token, strip.scale.pixels(.5))
        fixtures.finish(player.duration_editor.finish(token))
        self.assertGreater(band.width, width)
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(view.graph.undo())
        self.assertAlmostEqual(band.width, width)

    def test_timeline_drop_outside_group_updates_membership_and_undo_restores_it(self):
        from koma.editor.timeline_order import reorder
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        view.player.open()
        before, history = view.board, tuple(view.history.past)
        with patch.object(view, 'notify') as notice:
            fixtures.finish(reorder(view.player, a.id, c.id, after=True, expected=(before, view.session)))
        self.assertNotIn(a.id, view.sequences.index.parents)
        self.assertEqual(view.sequences.index.nodes[sequence.id].sequence.members, (b.id,))
        self.assertEqual(tuple(frame.id for frame in view.player.timeline.frames), (b.id, c.id, a.id))
        self.assertEqual(len(view.history.past), len(history) + 1)
        self.assertEqual(view.store.load(), view.board)
        self.assertTrue(view.player.opened)
        notice.assert_not_called()
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)

    def test_shortcut_flow_endpoints_and_invalid_ranges_leave_original_data_safe(self):
        view, root, a, b, c = self.project()
        before = view.board
        view.workspace.navigation.apply_selection({a.id, c.id})
        fixtures.finish(view.workspace.navigation.commands.execute(Action.SEQUENCE))
        self.assertIs(view.board, before)
        sequence = self.create(view, a, b)
        disconnected = graph.disconnect(view.board, {StoryLink(root.id, a.id)})
        connected = graph.connect(disconnected, root.id, sequence.id)
        self.assertIn(StoryLink(root.id, sequence.id), connected.links)
        self.assertIn(StoryLink(sequence.id, c.id), connected.links)
        fixtures.finish(view.toggle_muted({sequence.id}))
        self.assertEqual(view.sequences.index.total(sequence.id), 0)
        self.assertEqual(Timeline(view.board, root.id).frames, (c,))
        fixtures.finish(view.toggle_muted({sequence.id}))
        self.assertEqual(view.sequences.index.total(sequence.id), 3.5)
        view.workspace.navigation.apply_selection({root.id, sequence.id})
        fixtures.finish(view.graph.disconnect_selected())
        self.assertEqual(view.board.links, (StoryLink(a.id, b.id),))

    def test_member_deletion_repairs_composition_and_internal_disconnect_is_safe(self):
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        before = view.board
        fixtures.finish(view.graph.cut({StoryLink(a.id, b.id)}))
        self.assertNotEqual(view.board, before)
        self.assertTrue(view.cards[sequence.id].flow_warning.visible)
        self.assertEqual(Timeline(view.board, root.id).frames, (c,))
        fixtures.finish(view.graph.undo())
        view.confirm_remove_frames({a.id})
        self.assertEqual(view.sequences.index.nodes[sequence.id].sequence.members, (b.id,))
        self.assertIn(StoryLink(root.id, sequence.id), view.board.links)
        self.assertEqual(view.sequences.index.total(sequence.id), b.duration)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)

    def test_group_interfaces_allow_disconnected_members_and_only_export_complete_path(self):
        from koma.editor.group_ports import GroupPort
        from koma.exports.pdf_export import export_pdf
        view, root, a, b, c = self.project()
        sequence = self.create(view, a, b)
        fixtures.finish(view.workspace.scope.show(sequence.id))
        fixtures.finish(view.graph.cut({StoryLink(a.id, b.id)}))
        self.assertEqual(view.sequences.index.nodes[sequence.id].sequence.members, (a.id, b.id))
        self.assertTrue(view.cards[sequence.id].flow_warning.visible)
        self.assertEqual(ExportSequence.from_project(view.board).frames, (c,))
        self.assertEqual(view.sequences.index.nodes[a.id].drawing, a.drawing)
        fixtures.finish(view.graph.connect(GroupPort(sequence.id), b.id))
        self.assertEqual(Timeline(view.board, root.id).frames, (b, c))
        self.assertFalse(view.cards[sequence.id].flow_warning.visible)
        fixtures.finish(view.graph.connect(a.id, GroupPort(sequence.id, True)))
        self.assertTrue(view.cards[sequence.id].flow_warning.visible)
        fixtures.finish(view.graph.connect(b.id, a.id))
        self.assertEqual(Timeline(view.board, root.id).frames, (b, a, c))
        self.assertFalse(view.cards[sequence.id].flow_warning.visible)
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(view.graph.undo())
        self.assertTrue(view.cards[sequence.id].flow_warning.visible)
        (view.store.images / a.image).unlink()
        exported = export_pdf(view.board, view.store, self.root / 'connected-only.pdf')
        self.assertTrue(exported.read_bytes().startswith(b'%PDF'))

    def test_format_six_migration_wraps_nested_boundaries_preserving_data_and_playback(self):
        view, root, a, b, c = self.project()
        inner = self.create(view, a, b)
        outer = self.create(view, inner, c)
        raw = json.loads(json.dumps(document(view.board, view.store.document_id)))
        raw['version'] = 6
        for frame in raw['frames']:
            if frame['sequence']:
                frame['sequence'].pop('entry')
                frame['sequence'].pop('exit')
        raw['links'] = [{'source': x.id, 'target': y.id} for x, y in zip((root, a, b), (a, b, c))]
        snapshot = json.dumps(raw, sort_keys=True)
        migrated, _ = parse_document(raw)
        self.assertEqual(json.dumps(raw, sort_keys=True), snapshot)
        self.assertEqual(Timeline(migrated, root.id).frames, (a, b, c))
        index = SequenceIndex(migrated)
        self.assertEqual(index.nodes[inner.id].sequence.entry, a.id)
        self.assertEqual(index.nodes[outer.id].sequence.entry, inner.id)
        self.assertIn(StoryLink(root.id, outer.id), migrated.links)
        self.assertIn(StoryLink(inner.id, c.id), migrated.links)
        self.assertEqual(index.nodes[a.id], a)
        self.assertEqual(parse_document(json.loads(json.dumps(document(migrated, view.store.document_id))))[0], migrated)

    def test_interface_drag_uses_existing_connection_gestures_and_incomplete_nested_group_warns(self):
        from types import SimpleNamespace as Data
        from koma.editor.group_ports import GroupPort
        view, root, a, b, c = self.project()
        inner = self.create(view, a, b)
        outer = self.create(view, inner, c)
        fixtures.finish(view.workspace.scope.show(inner.id))
        links = view.workspace.links
        ref = GroupPort(inner.id)
        source = links.port(ref, True)
        endpoint = links.port(b.id, False)
        links.drag_begin(ref, Data(global_position=Data(x=0, y=0), local_position=Data(x=6, y=6)))
        links.drag_update(Data(global_position=Data(x=endpoint[0] - source[0], y=endpoint[1] - source[1])))
        fixtures.finish(links.drag_end())
        self.assertEqual(view.sequences.index.nodes[inner.id].sequence.entry, b.id)
        self.assertEqual(Timeline(view.board, root.id).frames, (b, c))
        edge = next(edge for edge in links.cache if isinstance(edge.source, GroupPort))
        view.player.open()
        view.player.subtitles.content.visible = True
        fixtures.finish(view.graph.cut({edge}))
        self.assertTrue(view.cards[inner.id].flow_warning.visible)
        self.assertTrue(view.cards[outer.id].flow_warning.visible)
        self.assertFalse(Timeline(view.board, root.id).frames)
        self.assertFalse(ExportSequence.from_project(view.board).frames)
        self.assertFalse(view.player.subtitles.content.visible)
        self.assertTrue(view.player.play.disabled)
