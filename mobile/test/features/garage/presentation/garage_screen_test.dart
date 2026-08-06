import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/garage/data/fake_vehicle_repository.dart';
import 'package:mobile/features/garage/domain/vehicle.dart';
import 'package:mobile/features/garage/presentation/garage_providers.dart';
import 'package:mobile/features/garage/presentation/garage_screen.dart';

void main() {
  testWidgets('GarageScreen lists vehicles from the repository', (tester) async {
    final repo = FakeVehicleRepository(const [
      Vehicle(id: 'a', displayName: 'Test EV', batteryPct: 77, usableKwh: 60),
    ]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [vehicleRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: GarageScreen()),
      ),
    );

    await tester.pump(); // let the FutureProvider resolve
    expect(find.text('Test EV'), findsOneWidget);
    expect(find.text('77%'), findsOneWidget);
  });
}
