"""Staged global preferences: confirm once, never mutate document data."""
from dataclasses import dataclass
import flet as ft
from koma.preference_catalog import CATEGORIES, defaults
from koma.ui.design import (dialog, input_style, APP_PADDING, PAGE_PADDING,
    CONTROL_HEIGHT, MUTED, BORDER, SURFACE, SELECTION, RADIUS)
from koma.ui.typography import TEXT_BODY, TEXT_SMALL, FONT_HEADING
from koma.ui.event_updates import explicit_updates
from koma.ui.preference_input import preference_input
from koma.ui.form_layout import FORM_LAYOUT, form_row


@dataclass(frozen=True)
class PreferencesLayout:
    width: int = 850
    height: int = 600
    sidebar: int = 200
    sample_height: int = FORM_LAYOUT.sample_height
    sample_font_scale: float = 3
    window_margin: int = 100


LAYOUT = PreferencesLayout()


class PreferencesPanel:
    def __init__(self, view):
        self.view, self.page = view, view.page
        self.store = view.settings.configuration
        self.shortcut_values = {action.id: '; '.join(view.keymap.bindings(action.id))
            for action in view.keymap.actions.values()}
        self.values = defaults()
        self.category = CATEGORIES[0]
        self.controls, self.buttons, self.group_examples = {}, {}, {}
        self.preview = ft.Container(height=LAYOUT.sample_height, padding=PAGE_PADDING,
            border=ft.Border.all(1, BORDER))
        self.status = ft.Text(size=TEXT_SMALL, color=ft.Colors.ERROR, visible=False)
        self.fields = ft.Column(spacing=FORM_LAYOUT.spacing, scroll=ft.ScrollMode.AUTO, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.heading = ft.Text(font_family=FONT_HEADING, size=TEXT_BODY)
        section = ft.Column([ft.Row([self.heading, ft.Container(expand=True),
            ft.TextButton('Restaurar seção', height=FORM_LAYOUT.row_height, on_click=self.reset)]),
            self.fields, self.status], spacing=FORM_LAYOUT.spacing, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        navigation = []
        for category in CATEGORIES:
            def choose(e, target=category):
                self.select(target)
            button = ft.TextButton(category.label, on_click=choose, height=FORM_LAYOUT.row_height,
                style=ft.ButtonStyle(alignment=ft.Alignment.CENTER_LEFT,
                    animation_duration=0, padding=PAGE_PADDING), expand=True)
            self.buttons[category.key] = button
            navigation.append(ft.Row([button]))
        navigation = ft.Column(navigation, spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        width = min(LAYOUT.width, max(1, (self.page.width or LAYOUT.width + LAYOUT.window_margin) - LAYOUT.window_margin))
        height = min(LAYOUT.height, max(1, (self.page.height or LAYOUT.height + LAYOUT.window_margin) - LAYOUT.window_margin))
        self.body = ft.Container(width=width, height=height, content=ft.Column([
            ft.Text('Configurações do programa · não alteram os dados dos projetos.',
                size=TEXT_SMALL, color=MUTED),
            ft.Row([ft.Container(width=LAYOUT.sidebar, content=navigation),
                ft.VerticalDivider(width=1, color=BORDER),
                ft.Container(expand=True, padding=APP_PADDING, content=section)],
                expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)], spacing=APP_PADDING))
        self.popup = dialog(title=ft.Text('Preferências'), content=self.body,
            on_confirm=self.save, on_cancel=self.cancel, actions=[
                ft.TextButton('Cancelar', on_click=self.cancel),
                ft.FilledButton('Aplicar', on_click=self.save)])

    async def open(self, e=None):
        if self.view.player.editing:
            self.view.notify('Conclua ou cancele o ajuste atual.', 'info')
            return
        self.view.player.pause_for_edit()
        self.values = self.store.editable()
        if not self.store.path.exists():
            from koma.preference_draft import PreferenceDraft
            prototype = PreferenceDraft(self.view.settings.directory)
            if prototype.path.exists():
                import asyncio
                self.values = await asyncio.to_thread(prototype.read)
        self.select(self.category, publish=False)
        self.page.show_dialog(self.popup)

    def collect(self):
        if self.category.presentation == 'shortcuts':
            self.shortcut_values.update({key: control.value for key, control in self.controls.items()})
            return True
        valid = True
        for field in self.category.fields:
            control = self.controls[field.key]
            try:
                self.values[self.category.key][field.key] = field.parse(control.value)
                if hasattr(control, 'error_text'):
                    control.error_text = None
            except ValueError as error:
                control.error_text = str(error)
                valid = False
        return valid

    @explicit_updates
    def changed(self, e=None):
        if self.collect():
            self.sample()
        self.page.update(self.fields, self.preview)

    @explicit_updates
    def select(self, category, *, publish=True):
        if self.controls and not self.collect():
            if publish:
                self.page.update(self.fields)
            return
        self.category, self.controls, self.group_examples = category, {}, {}
        self.heading.value = category.label
        self.status.visible = False
        rows = []
        groups = {}
        boolean_row = None
        for field in category.fields:
            value = self.values[category.key][field.key]
            control, presented = preference_input(self.page, field, value,
                on_change=self.changed, on_submit=self.save)
            self.controls[field.key] = control
            if field.group:
                boolean_row = None
                if field.group not in groups:
                    group_fields = ft.Column([ft.Text(field.group, font_family=FONT_HEADING, size=TEXT_BODY)],
                        spacing=FORM_LAYOUT.spacing, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
                    groups[field.group] = group_fields
                    rows.append(ft.Container(padding=APP_PADDING, border=ft.Border.all(1, BORDER),
                        border_radius=RADIUS, content=group_fields))
                groups[field.group].controls.append(presented)
            else:
                if field.kind == 'bool':
                    if boolean_row is None or len(boolean_row.controls) == 2:
                        boolean_row = ft.Row(spacing=APP_PADDING)
                        rows.append(boolean_row)
                    boolean_row.controls.append(ft.Container(content=control,
                        height=FORM_LAYOUT.row_height, expand=True))
                else:
                    boolean_row = None
                    rows.append(presented)
        if category.sample == 'identity':
            examples = {key: ft.Text(size=TEXT_SMALL, color=MUTED) for key in groups}
            for key, group_fields in groups.items():
                group_fields.controls.append(examples[key])
            self.group_examples = {field.key: examples[field.group] for field in category.fields if field.group}
        if category.presentation == 'shortcuts':
            rows = [ft.Text('Separe combinações com ponto e vírgula.', size=TEXT_SMALL, color=MUTED)]
            rows.append(form_row('Mover a vista', ft.Text('Arraste com o botão direito', size=TEXT_SMALL)))
            for action in self.view.keymap.actions.values():
                control = ft.TextField(value=self.shortcut_values[action.id],
                    width=FORM_LAYOUT.text_width, on_submit=self.save, **input_style(FORM_LAYOUT.row_height))
                self.controls[action.id] = control
                rows.append(form_row(action.label, control))
        self.fields.controls = [*rows, self.preview]
        actions = ([(category.action_key, category.action)] if category.action else []) + list(category.secondary_actions)
        if actions:
            buttons = []
            for command, label in actions:
                async def run(e, action=command):
                    await self.action(e, action=action)
                buttons.append(ft.OutlinedButton(label, height=FORM_LAYOUT.row_height, on_click=run))
            self.fields.controls.append(ft.Row(buttons, spacing=APP_PADDING, wrap=True))
        for key, button in self.buttons.items():
            button.style.bgcolor = SELECTION if key == category.key else ft.Colors.TRANSPARENT
        self.sample()
        if publish:
            self.page.update(self.body)

    def sample(self):
        key = self.category.sample
        values = self.values[self.category.key]
        self.preview.visible = bool(key)
        if not self.preview.visible:
            return
        self.preview.height = LAYOUT.sample_height if key in ('subtitles', 'reference', 'appearance') else CONTROL_HEIGHT * 2
        self.preview.bgcolor = SURFACE
        if key == 'identity':
            self.preview.visible = False
            for prefix in ('scene', 'shot'):
                example = f'{values[prefix + "_prefix"]}{1:0{values[prefix + "_digits"]}d}{values[prefix + "_suffix"]}'
                self.group_examples[prefix + '_prefix'].value = f'Exemplo: {example}'
            return
        elif key == 'numbers':
            example = f'Frame: {9:0{values["counter_digits"]}d} · {2.5:.{values["seconds_decimals"]}f} s'
        elif key == 'projects':
            example = f'{values["width"]} × {values["height"]} · {values["fps"]} FPS'
        elif key == 'appearance':
            self.preview.bgcolor = values['preview']
            self.preview.content = ft.Row([ft.Icon(ft.Icons.TUNE, color=values['accent']),
                ft.Text('Cor de destaque', color=values['accent'], size=TEXT_BODY)], spacing=APP_PADDING)
            return
        else:
            from koma.editor.production_numbers import scene_code, shot_code
            identity = self.values['identity']
            example = 'Uma legenda de exemplo' if key == 'subtitles' else f'{scene_code(1, identity)} · {shot_code(1, identity)} · Frame: 0009'
            label = ft.Text(example, color=values['color'], size=values['size'] * LAYOUT.sample_font_scale,
                font_family=values['font'], max_lines=2)
            alignments = {'Esquerda': ft.Alignment.CENTER_LEFT, 'Centro': ft.Alignment.CENTER,
                'Direita': ft.Alignment.CENTER_RIGHT}
            strip = ft.Container(padding=APP_PADDING,
                bgcolor=ft.Colors.with_opacity(values['opacity'] / 100, values['background']), content=label,
                alignment=alignments[values['align']])
            self.preview.content = ft.Container(content=strip,
                padding=values['margin'] * LAYOUT.sample_height / 100,
                alignment=ft.Alignment.TOP_CENTER if values['position'] == 'Em cima' else ft.Alignment.BOTTOM_CENTER)
            return
        self.preview.content = ft.Text(example, size=TEXT_BODY)

    @explicit_updates
    def reset(self, e=None):
        self.values[self.category.key] = defaults()[self.category.key]
        if self.category.presentation == 'shortcuts':
            from koma.keymap import Keymap
            keymap = Keymap(self.view.keymap.actions.values())
            self.shortcut_values = {key: '; '.join(keymap.bindings(key)) for key in keymap.actions}
        self.controls = {}
        self.select(self.category)

    async def save(self, e=None):
        if not self.collect():
            self.page.update(self.fields)
            return
        try:
            from koma.keymap import Keymap
            keymap = Keymap(self.view.keymap.actions.values())
            keymap.configure({key: tuple(part.strip() for part in text.split(';') if part.strip())
                for key, text in self.shortcut_values.items()})
            await self.store.commit(self.values)
        except (OSError, ValueError) as error:
            self.status.value = str(error) if isinstance(error, ValueError) else 'Não foi possível salvar as preferências.'
            self.status.visible = True
            self.page.update(self.status)
            return
        if any(self.view.keymap.bindings(key) != keymap.bindings(key) for key in keymap.actions):
            self.view.keymap.configure(keymap.overrides)
        self.page.pop_dialog()

    async def action(self, e=None, *, action=None):
        action = action or self.category.action_key
        if action == 'restore_confirmations':
            self.reset()
            return
        from koma.editor.preference_actions import perform
        try:
            await perform(self.view, action)
        except (OSError, ValueError):
            self.view.notify('Não foi possível concluir a ação.', 'warning')

    def cancel(self, e=None):
        self.page.pop_dialog()
