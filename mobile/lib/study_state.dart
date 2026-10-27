import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

class StudyTopic {
  final String id, group, text;
  StudyTopic(Map<String, dynamic> d)
    : id = d['id'],
      group = d['group'],
      text = d['text'];
}

class StudyDocument {
  final String id, title, kind;
  final String? asset, path;
  final int initialPage;
  StudyDocument(Map<String, dynamic> d)
    : id = d['id'],
      title = d['title'],
      kind = d['kind'],
      asset = d['asset'],
      path = d['path'],
      initialPage = d['initialPage'] ?? 1;
  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'kind': kind,
    'asset': asset,
    'path': path,
    'initialPage': initialPage,
  };
}

class StudyExam {
  final String id, title, description;
  final Map<String, String> documents;
  StudyExam(Map<String, dynamic> d)
    : id = d['id'],
      title = d['title'],
      description = d['description'],
      documents = Map<String, String>.from(d['documents']);
}

class StudyCatalog {
  final List<StudyTopic> topics;
  final List<StudyExam> exams;
  final List<StudyDocument> documents;
  StudyCatalog(Map<String, dynamic> d)
    : topics = (d['topics'] as List)
          .map((e) => StudyTopic(Map<String, dynamic>.from(e)))
          .toList(),
      exams = (d['exams'] as List)
          .map((e) => StudyExam(Map<String, dynamic>.from(e)))
          .toList(),
      documents = (d['documents'] as List)
          .map((e) => StudyDocument(Map<String, dynamic>.from(e)))
          .toList();
  List<String> get groups => topics.map((e) => e.group).toSet().toList();
  static Future<StudyCatalog> load() async => StudyCatalog(
    jsonDecode(await rootBundle.loadString('assets/data/catalog.json')),
  );
}

abstract class StudyStorage {
  Future<Map<String, dynamic>> read();
  Future<void> write(Map<String, dynamic> data);
}

class FileStudyStorage implements StudyStorage {
  final File file;
  FileStudyStorage(Directory dir) : file = File('${dir.path}/study-state.json');
  @override
  Future<Map<String, dynamic>> read() async {
    for (final candidate in [file, File('${file.path}.bak')]) {
      try {
        final data = jsonDecode(await candidate.readAsString());
        if (data is Map<String, dynamic>) return data;
      } on FileSystemException {
        /* Try backup. */
      } on FormatException {
        /* Try backup. */
      }
    }
    return {};
  }

  @override
  Future<void> write(Map<String, dynamic> data) async {
    await file.parent.create(recursive: true);
    final temporary = File('${file.path}.tmp');
    await temporary.writeAsString(jsonEncode(data), flush: true);
    if (await file.exists()) {
      try {
        jsonDecode(await file.readAsString());
        await file.copy('${file.path}.bak');
      } on FormatException {
        /* Preserve good backup. */
      }
    }
    await temporary.rename(file.path);
  }
}

class ReaderSettings {
  String theme, font;
  double size, lineHeight, margin, dim;
  bool justify;
  ReaderSettings({
    this.theme = 'paper',
    this.font = 'SourceSerif',
    this.size = 20,
    this.lineHeight = 1.65,
    this.margin = 24,
    this.dim = 0,
    this.justify = false,
  });
  factory ReaderSettings.fromJson(Map<String, dynamic> d) => ReaderSettings(
    theme: ['paper', 'sepia', 'night'].contains(d['theme'])
        ? d['theme']
        : 'paper',
    font: ['SourceSerif', 'DMSans', 'JetBrainsMono'].contains(d['font'])
        ? d['font']
        : 'SourceSerif',
    size: ((d['size'] as num?)?.toDouble() ?? 20).clamp(14, 34),
    lineHeight: ((d['lineHeight'] as num?)?.toDouble() ?? 1.65).clamp(1.2, 2.2),
    margin: ((d['margin'] as num?)?.toDouble() ?? 24).clamp(12, 48),
    dim: ((d['dim'] as num?)?.toDouble() ?? 0).clamp(0, .5),
    justify: d['justify'] == true,
  );
  Map<String, dynamic> toJson() => {
    'theme': theme,
    'font': font,
    'size': size,
    'lineHeight': lineHeight,
    'margin': margin,
    'dim': dim,
    'justify': justify,
  };
}

