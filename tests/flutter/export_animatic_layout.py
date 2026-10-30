"""Export the production workspace layout for the native geometry regression."""
import json
from pathlib import Path
from types import SimpleNamespace as Data
from unittest.mock import Mock, patch
import flet as ft
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack
from koma.ui.animatic_workspace import AnimaticWorkspace
from koma.editor.work_modes import WorkModes
from koma.ui.timeline_strip import TimelineStyle
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.documents.session import DocumentSession
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.view import StoryboardView
from koma.preferences import AppPreferences
from tests.test_storyboard import finish, immediate


def serialize(control):
    encoder = configure_encode_object_for_msgpack(BaseControl)
    patch, _, _ = ObjectPatch.from_diff(None, control, BaseControl)
    return msgpack.unpackb(msgpack.packb(patch.to_message(), default=encoder), raw=False)[1][3]


def production(directory):
    session = DocumentSession(directory / 'layout-document')
    scene, frame = StoryFrame(kind='main', title='Cena 01', x=0, y=0), StoryFrame(title='Corredor', x=400, y=0)
    session.board = Storyboard(frames=(scene, frame), links=(StoryLink(scene.id, frame.id),))
    view = StoryboardView(Mock(width=1600, height=900), session, AppPreferences(directory))
    with patch('asyncio.to_thread', side_effect=immediate):
        finish(view.activate())
    view.workspace.navigation.apply_selection({frame.id}, frame.id)
    cards, ports = [], []
    for index, card in enumerate(view.cards.values()):
        card.box.key = f'card-{index}'
        card.output_socket.key = f'output-{index}'
        cards.append(ft.Container(width=card.width, content=card.box))
        bounds = view.workspace.links.bounds(card.identifier)
        port = view.workspace.links.port(card.identifier, True, bounds=bounds)
        ports.append([port[0] - bounds[0], port[1] - bounds[1]])
    card_tree = serialize(ft.Row(cards, vertical_alignment=ft.CrossAxisAlignment.START))
    view.player.open()
    view.player.strip.resized(Data(width=1504))
    view.player.preview_slot.key = 'real-preview'
    workspace = serialize(view.work_modes.content)
    mode_ids = {'animatic': view.work_modes.animatic._i,
        'timeline': view.player.layout.timeline._i, 'splitter': view.player.layout.splitter.content._i}
    session.close()
    return {'cards': card_tree, 'ports': ports, 'workspace': workspace, 'mode_ids': mode_ids}


def export(destination):
    style = TimelineStyle()
    track_height = style.frames_top + style.track_height + style.audio_height
    player = Data(view=Data(page=Mock()), key_up=lambda event: None,
        controls=ft.Container(height=28),
        preview_slot=ft.Container(key='preview', content=ft.Container(aspect_ratio=16 / 9, bgcolor='#304E67')),
        strip=Data(track=Data(height=track_height), content=ft.Container(height=track_height + 32)))
    layout = AnimaticWorkspace(player, ft.Container(key='header', height=28))
    layout.timeline.key = 'timeline'
    player.surface, player.layout = layout.content, layout
    view = Data(player=player, board_area=ft.InteractiveViewer(expand=True, content=ft.Container(
            key='canvas-hit', width=200, height=200, bgcolor='#222222')),
        properties_splitter=Data(content=ft.Container(width=4)),
        properties=Data(content=ft.Container(key='inspector', width=WORKSPACE_STYLE.inspector_width),
            reopen_rail=ft.Container(visible=False)))
    modes = WorkModes(view)
    modes.canvas.key, modes.animatic.key = 'canvas-mode', 'animatic-mode'
    modes.center.key = 'mode-stack'
    modes.set_visibility(True)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({'control': serialize(modes.content), 'timeline_height': layout.timeline.height,
        'mode_ids': {'canvas': modes.canvas._i, 'animatic': modes.animatic._i, 'center': modes.center._i},
        'production': production(destination.parent)}), encoding='utf-8')


if __name__ == '__main__':
    export(Path(__file__).resolve().parents[2] / 'build/workflow-checks/animatic-layout.json')
