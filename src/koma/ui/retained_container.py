"""Retain unchanged widget bodies during gestures using Flet update isolation."""
import flet as ft
import flet.canvas as cv
from contextlib import contextmanager


class _RetainedUpdates:
    def __init__(self, *, hold_updates, **kwargs):
        super().__init__(**kwargs)
        self._hold_updates = hold_updates
        self._retention_depth = 0

    def is_isolated(self):
        # Explicit updates to this control still work. Parent updates skip its
        # descendants only while the caller guarantees their content is stable.
        return self._retention_depth > 0 or bool(self._hold_updates())


class RetainedContainer(_RetainedUpdates, ft.Container):
    pass


class RetainedStack(_RetainedUpdates, ft.Stack):
    pass


class RetainedColumn(_RetainedUpdates, ft.Column):
    pass


class RetainedCanvas(_RetainedUpdates, cv.Canvas):
    pass


@contextmanager
def retain_children(*controls):
    """Skip stable descendants for one synchronous patch, then restore normal updates.

    Boundaries must be descendants of the updated root. Their own layout and
    visibility still update; changed content must be updated outside this scope.
    """
    for control in controls:
        control._retention_depth += 1
    try:
        yield
    finally:
        for control in controls:
            control._retention_depth -= 1
