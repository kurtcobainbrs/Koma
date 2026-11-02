import 'package:flutter_test/flutter_test.dart';
import 'package:koma_drop/navigation_pose.dart';

void main() {
  test('zoom preserves the world point under the cursor, including limits', () {
    const pose = NavigationPose(zoom: 2, x: -100, y: 40);
    final next = pose.zoomAt(3, 330, 220, .25, 4);
    expect(next.zoom, 4);
    expect((330 - next.x) / next.zoom, (330 - pose.x) / pose.zoom);
    expect((220 - next.y) / next.zoom, (220 - pose.y) / pose.zoom);
    final restored = next.zoomAt(.5, 330, 220, .25, 4);
    expect(restored.zoom, pose.zoom);
    expect(restored.x, pose.x);
    expect(restored.y, pose.y);
    expect(identical(pose.zoomAt(double.nan, 0, 0, .25, 4), pose), isTrue);
  });

  test('pan changes only translation', () {
    const pose = NavigationPose(zoom: 3, x: 20, y: -50);
    final moved = pose.pan(100, -30);
    expect(moved.zoom, 3);
    expect(moved.x, 120);
    expect(moved.y, -80);
  });

  test('zoom batches keep one in flight and combine pending input without a queue', () {
    final batch = ZoomBatch()..add(2, 100);
    expect(batch.take(), (factor: 2.0, anchor: 100.0));
    batch.add(2, 150);
    batch.add(3, 180);
    expect(batch.take(), isNull);
    batch.acknowledge();
    expect(batch.take(), (factor: 6.0, anchor: 180.0));
    batch.add(3, 200);
    batch.clear();
    expect(batch.take(), isNull);
    expect(batch.busy, isFalse);
  });
}
