/// Desktop menu adapter for APIs not exposed by Flet 1.0.5.
library;

import 'package:flet/flet.dart';
import 'package:flet/src/utils/popup_menu.dart' show buildPopupMenuEntries;
import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';

class DesktopMenusExtension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) =>
      control.type == 'koma_context_menu'
          ? _ContextMenu(key: key, control: control)
          : null;
}

class _ContextMenu extends StatefulWidget {
  const _ContextMenu({super.key, required this.control});
  final Control control;

  @override
  State<_ContextMenu> createState() => _ContextMenuState();
}

class _ContextMenuState extends State<_ContextMenu> {
  ModalRoute<dynamic>? _route;
  Future<String?>? _pendingMenu;
  bool _closing = false;
  Offset? _pointer;
  bool _tracksPointer = false;

  void _trackPointer(PointerEvent event) {
    if (event is PointerHoverEvent || event is PointerMoveEvent ||
        event is PointerDownEvent) {
      _pointer = event.position;
    }
  }

  void _close() {
    _closing = true;
    final route = _route;
    if (route != null && route.isActive) route.navigator?.removeRoute(route);
  }

  @override
  void initState() {
    super.initState();
    widget.control.addInvokeMethodListener(_invokeMethod);
    _tracksPointer = widget.control.getBool('open_at_pointer', false)!;
    if (_tracksPointer) {
      GestureBinding.instance.pointerRouter.addGlobalRoute(_trackPointer);
    }
  }

  @override
  void dispose() {
    widget.control.removeInvokeMethodListener(_invokeMethod);
    if (_tracksPointer) {
      GestureBinding.instance.pointerRouter.removeGlobalRoute(_trackPointer);
    }
    final route = _route;
    if (route != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (route.isActive) route.navigator?.removeRoute(route);
      });
    }
    super.dispose();
  }

  Future<void> _open(Offset global, Offset local) async {
    if (_pendingMenu != null) {
      _close();
      await _pendingMenu;
      if (!mounted) return;
    }
    _closing = false;
    final control = widget.control;
    final overlay = Overlay.of(context, rootOverlay: true)
        .context.findRenderObject() as RenderBox;
    final position = overlay.globalToLocal(global);
    final items = control.children('items');
    final entries = buildPopupMenuEntries(items, context);
    if (entries.isEmpty) return;
    final menu = showMenu<String>(
      context: context,
      position: RelativeRect.fromSize(position & Size.zero, overlay.size),
      items: [for (final entry in entries) _TrackedEntry(entry, (route) {
        _route = route;
        if (_closing) WidgetsBinding.instance.addPostFrameCallback((_) => _close());
      })],
      popUpAnimationStyle: AnimationStyle.noAnimation,
      menuPadding: control.getPadding('menu_padding'),
      color: control.getColor('bgcolor', context),
      shape: control.getShape('shape', Theme.of(context)),
      elevation: 0,
      constraints: control.getBoxConstraints('size_constraints'),
    );
    _pendingMenu = menu;
    final selected = await menu;
    _pendingMenu = null;
    _route = null;
    if (!mounted) return;
    control.triggerEvent(selected == null ? 'dismiss' : 'select', {
      'g': {'x': global.dx, 'y': global.dy},
      'l': {'x': local.dx, 'y': local.dy},
      'id': selected == null ? null : int.tryParse(selected),
      'ic': items.length,
    });
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    if (name == 'close') {
      _close();
      return null;
    }
    if (name != 'open') throw ArgumentError('Unsupported menu method: $name');
    final box = context.findRenderObject() as RenderBox;
    final local = parseOffset(args['local_position']);
    final global = parseOffset(args['global_position']) ??
        (local == null && _tracksPointer ? _pointer : null);
    final resolvedLocal = local ?? (global == null
        ? box.size.center(Offset.zero) : box.globalToLocal(global));
    _open(global ?? box.localToGlobal(resolvedLocal), resolvedLocal);
    return null;
  }

  @override
  Widget build(BuildContext context) => LayoutControl(control: widget.control,
      child: widget.control.buildWidget('content') ?? const SizedBox());
}

/// Track only the popup's route so closing it cannot pop another dialog.
class _TrackedEntry extends PopupMenuEntry<String> {
  const _TrackedEntry(this.entry, this.onRoute);
  final PopupMenuEntry<String> entry;
  final ValueChanged<ModalRoute<dynamic>?> onRoute;

  @override
  double get height => entry.height;
  @override
  bool represents(String? value) => entry.represents(value);
  @override
  State<_TrackedEntry> createState() => _TrackedEntryState();
}

class _TrackedEntryState extends State<_TrackedEntry> {
  @override
  Widget build(BuildContext context) {
    widget.onRoute(ModalRoute.of(context));
    return widget.entry;
  }
}
