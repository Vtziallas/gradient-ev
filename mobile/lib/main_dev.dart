import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/app.dart';
import 'app/router.dart';

void main() {
  final router = buildRouter(
    planScreen: const Scaffold(body: Center(child: Text('Plan — coming soon'))),
    garageScreen: const Scaffold(body: Center(child: Text('Garage — coming soon'))),
  );
  runApp(ProviderScope(child: GradientApp(router: router)));
}
