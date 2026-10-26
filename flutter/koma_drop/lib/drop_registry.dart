import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';

class DropDestination {
  const DropDestination(this.nodeId, this.scenePosition);
  final String? nodeId;
  final Offset scenePosition;
}

/// One registry per canvas. Render objects, not model coordinates, own hit tests.
class DropRegistry {
  final nodes = <String, GlobalKey>{};
  GlobalKey? scene;
  final hovered = ValueNotifier<String?>(null);

  DropDestination? resolve(Offset globalPosition, int viewId) {
    final sceneBox = scene?.currentContext?.findRenderObject();
    if (sceneBox is! RenderBox || !sceneBox.attached || !sceneBox.hasSize) {
      return null;
    }
    final hit = HitTestResult();
    WidgetsBinding.instance.hitTestInView(hit, globalPosition, viewId);
    final route = hit.path.map((entry) => entry.target).toList();
    if (!route.contains(sceneBox)) return null; // Toolbars/dialogs are excluded.
    String? target;
    for (final entry in route) {
      for (final node in nodes.entries) {
        if (identical(node.value.currentContext?.findRenderObject(), entry)) {
          target = node.key;
          break;
        }
      }
      if (target != null) break; // Flutter's actual frontmost hit, not list order.
    }
    final position = sceneBox.globalToLocal(globalPosition);
    if (!position.dx.isFinite || !position.dy.isFinite) return null;
    return DropDestination(target, position);
  }

  void dispose() => hovered.dispose();
}

class DropScope extends InheritedWidget {
  const DropScope({super.key, required this.registry, required super.child});
  final DropRegistry registry;
  static DropRegistry? of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<DropScope>()?.registry;
  @override
  bool updateShouldNotify(DropScope oldWidget) => registry != oldWidget.registry;
}

class DropAnchor extends StatefulWidget {
  const DropAnchor({super.key, this.nodeId, required this.child});
  final String? nodeId;
  final Widget child;
  @override
  State<DropAnchor> createState() => _DropAnchorState();
}

class _DropAnchorState extends State<DropAnchor> {
  final anchor = GlobalKey();
  DropRegistry? registry;
  String? registeredId;

  void unregister() {
    if (registeredId == null) {
      if (identical(registry?.scene, anchor)) registry?.scene = null;
    } else if (identical(registry?.nodes[registeredId], anchor)) {
      registry?.nodes.remove(registeredId);
    }
  }

  void register() {
    registeredId = widget.nodeId;
    if (registeredId == null) {
      registry?.scene = anchor;
    } else {
      registry?.nodes[registeredId!] = anchor;
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    unregister();
    registry = DropScope.of(context);
    register();
  }

  @override
  void didUpdateWidget(DropAnchor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.nodeId != oldWidget.nodeId) {
      unregister();
      register();
    }
  }

  @override
  void dispose() {
    unregister();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SizedBox(key: anchor, child: widget.child);
}
