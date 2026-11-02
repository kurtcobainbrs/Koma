"""Apply confirmed global presentation once, without writing document/history data."""
from dataclasses import replace
import flet as ft
from koma.editor.geometry import WHEEL_ZOOM_FACTOR
from koma.exports.reference_overlay import REFERENCE_FIELDS


class PreferenceBindings:
    def __init__(self, view):
        self.view = view
        self.revision = -1
        self.previous = None
        view.settings.configuration.listeners.append(self.changed)

    def changed(self, previous, current):
        fields = tuple(key for key in REFERENCE_FIELDS if current['reference'][key])
        self.view.preferences.options = replace(self.view.preferences.options, reference_fields=fields)
        if self.view.active and self.view.loaded and not self.view.closing:
            self.apply()

    def apply(self):
        view = self.view
        config = view.settings.configuration
        if self.revision == config.revision:
            return
        values = config.values
        changed = {key for key in values if self.previous is None or self.previous[key] != values[key]}
        from koma.preview_cache import PREVIEW_BUDGET_SHARES
        view.settings.preview_cache.resize(values['system']['cache'] / PREVIEW_BUDGET_SHARES)
        ws, player = view.workspace, view.player
        if self.previous is not None and self.previous['system']['cache'] != values['system']['cache']:
            player.media.waveforms.clear()
        if 'animatic' in changed:
            player.preview_navigation.configure()
            player.strip.configure_navigation()
            player.layout.sidebar.configure()
            player.layout.scene_splitter.content.visible = player.layout.sidebar.content.visible
        if changed == {'appearance'} and self.previous is not None:
            differences = {key for key in values['appearance']
                if self.previous['appearance'][key] != values['appearance'][key]}
            if differences == {'selection'}:
                color = values['appearance']['selection']
                ws.box_selection.overlay.bgcolor = ft.Colors.with_opacity(.14, color)
                ws.box_selection.overlay.border = ft.Border.all(1, color)
                controls = [ws.box_selection.overlay]
                selection = ws.navigation.selection
                for identifier in selection.ids:
                    card = view.cards.get(identifier)
                    if card:
                        card.paint(True, identifier == selection.active)
                        controls.append(card.box)
                if player.opened:
                    player.strip.marker_lane.sync()
                    controls.append(player.strip.marker_lane.content)
                self.revision, self.previous = config.revision, values
                if view.active:
                    from koma.ui.retained_container import retain_children
                    with retain_children(*(view.cards[key].box.content for key in selection.ids if key in view.cards)):
                        view.page.update(*controls)
                return
        if changed == {'reference'}:
            self.revision, self.previous = config.revision, values
            player.reference_presentation.refresh()
            return
        ws.content.bgcolor = values['appearance']['canvas']
        ws.viewer.scale_factor = WHEEL_ZOOM_FACTOR / values['canvas']['zoom']
        if changed & {'appearance', 'canvas'}:
            ws.grid_size = None
        ws.box_selection.overlay.bgcolor = ft.Colors.with_opacity(.14, values['appearance']['selection'])
        ws.box_selection.overlay.border = ft.Border.all(1, values['appearance']['selection'])
        player.screen.bgcolor = values['appearance']['preview']
        player.preview.content.bgcolor = values['appearance']['preview']
        if 'timeline' in changed:
            player.marker_editor.snap_enabled = values['timeline']['snap']
        player.audio_transport.volume = values['timeline']['volume'] / 100
        drawing = values['drawing']
        if self.previous is None or self.previous['drawing'] != drawing:
            player.drawing.color, player.drawing.width = drawing['color'], drawing['width']
        fields = tuple(key for key in REFERENCE_FIELDS if values['reference'][key])
        view.preferences.options = replace(view.preferences.options, reference_fields=fields)
        if 'subtitles' in changed:
            player.subtitles.clear()
            player.subtitles.cache.clear()
        quality_changed = self.previous is None or self.previous['system']['quality'] != values['system']['quality']
        if quality_changed:
            player.video_preview.clear()
        if 'timeline' in changed:
            player.strip.ruler_key = None
        if 'identity' in changed:
            player.scenes_key = None
        refresh_nodes = bool(changed & {'identity', 'appearance', 'canvas'}) or quality_changed
        if refresh_nodes:
            for card in view.cards.values():
                card.sync_key = None
        self.revision = config.revision
        self.previous = values
        if view.loaded:
            if refresh_nodes:
                view.refresh()
            refresh_player = player.opened and (refresh_nodes or bool(changed & {'subtitles', 'timeline', 'reference', 'animatic'}))
            if refresh_player:
                player.current = -1
                player.render(update=False)
            if view.active:
                if refresh_nodes:
                    view.page.update(view.content)
                elif refresh_player:
                    view.page.update(player.content, player.layout.timeline)
                elif 'drawing' in changed:
                    player.drawing_surface.refresh()

    def close(self):
        listeners = self.view.settings.configuration.listeners
        if self.changed in listeners:
            listeners.remove(self.changed)
