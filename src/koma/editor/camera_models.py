"""Node-owned camera directions; indications do not animate or transform media."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraPreset:
    label: str
    kind: str
    direction: tuple = (0, 0)


CAMERA_PRESETS = {
    'none': CameraPreset('Nenhum', 'none'),
    'pan_left': CameraPreset('Pan · esquerda', 'arrow', (-1, 0)),
    'pan_right': CameraPreset('Pan · direita', 'arrow', (1, 0)),
    'tilt_up': CameraPreset('Tilt · cima', 'arrow', (0, -1)),
    'tilt_down': CameraPreset('Tilt · baixo', 'arrow', (0, 1)),
    'zoom_in': CameraPreset('Zoom · aproximar', 'in'),
    'zoom_out': CameraPreset('Zoom · afastar', 'out'),
    'dolly_in': CameraPreset('Dolly · avançar', 'in'),
    'dolly_out': CameraPreset('Dolly · recuar', 'out'),
    'truck_left': CameraPreset('Deslocar · esquerda', 'arrow', (-1, 0)),
    'truck_right': CameraPreset('Deslocar · direita', 'arrow', (1, 0)),
    'pedestal_up': CameraPreset('Elevar câmera', 'arrow', (0, -1)),
    'pedestal_down': CameraPreset('Baixar câmera', 'arrow', (0, 1)),
    'orbit_left': CameraPreset('Órbita · esquerda', 'orbit', (-1, 0)),
    'orbit_right': CameraPreset('Órbita · direita', 'orbit', (1, 0)),
}
MAX_CAMERA_NOTE = 200


@dataclass(frozen=True)
class CameraMotion:
    preset: str = 'none'
    note: str = ''
    visible: bool = True

    def validate(self):
        if not isinstance(self.preset, str) or self.preset not in CAMERA_PRESETS:
            raise ValueError('Movimento de câmera inválido.')
        if not isinstance(self.note, str) or len(self.note) > MAX_CAMERA_NOTE or type(self.visible) is not bool:
            raise ValueError('Indicação de câmera inválida.')

    @classmethod
    def from_document(cls, raw):
        if not isinstance(raw, dict):
            raise ValueError('Indicação de câmera inválida.')
        result = cls(**raw)
        result.validate()
        return result
