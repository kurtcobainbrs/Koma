"""Declarative global preferences: one catalog of fields, groups and validation."""
from dataclasses import dataclass, replace
import math
import re


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    default: object
    kind: str = 'text'
    choices: tuple = ()
    minimum: float = 0
    maximum: float = 10000
    slider: bool = False
    group: str = ''

    def parse(self, value):
        if self.kind == 'bool':
            if type(value) is not bool:
                raise ValueError('Escolha ligado ou desligado.')
        elif self.kind in ('int', 'float'):
            if isinstance(value, bool):
                raise ValueError('Informe um número.')
            try:
                number = float(str(value).replace(',', '.'))
            except (TypeError, ValueError):
                raise ValueError('Informe um número.') from None
            if not math.isfinite(number) or not self.minimum <= number <= self.maximum:
                raise ValueError(f'Use um valor entre {self.minimum:g} e {self.maximum:g}.')
            if self.kind == 'int' and not number.is_integer():
                raise ValueError('Use um número inteiro.')
            value = int(number) if self.kind == 'int' else number
            if self.choices and value not in self.choices:
                raise ValueError('Escolha um valor da lista.')
        else:
            maximum = 4096 if self.kind == 'path' else 256
            if not isinstance(value, str) or len(value) > maximum:
                raise ValueError(f'Use até {maximum} caracteres.')
            if self.kind == 'color' and not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                raise ValueError('Use uma cor no formato #RRGGBB.')
            if self.choices and value not in self.choices:
                raise ValueError('Escolha uma opção da lista.')
        return value


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    fields: tuple[Field, ...]
    sample: str = ''
    presentation: str = 'fields'
    action: str = ''
    action_key: str = ''
    secondary_actions: tuple = ()


def number(key, label, default, low, high, *, decimal=False, slider=False):
    return Field(key, label, default, 'float' if decimal else 'int', minimum=low, maximum=high, slider=slider)


def choice(key, label, default, *values):
    return Field(key, label, default, 'choice', choices=values)


def group(label, *fields):
    return tuple(replace(field, group=label) for field in fields)


def text_style(*, reference=False):
    return (
        choice('font', 'Fonte', 'Archivo', 'Archivo', 'Arial'),
        number('size', 'Tamanho (% da altura)', 1.9 if reference else 4.3, .5, 15, decimal=True, slider=True),
        Field('color', 'Cor do texto', '#FFFFFF', 'color'),
        choice('align', 'Alinhamento', 'Esquerda' if reference else 'Centro', 'Esquerda', 'Centro', 'Direita'),
        choice('position', 'Posição', 'Em cima' if reference else 'Embaixo', 'Em cima', 'Embaixo'),
        number('margin', 'Margem (%)', 1.2 if reference else 5, 0, 25, decimal=True, slider=True),
        Field('background', 'Cor do fundo', '#000000', 'color'),
        number('opacity', 'Opacidade do fundo (%)', 72, 0, 100, slider=True),
    )


