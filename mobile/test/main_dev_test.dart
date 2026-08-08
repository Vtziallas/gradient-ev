import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app/app.dart';
import 'package:mobile/main_dev.dart';

void main() {
  testWidgets('app boots to Plan screen and navigates to Garage with real data', (tester) async {
    await tester.pumpWidget(ProviderScope(child: GradientApp(router: buildAppRouter())));
    await tester.pumpAndSettle();

    expect(find.text('Where to?'), findsOneWidget);

    await tester.tap(find.text('Garage'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Tesla Model 3 LR'), findsOneWidget);
  });
}
