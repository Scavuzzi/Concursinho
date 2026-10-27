import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:concursinho_mobile/main.dart';
import 'package:concursinho_mobile/study_state.dart';

class MemoryStorage implements StudyStorage {
  Map<String, dynamic> data = {};
  @override
  Future<Map<String, dynamic>> read() async => data;
  @override
  Future<void> write(Map<String, dynamic> value) async {
    data = value;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Plano, provas e foco cabem em um telefone estreito', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    late StudyState state;
    await tester.runAsync(() async {
      state = StudyState(
        await StudyCatalog.load(),
        MemoryStorage(),
        Directory.systemTemp,
      );
      await state.load();
    });
    await tester.pumpWidget(ConcursinhoApp(state: state));
    await tester.pumpAndSettle();
    expect(find.text('concursinho.'), findsOneWidget);
    expect(find.text('Um pouco hoje.\nMais perto amanhã.'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('Provas').last);
    await tester.pumpAndSettle();
    expect(find.text('Provas na mão.'), findsOneWidget);
    expect(find.text('Abrir prova'), findsWidgets);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('Foco').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('focus-clock')), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    state.dispose();
  });
}
