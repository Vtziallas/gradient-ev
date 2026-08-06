import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app/app_shell.dart';

void main() {
  testWidgets('AppShell shows the first tab and switches on nav tap', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(
          tabs: const [
            AppShellTab(label: 'Plan', icon: Icons.map_outlined, screen: Text('PLAN SCREEN')),
            AppShellTab(label: 'Garage', icon: Icons.directions_car_outlined, screen: Text('GARAGE SCREEN')),
          ],
        ),
      ),
    );

    expect(find.text('PLAN SCREEN'), findsOneWidget);
    expect(find.text('GARAGE SCREEN'), findsNothing);

    await tester.tap(find.text('Garage'));
    await tester.pumpAndSettle();

    expect(find.text('GARAGE SCREEN'), findsOneWidget);
  });
}
