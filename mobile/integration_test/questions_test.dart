import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:pdfrx/pdfrx.dart';
import 'package:concursinho_mobile/main.dart';
import 'package:concursinho_mobile/question_bank.dart';
import 'package:concursinho_mobile/study_state.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Banco real no Android: recorte PDF, resposta, motivo, gráfico e persistência',
    (tester) async {
      await pdfrxFlutterInitialize();
      final dir = await Directory.systemTemp.createTemp(
        'concursinho-questions-device-',
      );
      final bank = await QuestionBank.open('${dir.path}/questions.sqlite3');
      final lines = const LineSplitter().convert(
        await rootBundle.loadString('assets/data/questoes.jsonl'),
      );
      final question = lines
          .map((s) => jsonDecode(s) as Map<String, dynamic>)
          .firstWhere((q) => q['id'] == '01_TJRR_2024_FGV:tipo1:q36');
      await bank.importLines(Stream.value(jsonEncode(question)));
      final state = StudyState(
        await StudyCatalog.load(),
        FileStudyStorage(dir),
        dir,
      );
      await state.load();
      await tester.pumpWidget(ConcursinhoApp(state: state, questionBank: bank));
      await tester.pumpAndSettle();
      await binding.convertFlutterSurfaceToImage();
      await tester.pumpAndSettle();
      await tester.tap(find.text('Questões').last);
      await tester.pumpAndSettle();
      for (
        var i = 0;
        i < 30 && find.byKey(const Key('draw-question')).evaluate().isEmpty;
        i++
      ) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      final draw = find.byKey(const Key('draw-question'));
      await tester.ensureVisible(draw);
      await tester.tap(draw);
      await tester.pumpAndSettle();
      for (
        var i = 0;
        i < 30 && find.text('Ler como texto').evaluate().isEmpty;
        i++
      ) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      // The quiz loads the real PDF crop. Independently check native pixels as
      // Flutter surface screenshots may omit asynchronous PDF images here.
      final source = state.document(question['documentId'])!;
      final doc = await PdfDocument.openFile(await state.localPath(source));
      final clip = (question['clips'] as List).first as Map;
      final rect = (clip['rect'] as List).cast<num>();
      final page = doc.pages[(clip['page'] as int) - 1],
          scale = 700 / (rect[2] - rect[0]);
      final image = (await page.render(
        x: (rect[0] * scale).round(),
        y: (rect[1] * scale).round(),
        width: 700,
        height: ((rect[3] - rect[1]) * scale).ceil(),
        fullWidth: page.width * scale,
        fullHeight: page.height * scale,
      ))!;
      var ink = 0;
      for (var i = 0; i < image.pixels.length; i += 4) {
        if (image.pixels[i] < 170 &&
            image.pixels[i + 1] < 170 &&
            image.pixels[i + 2] < 170) {
          ink++;
        }
      }
      expect(ink, greaterThan(500));
      image.dispose();
      await doc.dispose();
      await tester.ensureVisible(find.text('Ler como texto'));
      await tester.tap(find.text('Ler como texto'));
      await tester.pumpAndSettle();
      await binding.takeScreenshot('05-questoes');
      final wrong = ((question['answer'] as int) + 1) % 5;
      final alternative = find.byKey(Key('answer-$wrong'));
      await tester.ensureVisible(alternative);
      await tester.tap(alternative);
      await tester.pump();
      await tester.ensureVisible(find.text('Confirmar resposta'));
      await tester.tap(find.text('Confirmar resposta'));
      await tester.pumpAndSettle();
      for (
        var i = 0;
        i < 30 && find.text('Vamos entender esse erro.').evaluate().isEmpty;
        i++
      ) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(find.text('Vamos entender esse erro.'), findsOneWidget);
      await tester.ensureVisible(find.text('Interpretação'));
      await tester.tap(find.text('Interpretação'));
      await tester.pumpAndSettle();
      await tester.drag(
        find.byKey(const PageStorageKey('questions-scroll')),
        const Offset(0, 5000),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Desempenho'));
      await tester.tap(find.text('Desempenho'));
      await tester.pumpAndSettle();
      for (
        var i = 0;
        i < 30 && find.text('Amostra inicial').evaluate().isEmpty;
        i++
      ) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      final report = await bank.report();
      expect(report.attempts, 1);
      expect(report.correct, 0);
      expect(report.reasons.single['reason'], 'Interpretação');
      expect(find.text('Amostra inicial'), findsOneWidget);
      await tester.ensureVisible(find.text('Por assunto e tópico'));
      await tester.pumpAndSettle();
      await binding.takeScreenshot('06-desempenho-teste');
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      state.dispose();
      await bank.close();
      final restored = await QuestionBank.open('${dir.path}/questions.sqlite3');
      expect((await restored.report()).attempts, 1);
      await restored.close();
    },
  );
}
