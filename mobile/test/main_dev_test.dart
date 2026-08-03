import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main_dev.dart';

void main() {
  testWidgets('GradientDevApp renders bootstrap placeholder', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: GradientDevApp()));
    expect(find.text('Gradient — bootstrap OK'), findsOneWidget);
  });
}
