"""Inclui recursos Flet sem copiar o cliente padrão incompatível com koma_drop."""
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('flet.controls.material', includes=['icons.json'])
datas += collect_data_files('flet.controls.cupertino', includes=['cupertino_icons.json'])
