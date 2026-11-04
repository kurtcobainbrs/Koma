import 'package:flet/flet.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

class SpatialExtension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) => control.type == 'koma_spatial_view'
      ? SpatialView(key: key ?? ValueKey(control.id), control: control) : null;
}

class SpatialView extends StatefulWidget {
  const SpatialView({super.key, required this.control});
  final Control control;
  @override
  State<SpatialView> createState() => _SpatialViewState();
}

class _SpatialViewState extends State<SpatialView> {
  final camera = TransformationController();
  int revision = -1;
  bool pending = false;

  void report() {
    final matrix = camera.value;
    widget.control.triggerEvent('pose', {'zoom': matrix.getMaxScaleOnAxis(),
      'x': matrix.storage[12], 'y': matrix.storage[13], 'generation': revision});
  }

  void scheduleReport() {
    if (pending) return;
    pending = true;
    SchedulerBinding.instance.addPostFrameCallback((_) {
      pending = false;
      if (mounted) report();
    });
  }

  @override
  Widget build(BuildContext context) {
    final control = widget.control;
    final next = control.getInt('camera_revision', 0)!;
    if (revision != next) {
      revision = next;
      final zoom = control.getDouble('camera_zoom', 1)!;
      camera.value = Matrix4.diagonal3Values(zoom, zoom, 1)
        ..setTranslationRaw(control.getDouble('camera_x', 0)!, control.getDouble('camera_y', 0)!, 0);
    }
    return LayoutControl(control: control, child: InteractiveViewer(
      transformationController: camera,
      constrained: false, alignment: Alignment.topLeft,
      boundaryMargin: const EdgeInsets.all(double.infinity),
      panEnabled: control.getBool('pan_enabled', false)!,
      scaleEnabled: control.getBool('scale_enabled', true)!,
      minScale: control.getDouble('min_scale', .05)!,
      maxScale: control.getDouble('max_scale', 16)!,
      scaleFactor: control.getDouble('scale_factor', 240)!,
      onInteractionStart: (_) => control.triggerEvent('camera_start'),
      onInteractionUpdate: (_) => scheduleReport(),
      onInteractionEnd: (_) => report(),
      child: control.buildWidget('content') ?? const SizedBox(),
    ));
  }

  @override
  void dispose() {
    camera.dispose();
    super.dispose();
  }
}
