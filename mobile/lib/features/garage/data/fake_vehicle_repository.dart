import '../domain/vehicle.dart';
import '../domain/vehicle_repository.dart';

/// In-memory repository — stands in for the API-backed implementation
/// until the backend (BackendArchitecture.md) exists. Replace with a
/// dio-backed implementation once `GET /vehicles` ships.
class FakeVehicleRepository implements VehicleRepository {
  FakeVehicleRepository([List<Vehicle>? seed])
      : _vehicles = seed ??
            const [
              Vehicle(
                id: 'tesla-model3-lr',
                displayName: 'Tesla Model 3 LR',
                batteryPct: 82,
                usableKwh: 75,
              ),
              Vehicle(
                id: 'ioniq5-awd',
                displayName: 'Hyundai Ioniq 5 AWD',
                batteryPct: 64,
                usableKwh: 77.4,
              ),
            ];

  final List<Vehicle> _vehicles;

  @override
  Future<List<Vehicle>> listVehicles() async => List.unmodifiable(_vehicles);
}
