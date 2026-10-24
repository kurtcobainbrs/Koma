"""Manifesto versionado e área de trabalho; não lê formatos do Akira."""

import json
import re
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from koma.editor.models import MAX_CARDS, Storyboard, StoryFrame, StoryLink, StoryGroup
from koma.paths import atomic_json

DOCUMENT_VERSION = 1


def document(board, document_id):
    board.validate()
    return {'format': 'koma', 'version': DOCUMENT_VERSION, 'document_id': document_id, **asdict(board)}


def parse_document(raw):
    try:
        if not isinstance(raw, dict) or raw.get('format') != 'koma' or type(raw.get('version')) is not int or raw['version'] != DOCUMENT_VERSION:
            raise ValueError('Formato ou versão Koma não reconhecidos.')
        identifier = raw['document_id']
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{32}', identifier):
            raise ValueError('Identificador de documento inválido.')
        frames, links, groups = raw['frames'], raw['links'], raw['groups']
        if any(not isinstance(items, list) or len(items) > MAX_CARDS for items in (frames, links, groups)):
            raise ValueError('Lista de nodes, ligações ou grupos inválida.')
        if any(not isinstance(group, dict) or not isinstance(group.get('members'), list)
               or len(group['members']) > MAX_CARDS for group in groups):
            raise ValueError('Membros de grupo inválidos.')
        board = Storyboard(raw['title'], tuple(StoryFrame(**frame) for frame in frames),
            tuple(StoryLink(**link) for link in links),
            tuple(StoryGroup(group['id'], group['title'], tuple(group['members'])) for group in groups))
        board.validate()
        return board, identifier
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f'Não foi possível ler o documento Koma: {exc}') from exc


class StoryboardStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'manifest.json'
        self.images = self.directory / 'images'
        self.thumbnails = self.directory / 'thumbnails'
        self.document_id = uuid4().hex

    def load(self):
        board, identifier = parse_document(json.loads(self.path.read_text(encoding='utf-8')))
        self.document_id = identifier
        return board

    def save(self, board):
        atomic_json(self.path, document(board, self.document_id))
