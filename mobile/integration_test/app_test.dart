import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:pdfrx/pdfrx.dart';
import 'package:concursinho_mobile/main.dart';
import 'package:concursinho_mobile/reader_screen.dart';
import 'package:concursinho_mobile/study_state.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Leitura PDF nativa, aparência, marcadores e retomada no Android',
    (tester) async {
      await pdfrxFlutterInitialize();
      final directory = await Directory.systemTemp.createTemp(
        'concursinho-device-test',
      );
      final catalog = await StudyCatalog.load();
      final state = StudyState(catalog, FileStudyStorage(directory), directory);
      await state.load();
      final nativeDocument = await PdfDocument.openFile(
        await state.localPath(catalog.documents.first),
      );
      final bitmap = (await nativeDocument.pages.first.render(
        fullWidth: 540,
        fullHeight: 780,
      ))!;
      var nativeInk = 0;
      for (var i = 0; i < bitmap.pixels.length; i += 4) {
        if (bitmap.pixels[i] < 170 &&
            bitmap.pixels[i + 1] < 170 &&
            bitmap.pixels[i + 2] < 170) {
          nativeInk++;
        }
      }
      debugPrint('Native PDF raster: $nativeInk ink pixels');
      expect(nativeInk, greaterThan(500));
      bitmap.dispose();
      nativeDocument.dispose();
      await tester.pumpWidget(ConcursinhoApp(state: state));
      await tester.pumpAndSettle();
      await binding.convertFlutterSurfaceToImage();
      await tester.pumpAndSettle();
      await binding.takeScreenshot('01-plano');
      await tester.tap(find.text('Provas').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Abrir prova').first);
      await tester.pump(const Duration(seconds: 1));
      for (var i = 0; i < 60 && find.text('1 / 16').evaluate().isEmpty; i++) {
        await tester.pump(const Duration(milliseconds: 500));
      }
      expect(find.text('1 / 16'), findsOneWidget);
      expect(find.byType(PdfViewer), findsOneWidget);
      // Validate native raster bytes above. Integration screenshots omit this
      // asynchronous image on this emulator; release-original.png is checked
      // separately from an Android screencap of the installed release APK.
      await tester.tap(find.text('Leitura'));
      await tester.pump(const Duration(seconds: 1));
      for (
        var i = 0;
        i < 30 && find.byKey(const Key('reflow-text')).evaluate().isEmpty;
        i++
      ) {
        await tester.pump(const Duration(milliseconds: 300));
      }
      final text = tester.widget<SelectableText>(
        find.byKey(const Key('reflow-text')),
      );
      expect(text.data!.toUpperCase(), contains('TRIBUNAL'));
      await tester.tap(find.byTooltip('Próxima página'));
      await tester.pump(const Duration(seconds: 1));
      await tester.tap(find.byTooltip('Marcar página'));
      await tester.pump();
      await tester.tap(find.byTooltip('Preferências de leitura'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Sépia'));
      await tester.pumpAndSettle();
      expect(state.reader.theme, 'sepia');
      await tester.tap(find.text('Serifada · Source Serif').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Sem serifa · DM Sans').last);
      await tester.pumpAndSettle();
      final sizeSlider = find.byType(Slider).first;
      await tester.ensureVisible(sizeSlider);
      await tester.drag(sizeSlider, const Offset(45, 0));
      await tester.pumpAndSettle();
      final chosenSize = state.reader.size;
      expect(chosenSize, greaterThan(20));
      expect(state.reader.font, 'DMSans');
      await binding.takeScreenshot('03-preferencias');
      final use = find.text('Usar o modo Leitura');
      await tester.ensureVisible(use);
      await tester.tap(use);
      await tester.pumpAndSettle();
      await binding.takeScreenshot('04-leitura-adaptada');
      await state.persist();
      expect(state.positions[catalog.documents.first.id], 2);
      expect(state.bookmarks[catalog.documents.first.id], [2]);
      final restored = StudyState(
        catalog,
        FileStudyStorage(directory),
        directory,
      );
      await restored.load();
      expect(restored.reader.font, 'DMSans');
      expect(restored.reader.size, chosenSize);
      expect(restored.reader.theme, 'sepia');
      expect(restored.positions[catalog.documents.first.id], 2);
      expect(tester.takeException(), isNull);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byType(ReaderScreen), findsNothing);
      await tester.pumpWidget(const SizedBox());
      state.dispose();
      restored.dispose();
    },
  );
}
