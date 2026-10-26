library koma_drop;

import 'package:desktop_drop/desktop_drop.dart';
import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';
import 'drop_registry.dart';

class Extension extends FletExtension {
  @override
  void ensureInitialized() {}

  @override
  Widget? createWidget(Key? key, Control control) {
    switch (control.type) {
      case 'koma_drop_surface':
        return _Surface(key: key ?? ValueKey(control.id), control: control);
      case 'koma_drop_scene':
      case 'koma_drop_node':
        final child = control.buildWidget('content') ?? const SizedBox();
        return LayoutControl(control: control, child: DropAnchor(
          nodeId: control.type == 'koma_drop_node' ? control.get<String>('node_id') : null,
          child: child,
        ));
    }
    return null;
  }
}

class _Surface extends StatefulWidget {
  const _Surface({super.key, required this.control});
  final Control control;
  @override
  State<_Surface> createState() => _SurfaceState();
}

class _SurfaceState extends State<_Surface> {
  final registry = DropRegistry();
  @override
  void dispose() {
    registry.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final control = widget.control;
    final child = control.buildWidget('content') ?? const SizedBox();
    return LayoutControl(control: control, child: DropScope(
      registry: registry,
      child: DropTarget(
        enable: !control.disabled,
        onDragDone: (details) {
          final files = details.files.map((file) => file.path).toList();
          final hasProject = files.any((path) => path.toLowerCase().endsWith('.koma'));
          final documentsOnly = control.getBool('documents_only', false)!;
          // As duas superfícies têm responsabilidades exclusivas, sem abrir
          // duas abas nem importar imagens de uma soltura mista.
          if (documentsOnly != hasProject) return;
          final destination = documentsOnly ? null :
              registry.resolve(details.globalPosition, View.of(context).viewId);
          if (!documentsOnly && destination == null) return;
          control.triggerEvent('dropped', {
            'protocol': 1,
            'session_token': control.get<String>('session_token'),
            'files': files,
            'node_id': destination?.nodeId,
            'scene_x': destination?.scenePosition.dx ?? 0.0,
            'scene_y': destination?.scenePosition.dy ?? 0.0,
            'origin_x': control.get<double>('origin_x') ?? 0.0,
            'origin_y': control.get<double>('origin_y') ?? 0.0,
          });
        },
        child: child,
      ),
    ));
  }
}
