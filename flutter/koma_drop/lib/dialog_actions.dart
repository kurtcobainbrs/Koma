/// Dialog action routing: Enter accepts, Escape cancels, barrier is explicit.
library;

import 'package:flet/flet.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class DialogActionsExtension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) => control.type == 'koma_dialog'
      ? _ActionDialog(key: key, control: control) : null;
}

class _ActionDialog extends StatefulWidget {
  const _ActionDialog({super.key, required this.control});
  final Control control;
  @override
  State<_ActionDialog> createState() => _ActionDialogState();
}

class _ActionDialogState extends State<_ActionDialog> {
  ModalRoute<dynamic>? _route;
  bool _shown = false;

  void _action(String name) {
    if (widget.control.getBool('open', false)!) widget.control.triggerEvent(name);
  }

  KeyEventResult _key(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent) return KeyEventResult.ignored;
    final keyboard = HardwareKeyboard.instance;
    if (keyboard.isAltPressed || keyboard.isControlPressed || keyboard.isMetaPressed || keyboard.isShiftPressed) {
      return KeyEventResult.ignored;
    }
    if (event.logicalKey == LogicalKeyboardKey.escape) {
      _action('cancel');
      return KeyEventResult.handled;
    }
    if (event.logicalKey == LogicalKeyboardKey.enter || event.logicalKey == LogicalKeyboardKey.numpadEnter) {
      final editable = FocusManager.instance.primaryFocus?.context
          ?.findAncestorWidgetOfExactType<EditableText>();
      if (editable != null && editable.maxLines != 1) return KeyEventResult.ignored;
      _action('confirm');
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  Future<void> _show() async {
    if (!mounted || !widget.control.getBool('open', false)!) return;
    final c = widget.control;
    await showDialog<void>(context: context, barrierDismissible: false,
      barrierColor: Colors.transparent, useSafeArea: false, useRootNavigator: false,
      animationStyle: AnimationStyle.noAnimation,
      builder: (context) {
        _route = ModalRoute.of(context);
        return ListenableBuilder(listenable: c, builder: (context, _) => Stack(
          fit: StackFit.expand,
          children: [
            GestureDetector(behavior: HitTestBehavior.opaque,
              onTap: c.getBool('modal', false)! ? null : () => _action('outside'),
              child: ColoredBox(color: c.getColor('barrier_color', context) ?? Colors.black54)),
            SafeArea(child: Focus(autofocus: true, onKeyEvent: _key,
              child: AlertDialog(
                title: c.buildTextOrWidget('title'), content: c.buildWidget('content'),
                actions: c.buildWidgets('actions'), backgroundColor: c.getColor('bgcolor', context),
                titlePadding: c.getPadding('title_padding'), contentPadding: c.getPadding('content_padding'),
                actionsPadding: c.getPadding('actions_padding'), insetPadding: c.getPadding('inset_padding') ?? const EdgeInsets.symmetric(horizontal: 40, vertical: 24),
                actionsAlignment: c.getMainAxisAlignment('actions_alignment'),
                titleTextStyle: c.getTextStyle('title_text_style', Theme.of(context)),
                contentTextStyle: c.getTextStyle('content_text_style', Theme.of(context)),
                shape: c.getShape('shape', Theme.of(context)),
                scrollable: c.getBool('scrollable', false)!, elevation: c.getDouble('elevation'),
              ))),
          ],
        ));
      });
    _route = null;
    _shown = false;
    if (mounted) {
      c.updateProperties({'open': false});
      c.triggerEvent('dismiss');
    }
  }

  @override
  Widget build(BuildContext context) {
    final open = widget.control.getBool('open', false)!;
    if (open && !_shown) {
      _shown = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _show());
    } else if (!open && _shown && _route != null) {
      final route = _route!;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (route.isActive) route.navigator?.removeRoute(route);
      });
    }
    return const SizedBox.shrink();
  }

  @override
  void dispose() {
    final route = _route;
    if (route != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (route.isActive) route.navigator?.removeRoute(route);
      });
    }
    super.dispose();
  }
}
