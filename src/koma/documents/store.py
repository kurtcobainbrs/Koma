"""Manifesto versionado e área de trabalho; não lê formatos do Akira."""

import json
import re
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from koma.editor.models import MAX_CARDS, Storyboard, StoryFrame, StoryLink, StoryGroup
from koma.paths import atomic_json
from koma.editor.media_models import AudioTrack, TimelineMarker, MAX_AUDIO_TRACKS, MAX_MARKERS
from koma.editor.frame_format import FrameFormat
from koma.editor.drawing_models import DrawingLayer
from koma.editor.sequence_models import SequenceState
from koma.editor.node_media import NodeMedia, MediaTransform, MAX_MEDIA_ITEMS

DOCUMENT_VERSION = 14


def document(board, document_id):
    board.validate()
    return {'format': 'koma', 'version': DOCUMENT_VERSION, 'document_id': document_id, **asdict(board)}


def parse_document(raw):
    try:
        if not isinstance(raw, dict) or raw.get('format') != 'koma' or type(raw.get('version')) is not int or raw['version'] not in range(1, DOCUMENT_VERSION + 1):
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
        tracks, markers = raw.get('audio_tracks', []), raw.get('markers', [])
        if any(not isinstance(items, list) or len(items) > limit for items, limit in
                ((tracks, MAX_AUDIO_TRACKS), (markers, MAX_MARKERS))):
            raise ValueError('Lista de trilhas ou marcadores inválida.')
        parsed_frames = []
        for frame in frames:
            if not isinstance(frame, dict):
                raise ValueError('Quadro inválido.')
            values = dict(frame)
            if raw['version'] >= 7 and values.get('sequence') is not None:
                if not {'entry', 'exit'} <= values['sequence'].keys():
                    raise ValueError('A sequência não informa sua Entrada e Saída.')
            entries = values.pop('media', [])
            if not isinstance(entries, list) or len(entries) > MAX_MEDIA_ITEMS:
                raise ValueError('Lista de mídias inválida.')
            if entries:
                values['media'] = tuple(NodeMedia.from_document(entry) for entry in entries)
            from koma.editor.media_animation import animation_from_document
            values['image_defaults'] = MediaTransform(**animation_from_document(values.pop('image_defaults', {})))
            values['drawing'] = DrawingLayer.from_document(values.pop('drawing', {}))
            from koma.editor.camera_models import CameraMotion
            values['camera'] = CameraMotion.from_document(values.pop('camera', {}) if raw['version'] >= 9 else {})
            values['sequence'] = SequenceState.from_document(values.pop('sequence', None), MAX_CARDS)
            parsed_frames.append(StoryFrame(**values))
        from koma.editor.reference_models import ReferenceImage, MAX_REFERENCES
        references = raw.get('references', []) if raw['version'] >= 8 else []
        if not isinstance(references, list) or len(references) > MAX_REFERENCES:
            raise ValueError('Lista de referências inválida.')
        board = Storyboard(raw['title'], tuple(parsed_frames),
            tuple(StoryLink(**link) for link in links),
            tuple(StoryGroup(group['id'], group['title'], tuple(group['members'])) for group in groups),
            fps=raw.get('fps', 24), audio_tracks=tuple(AudioTrack(**track) for track in tracks),
            markers=tuple(TimelineMarker(**marker) for marker in markers),
            frame_format=FrameFormat(**raw.get('frame_format', {})),
            references=tuple(ReferenceImage.from_document(item, raw['version']) for item in references),
            media_filter=raw['media_filter'] if raw['version'] >= 10 else 'none')
        if raw['version'] < 7:
            from koma.documents.sequence_migration import migrate_sequences
            board = migrate_sequences(board)
        if raw['version'] < 12:
            from koma.documents.audio_migration import migrate_project_audio
            board = migrate_project_audio(board)
        board.validate()
        return board, identifier
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f'Não foi possível ler o documento Koma: {exc}') from exc


class StoryboardStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'manifest.json'
        self.images = self.directory / 'images'
        self.videos = self.directory / 'videos'
        self.thumbnails = self.directory / 'thumbnails'
        self.audio = self.directory / 'audio'
        self.waveforms = self.directory / 'waveforms'
        self.document_id = uuid4().hex

    def load(self):
        board, identifier = parse_document(json.loads(self.path.read_text(encoding='utf-8')))
        self.document_id = identifier
        return board

    def save(self, board):
        atomic_json(self.path, document(board, self.document_id))
