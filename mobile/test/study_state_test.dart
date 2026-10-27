import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
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
  test(
    'Acervo contém 146 tópicos, 25 provas de TI e documentos sem Dataprev',
    () async {
      final catalog = await StudyCatalog.load();
      expect(catalog.topics.length, 146);
      expect(catalog.groups.length, 14);
      expect(catalog.exams.length, 25);
      expect(catalog.documents.length, 54);
      expect(
        catalog.documents.where((e) => e.id.toLowerCase().contains('dataprev')),
        isEmpty,
      );
      expect(catalog.documents.map((e) => e.id).toSet().length, 54);
      for (final exam in catalog.exams) {
        expect(exam.documents.containsKey('prova'), isTrue);
        expect(exam.documents.containsKey('gabarito_definitivo'), isTrue);
      }
    },
  );
  test(
    'Progresso importado mescla IDs válidos e sobrevive ao recarregamento',
    () async {
      final catalog = await StudyCatalog.load(), storage = MemoryStorage();
      final state = StudyState(catalog, storage, Directory.systemTemp);
      await state.load();
      state.toggle(catalog.topics[0].id);
      await state.importProgress(
        jsonEncode([catalog.topics[1].id, 'foreign-key']),
      );
      await state.persist();
      final restored = StudyState(catalog, storage, Directory.systemTemp);
      await restored.load();
      expect(restored.topicCount, 2);
      expect(restored.completed.contains('foreign-key'), isFalse);
      state.dispose();
      restored.dispose();
    },
  );
  test('Página, marcadores e preferências se mantêm após fechar', () async {
    final catalog = await StudyCatalog.load(), storage = MemoryStorage();
    final state = StudyState(catalog, storage, Directory.systemTemp);
    await state.load();
    state.setPosition(catalog.documents.first.id, 3);
    state.toggleBookmark(catalog.documents.first.id, 3);
    state.reader.theme = 'night';
    state.reader.font = 'DMSans';
    state.reader.size = 28;
    state.updateReader();
    await state.persist();
    final restored = StudyState(catalog, storage, Directory.systemTemp);
    await restored.load();
    expect(restored.positions[catalog.documents.first.id], 3);
    expect(restored.bookmarks[catalog.documents.first.id], [3]);
    expect(restored.reader.size, 28);
    expect(restored.reader.theme, 'night');
    expect(restored.reader.font, 'DMSans');
    state.dispose();
    restored.dispose();
  });
  test('Foco vencido é contabilizado apenas uma vez ao reabrir', () async {
    final catalog = await StudyCatalog.load(), storage = MemoryStorage();
    storage.data = {
      'focusDuration': 1500,
      'focusEnd': DateTime.now()
          .subtract(const Duration(minutes: 1))
          .toIso8601String(),
    };
    final state = StudyState(catalog, storage, Directory.systemTemp);
    await state.load();
    await state.persist();
    state.tick();
    expect(state.focusMinutes, 25);
    final restored = StudyState(catalog, storage, Directory.systemTemp);
    await restored.load();
    expect(restored.focusMinutes, 25);
    expect(restored.focusEnd, isNull);
    state.dispose();
    restored.dispose();
  });
  test(
    'Gravação atômica recupera a versão anterior de um arquivo corrompido',
    () async {
      final directory = await Directory.systemTemp.createTemp(
        'concursinho-test',
      );
      try {
        final storage = FileStudyStorage(directory);
        await storage.write({
          'completed': ['first'],
        });
        await storage.write({
          'completed': ['second'],
        });
        await storage.file.writeAsString('{broken');
        expect((await storage.read())['completed'], ['first']);
      } finally {
        await directory.delete(recursive: true);
      }
    },
  );
  test('Importação rejeita arquivos que não são PDF', () async {
    final state = StudyState(
      await StudyCatalog.load(),
      MemoryStorage(),
      Directory.systemTemp,
    );
    await expectLater(
      state.importPdf(Uint8List.fromList(utf8.encode('Not a PDF')), 'fake.pdf'),
      throwsFormatException,
    );
    state.dispose();
  });
  test(
    'Preferências de leitura respeitam limites e preservam quebras do código',
    () {
      final settings = ReaderSettings.fromJson({
        'size': 100,
        'lineHeight': 0,
        'margin': 100,
        'dim': 2,
        'font': 'unknown',
      });
      expect(settings.size, 34);
      expect(settings.lineHeight, 1.2);
      expect(settings.font, 'SourceSerif');
      expect(
        readablePdfText('if (x) {\r\n  return y;\r\n}\n\n\n'),
        'if (x) {\n  return y;\n}',
      );
    },
  );
}
