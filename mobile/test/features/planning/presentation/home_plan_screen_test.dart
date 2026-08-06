import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/garage/data/fake_vehicle_repository.dart';
import 'package:mobile/features/garage/domain/vehicle.dart';
import 'package:mobile/features/garage/presentation/garage_providers.dart';
import 'package:mobile/features/planning/presentation/home_plan_screen.dart';

void main() {
  testWidgets('HomePlanScreen shows the garage chip, search field, and recents', (tester) async {
    final repo = FakeVehicleRepository(const [
      Vehicle(id: 'a', displayName: 'Test EV', batteryPct: 82, usableKwh: 75),
    ]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [vehicleRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: HomePlanScreen()),
      ),
    );

    await tester.pump();

    expect(find.textContaining('82%'), findsOneWidget);
    expect(find.textContaining('Test EV'), findsOneWidget);
    expect(find.text('Where to?'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
    expect(find.text('3D map — coming soon'), findsOneWidget);
  });

  testWidgets('HomePlanScreen shows a fallback when there is no vehicle', (tester) async {
    final repo = FakeVehicleRepository(const []);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [vehicleRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: HomePlanScreen()),
      ),
    );

    await tester.pump();
    expect(find.text('No vehicle selected'), findsOneWidget);
  });
}
