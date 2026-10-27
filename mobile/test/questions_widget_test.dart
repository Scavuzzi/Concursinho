import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:concursinho_mobile/main.dart';
import 'package:concursinho_mobile/question_bank.dart';
import 'package:concursinho_mobile/study_state.dart';
import 'study_state_test.dart' show MemoryStorage;

Future<void> waitFor(WidgetTester tester, Finder finder) async {
  for (var i = 0; i < 80 && finder.evaluate().isEmpty; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await tester.pumpAndSettle();
  }
  expect(finder, findsWidgets);
}

void main() {
  setUpAll(sqfliteFfiInit);
  testWidgets(
    'Questões: confirmar uma vez, registrar erro, ver diagnóstico e corrigir assunto em tela estreita',
    (tester) async {
      tester.view.physicalSize = const Size(360, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      late Directory dir;
      late QuestionBank bank;
      late StudyState state;
      await tester.runAsync(() async {
        dir = await Directory.systemTemp.createTemp('question-widget-');
        bank = await QuestionBank.open(
          '${dir.path}/db.sqlite',
          factory: databaseFactoryFfiNoIsolate,
        );
        await bank.importLines(
          Stream.value(
            jsonEncode({
              'id': 'widget:1',
              'subject': 'Banco de dados',
              'topic': 'SQL',
              'stem':
                  'Questão fictícia para testar a interface. Qual é a correta?',
              'options': ['A correta', 'A incorreta'],
              'answer': 0,
              'source': 'Fixture de teste',
              'explanation': 'Comentário fictício de teste.',
            }),
          ),
        );
        state = StudyState(await StudyCatalog.load(), MemoryStorage(), dir);
        await state.load();
      });
      Future<PracticeReport> report() async =>
          (await tester.runAsync(() => bank.report()))!;
      await tester.pumpWidget(ConcursinhoApp(state: state, questionBank: bank));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Questões').last);
      await tester.pumpAndSettle();
      await waitFor(tester, find.byKey(const Key('draw-question')));
      await tester.ensureVisible(find.byKey(const Key('draw-question')));
      await tester.tap(find.byKey(const Key('draw-question')));
      await tester.pumpAndSettle();
      await waitFor(tester, find.byKey(const Key('answer-1')));
      await tester.ensureVisible(find.byKey(const Key('answer-1')));
      await tester.tap(find.byKey(const Key('answer-1')));
      await tester.pumpAndSettle();
      final confirm = find.text('Confirmar resposta');
      await tester.ensureVisible(confirm);
      await tester.tap(confirm);
      await tester.pumpAndSettle();
      await waitFor(tester, find.text('Vamos entender esse erro.'));
      await tester.ensureVisible(find.text('Interpretação'));
      await tester.tap(find.text('Interpretação'));
      await tester.pumpAndSettle();
      await tester.drag(
        find.byKey(const PageStorageKey('questions-scroll')),
        const Offset(0, 3000),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Desempenho'));
      await tester.tap(find.text('Desempenho'));
      await tester.pumpAndSettle();
      await waitFor(tester, find.text('Amostra inicial'));
      expect((await report()).attempts, 1);
      expect((await report()).correct, 0);
      expect((await report()).reasons.single['reason'], 'Interpretação');
      expect(tester.takeException(), isNull);
      await tester.drag(
        find.byKey(const PageStorageKey('questions-scroll')),
        const Offset(0, 3000),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Praticar'));
      await tester.tap(find.text('Praticar'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Ajustar assunto e tópico'));
      await tester.tap(find.text('Ajustar assunto e tópico'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).first, 'Desenvolvimento');
      await tester.enterText(find.byType(TextField).last, 'Algoritmos');
      await tester.tap(find.text('Salvar'));
      await tester.pumpAndSettle();
      for (var i = 0; i < 30; i++) {
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 20)),
        );
        await tester.pumpAndSettle();
        if ((await report()).topics.single.subject == 'Desenvolvimento') {
          break;
        }
      }
      expect((await report()).topics.single.subject, 'Desenvolvimento');
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      state.dispose();
      await tester.runAsync(() async {
        await bank.close();
        await dir.delete(recursive: true);
      });
    },
  );
}
