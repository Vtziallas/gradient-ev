import 'vehicle.dart';

abstract class VehicleRepository {
  Future<List<Vehicle>> listVehicles();
}
