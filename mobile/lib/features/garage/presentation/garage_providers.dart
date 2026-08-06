import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/fake_vehicle_repository.dart';
import '../domain/vehicle.dart';
import '../domain/vehicle_repository.dart';

final vehicleRepositoryProvider = Provider<VehicleRepository>((ref) {
  return FakeVehicleRepository();
});

final vehiclesProvider = FutureProvider<List<Vehicle>>((ref) {
  return ref.watch(vehicleRepositoryProvider).listVehicles();
});
