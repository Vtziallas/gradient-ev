/// Domain entity — a plain immutable class (no codegen in this skeleton;
/// see plan Non-Goals for why `freezed` is deferred).
class Vehicle {
  const Vehicle({
    required this.id,
    required this.displayName,
    required this.batteryPct,
    required this.usableKwh,
  });

  final String id;
  final String displayName;
  final double batteryPct;
  final double usableKwh;

  @override
  bool operator ==(Object other) =>
      other is Vehicle &&
      other.id == id &&
      other.displayName == displayName &&
      other.batteryPct == batteryPct &&
      other.usableKwh == usableKwh;

  @override
  int get hashCode => Object.hash(id, displayName, batteryPct, usableKwh);
}
