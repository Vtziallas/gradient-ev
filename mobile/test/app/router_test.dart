import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app/app.dart';
import 'package:mobile/app/router.dart';

void main() {
  testWidgets('GradientApp boots to the Plan tab via the router', (tester) async {
    final router = buildRouter(
      planScreen: const Text('PLAN'),
      garageScreen: const Text('GARAGE'),
    );
    await tester.pumpWidget(ProviderScope(child: GradientApp(router: router)));
    await tester.pumpAndSettle();
    expect(find.text('PLAN'), findsOneWidget);
  });

  testWidgets('GradientApp switches to Garage on nav tap', (tester) async {
    final router = buildRouter(
      planScreen: const Text('PLAN'),
      garageScreen: const Text('GARAGE'),
    );
    await tester.pumpWidget(ProviderScope(child: GradientApp(router: router)));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Garage'));
    await tester.pumpAndSettle();

    expect(find.text('GARAGE'), findsOneWidget);
  });
}