class StudyState extends ChangeNotifier {
  final StudyCatalog catalog;
  final StudyStorage storage;
  final Directory directory;
  Set<String> completed = {};
  Map<String, int> positions = {};
  Map<String, List<int>> bookmarks = {};
  List<StudyDocument> imported = [];
  ReaderSettings reader = ReaderSettings();
  String? lastDocument, saveError;
  String focusSubject = 'Revisão geral';
  int focusDuration = 1500, remaining = 1500, focusMinutes = 0;
  DateTime? focusEnd;
  Timer? _timer;
  Future<void> _pending = Future.value();
  StudyState(this.catalog, this.storage, this.directory);
  Future<void> load() async {
    final d = await storage.read();
    final known = {
      ...catalog.topics.map((e) => e.id),
      ...catalog.exams.map((e) => e.id),
    };
    completed =
        (d['completed'] is List
                ? (d['completed'] as List).whereType<String>().toSet()
                : <String>{})
            .intersection(known);
    if (d['positions'] is Map) {
      positions = (d['positions'] as Map).map(
        (k, v) =>
            MapEntry(k.toString(), v is num ? v.toInt().clamp(1, 100000) : 1),
      );
    }
    if (d['bookmarks'] is Map) {
      bookmarks = (d['bookmarks'] as Map).map(
        (k, v) => MapEntry(
          k.toString(),
          v is List
              ? v
                    .whereType<num>()
                    .map((p) => p.toInt())
                    .where((p) => p > 0)
                    .toSet()
                    .toList()
              : <int>[],
        ),
      );
    }
    if (d['reader'] is Map) {
      reader = ReaderSettings.fromJson(Map<String, dynamic>.from(d['reader']));
    }
    if (d['imported'] is List) {
      for (final item in d['imported']) {
        if (item is! Map || item['id'] is! String || item['title'] is! String) {
          continue;
        }
        final id = item['id'] as String;
        if (!RegExp(r'^[a-f0-9]{64}$').hasMatch(id)) continue;
        final path = '${directory.path}/imports/$id.pdf';
        if (File(path).existsSync()) {
          imported.add(
            StudyDocument({
              ...Map<String, dynamic>.from(item),
              'path': path,
              'kind': 'importado',
            }),
          );
        }
      }
    }
    lastDocument = d['lastDocument'] is String ? d['lastDocument'] : null;
    focusMinutes = (d['focusMinutes'] is int ? d['focusMinutes'] as int : 0)
        .clamp(0, 1000000);
    focusDuration =
        (d['focusDuration'] is int ? d['focusDuration'] as int : 1500).clamp(
          300,
          7200,
        );
    remaining = (d['remaining'] is int ? d['remaining'] as int : focusDuration)
        .clamp(0, focusDuration);
    focusSubject = d['focusSubject'] is String
        ? d['focusSubject']
        : 'Revisão geral';
    if (d['focusEnd'] is String) focusEnd = DateTime.tryParse(d['focusEnd']);
    if (focusEnd != null) {
      tick();
      _startTicker();
    }
    notifyListeners();
  }

  List<StudyDocument> get allDocuments => [...catalog.documents, ...imported];
  StudyDocument? document(String? id) {
    for (final doc in allDocuments) {
      if (doc.id == id) return doc;
    }
    return null;
  }

  int get topicCount =>
      catalog.topics.where((e) => completed.contains(e.id)).length;
  int get examCount =>
      catalog.exams.where((e) => completed.contains(e.id)).length;
  Map<String, dynamic> toJson() => {
    'schemaVersion': 1,
    'completed': completed.toList(),
    'positions': positions,
    'bookmarks': bookmarks,
    'reader': reader.toJson(),
    'lastDocument': lastDocument,
    'imported': imported.map((e) => e.toJson()).toList(),
    'focusDuration': focusDuration,
    'remaining': remaining,
    'focusEnd': focusEnd?.toIso8601String(),
    'focusSubject': focusSubject,
    'focusMinutes': focusMinutes,
  };
  Future<void> persist() {
    final snapshot = jsonDecode(jsonEncode(toJson())) as Map<String, dynamic>;
    _pending = _pending.then((_) async {
      try {
        await storage.write(snapshot);
        saveError = null;
      } catch (_) {
        saveError =
            'Não foi possível salvar. Exporte seu progresso antes de sair.';
        notifyListeners();
      }
    });
    return _pending;
  }

