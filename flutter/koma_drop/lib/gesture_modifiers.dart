import 'package:flet/flet.dart';
import 'package:flutter/services.dart';

bool matchesGestureModifiers(Control control, String property) {
  final keyboard = HardwareKeyboard.instance;
  final pressed = <String>{
    if (keyboard.isControlPressed) 'Ctrl',
    if (keyboard.isAltPressed) 'Alt',
    if (keyboard.isShiftPressed) 'Shift',
    if (keyboard.isMetaPressed) 'Meta',
  };
  return control.get<List<dynamic>>(property, [])!.any((combo) =>
      (combo as String).split('+').every(pressed.contains));
}