CATEGORIES = (
    Category('identity', 'Identificação', (
        *group('Cenas', Field('scene_prefix', 'Prefixo', 'Scene_'), Field('scene_suffix', 'Sufixo', ''),
            number('scene_digits', 'Dígitos', 2, 1, 8)),
        *group('Shots', Field('shot_prefix', 'Prefixo', 'shot_'), Field('shot_suffix', 'Sufixo', ''),
            number('shot_digits', 'Dígitos', 4, 1, 8))), sample='identity'),
    Category('subtitles', 'Legendas', text_style(), sample='subtitles'),
    Category('reference', 'Dados de referência', text_style(reference=True) + (
        Field('project', 'Projeto', False, 'bool'), Field('scene', 'Cena', False, 'bool'),
        Field('sequence', 'Sequência', False, 'bool'), Field('shot', 'Shot', False, 'bool'),
        Field('duration_frames', 'Duração em frames', False, 'bool'),
        Field('duration_seconds', 'Duração em segundos', False, 'bool'),
        Field('shot_frame', 'Frame do quadro', False, 'bool'),
        Field('current_frame', 'Frame atual', False, 'bool'),
        Field('total_frames', 'Total de frames', False, 'bool'),
        Field('elapsed_seconds', 'Tempo decorrido', False, 'bool'),
        Field('fps', 'FPS', False, 'bool'), Field('resolution', 'Resolução', False, 'bool')), sample='reference'),
    Category('appearance', 'Aparência', (
        Field('canvas', 'Fundo do canvas', '#181818', 'color'),
        Field('preview', 'Fundo da prévia', '#101010', 'color'),
        Field('selection', 'Seleção', '#80B8E5', 'color'),
        Field('marker', 'Marcadores', '#7DAA9B', 'color'),
        Field('grid_color', 'Cor da grade', '#282828', 'color')), sample='appearance'),
    Category('canvas', 'Canvas', (
        Field('grid', 'Exibir grade', True, 'bool'), number('spacing', 'Espaçamento da grade', 24, 4, 256),
        number('zoom', 'Sensibilidade do zoom', 1, .1, 5, decimal=True),
        Field('fit', 'Enquadrar ao abrir', False, 'bool'))),
    Category('timeline', 'Timeline', (
        choice('unit', 'Unidade de tempo', 'Segundos', 'Frames', 'Segundos'),
        number('seconds_decimals', 'Casas decimais dos segundos', 3, 0, 6),
        number('counter_digits', 'Dígitos dos contadores', 4, 1, 10),
        Field('snap', 'Snap ligado ao abrir', True, 'bool'),
        number('volume', 'Volume (%)', 100, 0, 100, slider=True)), sample='numbers'),
    Category('drawing', 'Desenho', (
        Field('color', 'Cor inicial', '#FF5050', 'color'), number('width', 'Espessura (px)', 4, 1, 64),
        number('eraser', 'Borracha (px)', 24, 1, 200), Field('remember', 'Lembrar ferramenta', True, 'bool'))),
    Category('shortcuts', 'Atalhos', (), presentation='shortcuts'),
    Category('system', 'Salvamento e desempenho', (
        *group('Recuperação', number('interval', 'Backup a cada (min)', 2, 1, 60),
            number('backups', 'Cópias mantidas', 10, 1, 100),
            Field('restore', 'Restaurar última sessão', True, 'bool')),
        *group('Mídia e cache',
            choice('quality', 'Qualidade da prévia', 'Automática', 'Automática', 'Baixa', 'Média', 'Alta'),
            number('cache', 'Cache de prévias (MB)', 512, 64, 8192))), action='Limpar prévias', action_key='clear_previews',
        secondary_actions=(('open_backups', 'Abrir backups'),)),
    Category('files', 'Arquivos e exportação', (
        Field('import_folder', 'Pasta de importação', '', 'path'), Field('export_folder', 'Pasta de exportação', '', 'path'),
        number('recent', 'Projetos recentes', 20, 1, 100),
        choice('quality', 'Qualidade do MP4', 'Alta', 'Média', 'Alta'),
        Field('filename', 'Nome do arquivo', '{project}_{scene}'))),
    Category('confirmations', 'Confirmações', (
        Field('delete', 'Confirmar exclusão', False, 'bool'),
        Field('close', 'Avisar sobre alterações ao fechar', True, 'bool')), action='Restaurar avisos', action_key='restore_confirmations'),
    Category('projects', 'Novos projetos', (
        Field('fps', 'FPS inicial', 24, 'int', choices=(24, 25, 30, 60)),
        number('width', 'Largura (px)', 1920, 64, 8192),
        number('height', 'Altura (px)', 1080, 64, 8192)), sample='projects'),
)


def defaults():
    return {category.key: {field.key: field.default for field in category.fields} for category in CATEGORIES}


def validated(values):
    if not isinstance(values, dict):
        raise ValueError('Preferências inválidas.')
    result = defaults()
    for category in CATEGORIES:
        section = values.get(category.key, {})
        if not isinstance(section, dict):
            raise ValueError('Categoria inválida.')
        for field in category.fields:
            if field.key in section:
                result[category.key][field.key] = field.parse(section[field.key])
    return result
