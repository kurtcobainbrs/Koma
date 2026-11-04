"""Event contract for interactions that publish their own local UI updates."""
from functools import wraps
from inspect import iscoroutinefunction, isawaitable

import flet as ft


def action_event(action, *args, **kwargs):
    """Bind a parameterized command to Flet and await its completion if needed.

    The UI event is deliberately not passed to the command. Arguments express
    the operation explicitly, including keyword-only command parameters.
    """
    async def invoke(e=None):
        result = action(*args, **kwargs)
        return await result if isawaitable(result) else result
    return invoke


def explicit_updates(handler):
    """Keep no-op/input-only events from triggering Flet's ancestor auto-diff.

    Flet resets this policy for each dispatched event. Visual changes remain
    the handler's responsibility, through the existing local update methods.
    Preserve async handlers so Flet continues to await them correctly.
    """
    if iscoroutinefunction(handler):
        @wraps(handler)
        async def asynchronous(*args, **kwargs):
            ft.context.reset_auto_update()
            ft.context.disable_auto_update()
            return await handler(*args, **kwargs)
        return asynchronous

    @wraps(handler)
    def synchronous(*args, **kwargs):
        # Controllers also call these methods outside event dispatch (startup,
        # cancellation). Create a local policy rather than mutating the default.
        ft.context.reset_auto_update()
        ft.context.disable_auto_update()
        return handler(*args, **kwargs)
    return synchronous
