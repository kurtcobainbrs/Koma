"""Insertion icons follow capabilities from the shared node catalog."""
import flet as ft


def node_icon(spec):
    if spec.contains_frames:
        return ft.Icons.VIEW_TIMELINE_OUTLINED
    return ft.Icons.MOVIE_OUTLINED if spec.starts_scene else ft.Icons.ADD
