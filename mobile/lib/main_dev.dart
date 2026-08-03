import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

void main() {
  runApp(const ProviderScope(child: GradientDevApp()));
}

class GradientDevApp extends StatelessWidget {
  const GradientDevApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      title: 'Gradient (dev)',
      home: Scaffold(
        body: Center(child: Text('Gradient — bootstrap OK')),
      ),
    );
  }
}