  void toggle(String id) {
    completed.contains(id) ? completed.remove(id) : completed.add(id);
    notifyListeners();
    unawaited(persist());
  }

  void setPosition(String id, int page) {
    if (page < 1) return;
    positions[id] = page;
    lastDocument = id;
    notifyListeners();
    unawaited(persist());
  }

  void toggleBookmark(String id, int page) {
    final pages = bookmarks.putIfAbsent(id, () => []);
    pages.contains(page) ? pages.remove(page) : pages.add(page);
    pages.sort();
    notifyListeners();
    unawaited(persist());
  }

  void updateReader() {
    notifyListeners();
    unawaited(persist());
  }

  Future<String> localPath(StudyDocument doc) async {
    if (doc.path != null) return doc.path!;
    final file = File('${directory.path}/pdfs/${doc.id}.pdf');
    if (!await file.exists()) {
      await file.parent.create(recursive: true);
      final data = await rootBundle.load(doc.asset!);
      await file.writeAsBytes(
        data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
        flush: true,
      );
    }
    return file.path;
  }

  Future<StudyDocument> importPdf(Uint8List bytes, String name) async {
    if (bytes.length < 5 ||
        !latin1.decode(bytes.take(1024).toList()).contains('%PDF-')) {
      throw const FormatException('O arquivo escolhido não é um PDF válido.');
    }
    final id = sha256.convert(bytes).toString();
    final existing = document(id);
    if (existing != null) return existing;
    final file = File('${directory.path}/imports/$id.pdf');
    await file.parent.create(recursive: true);
    await file.writeAsBytes(bytes, flush: true);
    final doc = StudyDocument({
      'id': id,
      'title': name,
      'path': file.path,
      'kind': 'importado',
    });
    imported.add(doc);
    notifyListeners();
    await persist();
    return doc;
  }

  Future<int> importProgress(String content) async {
    final data = jsonDecode(content);
    final values = data is List
        ? data
        : data is Map
        ? data['completed']
        : null;
    if (values is! List) {
      throw const FormatException(
        'Escolha uma lista de progresso do Concursinho.',
      );
    }
    final known = {
      ...catalog.topics.map((e) => e.id),
      ...catalog.exams.map((e) => e.id),
    };
    final valid = values.whereType<String>().toSet().intersection(known);
    completed.addAll(valid);
    notifyListeners();
    await persist();
    return valid.length;
  }

  void setDuration(int minutes) {
    if (focusEnd != null) return;
    focusDuration = minutes.clamp(5, 120) * 60;
    remaining = focusDuration;
    notifyListeners();
    unawaited(persist());
  }

  void startFocus() {
    if (focusEnd != null) return;
    if (remaining <= 0) remaining = focusDuration;
    focusEnd = DateTime.now().add(Duration(seconds: remaining));
    _startTicker();
    notifyListeners();
    unawaited(persist());
  }

  void pauseFocus() {
    tick();
    focusEnd = null;
    _timer?.cancel();
    notifyListeners();
    unawaited(persist());
  }

  void resetFocus() {
    focusEnd = null;
    _timer?.cancel();
    remaining = focusDuration;
    notifyListeners();
    unawaited(persist());
  }

  void _startTicker() {
    _timer?.cancel();
    if (focusEnd != null) {
      _timer = Timer.periodic(const Duration(seconds: 1), (_) => tick());
    }
  }

  void tick() {
    if (focusEnd == null) return;
    remaining = (focusEnd!.difference(DateTime.now()).inMilliseconds / 1000)
        .ceil()
        .clamp(0, focusDuration);
    if (remaining == 0) {
      focusEnd = null;
      _timer?.cancel();
      focusMinutes += focusDuration ~/ 60;
      unawaited(persist());
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}

String readablePdfText(String raw) => raw
    .replaceAll('\r\n', '\n')
    .replaceAll('\r', '\n')
    .replaceAll(RegExp(r'[ \t]+\n'), '\n')
    .replaceAll(RegExp(r'\n{3,}'), '\n\n')
    .trim();
