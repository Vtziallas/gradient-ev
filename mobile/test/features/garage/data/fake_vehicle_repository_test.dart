import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/garage/data/fake_vehicle_repository.dart';
import 'package:mobile/features/garage/domain/vehicle.dart';

void main() {
  test('default seed returns two vehicles', () async {
    final repo = FakeVehicleRepository();
    final vehicles = await repo.listVehicles();
    expect(vehicles, hasLength(2));
    expect(vehicles.first.displayName, 'Tesla Model 3 LR');
  });

  test('custom seed is returned unmodified', () async {
    const seed = [Vehicle(id: 'x', displayName: 'X', batteryPct: 50, usableKwh: 60)];
    final repo = FakeVehicleRepository(seed);
    final vehicles = await repo.listVehicles();
    expect(vehicles, seed);
  });

  test('returned list is unmodifiable', () async {
    final repo = FakeVehicleRepository();
    final vehicles = await repo.listVehicles();
    expect(() => vehicles.add(vehicles.first), throwsUnsupportedError);
  });
}
