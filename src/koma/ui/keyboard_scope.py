"""Dialog ownership shared by page shortcuts and workspace keyboard listeners."""
import flet as ft
from flet.controls.dialog_control import DialogControl


def dialog_owns_keyboard(page):
    # Flet 1.0.5 keeps dialogs here until dismissal completes. Read the open
    # flags directly so closing/nested dialogs need no parallel state tracker.
    controls = getattr(getattr(page, '_dialogs', None), 'controls', ())
    if not isinstance(controls, (list, tuple)):
        return False
    return any(isinstance(item, DialogControl) and item.open
        and not isinstance(item, (ft.SnackBar, ft.Banner)) for item in controls)
