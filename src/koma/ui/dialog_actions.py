"""Explicit dialog actions shared by mouse buttons, Enter and Escape."""
from inspect import isawaitable
from typing import Optional
import flet as ft
from flet.controls.base_control import control
from flet.controls.control_event import ControlEventHandler
from koma.ui import drop_runtime


@control('koma_dialog')
class ActionDialog(ft.AlertDialog):
    on_confirm: Optional[ControlEventHandler] = None
    on_cancel: Optional[ControlEventHandler] = None
    on_outside: Optional[ControlEventHandler] = None


def close_dialog(e):
    e.control.page.pop_dialog()


def action_dialog(*, on_confirm=None, on_cancel=None, on_outside=None, native_actions=True, bind_fields=True, **kwargs):
    if not native_actions:
        return ft.AlertDialog(**kwargs)
    confirm = close_dialog if on_confirm is None else on_confirm
    cancel = close_dialog if on_cancel is None else on_cancel
    outside = cancel if on_outside is None else on_outside
    popup = ActionDialog(**kwargs) if drop_runtime.enabled() else ft.AlertDialog(**kwargs)
    running = False
    def guarded(handler):
        async def invoke(e):
            nonlocal running
            if running or not popup.open or handler is False:
                return
            running = True
            try:
                result = handler(e)
                if isawaitable(result):
                    await result
            finally:
                running = False
        return invoke
    accept, reject, dismiss = guarded(confirm), guarded(cancel), guarded(outside)
    if isinstance(popup, ActionDialog):
        popup.on_confirm, popup.on_cancel, popup.on_outside = accept, reject, dismiss
    def bind(control):
        if isinstance(control, ft.TextField):
            if not control.multiline:
                control.on_submit = accept
            return
        for child in getattr(control, 'controls', None) or []:
            bind(child)
        child = getattr(control, 'content', None)
        if isinstance(child, ft.Control):
            bind(child)
    if bind_fields and popup.content is not None:
        bind(popup.content)
    for button in popup.actions:
        handler = getattr(button, 'on_click', None)
        if handler == confirm:
            button.on_click = accept
        elif handler == cancel:
            button.on_click = reject
    return popup
