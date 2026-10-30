"""Explicit group-interface references and derived connections."""
from dataclasses import dataclass


@dataclass(frozen=True)
class GroupPort:
    group: str
    output: bool = False


@dataclass(frozen=True)
class PortLink:
    source: str | GroupPort
    target: str | GroupPort
