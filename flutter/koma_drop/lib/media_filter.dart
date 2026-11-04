import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';

class MediaFilterExtension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) {
    if (control.type != 'koma_media_filter') return null;
    final values = control.get<List<dynamic>>('matrix');
    final matrix = values is List ? values.map((v) => (v as num).toDouble()).toList() : null;
    return LayoutControl(key: key, control: control,
        child: MediaColorTransform(matrix: matrix,
            child: control.buildWidget('content') ?? const SizedBox()));
  }
}

/// Applies only the supplied media transform; annotations remain sibling layers.
class MediaColorTransform extends StatelessWidget {
  const MediaColorTransform({super.key, required this.child, this.matrix});
  final Widget child;
  final List<double>? matrix;

  @override
  Widget build(BuildContext context) => matrix == null || matrix!.length != 20
      ? child : ColorFiltered(colorFilter: ColorFilter.matrix(matrix!), child: child);
}
