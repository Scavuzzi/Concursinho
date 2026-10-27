import 'dart:convert';
import 'dart:math';
import 'package:crypto/crypto.dart';
import 'package:sqflite/sqflite.dart';

/// A question is independent of a practice session. Answers use zero-based
/// indices, so both A–E and true/false imports share the same format.
class BankQuestion {
  final String id, subject, topic, stem, explanation, board, role, source;
  final String sourceUrl, answerSourceUrl, classification;
  final List<String> options;
  final int answer, year;
  final String? documentId;
  final List<Map<String, dynamic>> clips;

  BankQuestion.fromJson(Map<String, dynamic> d)
    : id = _text(d, 'id', 240),
      subject = _text(d, 'subject', 120),
      topic = _text(d, 'topic', 160),
      stem = _text(d, 'stem', 50000),
      source = _text(d, 'source', 500),
      options = _options(d['options']),
      answer = d['answer'] is int ? d['answer'] : -1,
      explanation = (d['explanation'] as String?) ?? '',
      board = (d['board'] as String?) ?? '',
      role = (d['role'] as String?) ?? '',
      year = d['year'] is int ? d['year'] : 0,
      sourceUrl = (d['sourceUrl'] as String?) ?? '',
      answerSourceUrl = (d['answerSourceUrl'] as String?) ?? '',
      classification = (d['classification'] as String?) ?? 'provided',
      documentId = d['documentId'] as String?,
      clips = d['clips'] is List
          ? (d['clips'] as List)
                .map((c) => Map<String, dynamic>.from(c as Map))
                .toList()
          : [] {
    if (answer < 0 || answer >= options.length) {
      throw FormatException('Gabarito inválido na questão $id.');
    }
    for (final clip in clips) {
      final rect = clip['rect'];
      if (clip['page'] is! int ||
          clip['page'] < 1 ||
          rect is! List ||
          rect.length != 4 ||
          rect.any((n) => n is! num || !n.isFinite || n < 0) ||
          rect[2] <= rect[0] ||
          rect[3] <= rect[1]) {
        throw FormatException('Recorte inválido na questão $id.');
      }
    }
  }

  static String _text(Map<String, dynamic> d, String key, int max) {
    final v = d[key];
    if (v is! String || v.trim().isEmpty || v.length > max) {
      throw FormatException('Campo $key ausente ou inválido.');
    }
    return v.trim();
  }

  static List<String> _options(dynamic value) {
    if (value is! List ||
        value.length < 2 ||
        value.length > 5 ||
        value.any(
          (o) => o is! String || o.trim().isEmpty || o.length > 30000,
        )) {
      throw const FormatException('Forneça de duas a cinco alternativas.');
    }
    return value.cast<String>().map((s) => s.trim()).toList();
  }

  String get fingerprint => sha256
      .convert(
        utf8.encode(
          [stem, ...options]
              .map(
                (s) => s.toLowerCase().replaceAll(RegExp(r'\s+'), ' ').trim(),
              )
              .join('\n'),
        ),
      )
      .toString();

  Map<String, dynamic> toJson() => {
    'id': id,
    'subject': subject,
    'topic': topic,
    'stem': stem,
    'options': options,
    'answer': answer,
    'explanation': explanation,
    'board': board,
    'role': role,
    'source': source,
    'year': year,
    'sourceUrl': sourceUrl,
    'answerSourceUrl': answerSourceUrl,
    'classification': classification,
    'documentId': documentId,
    'clips': clips,
  };
}

class QuestionFilter {
  final String? subject, topic, board;
  final String mode;
  final bool avoidRepeats;
  const QuestionFilter({
    this.subject,
    this.topic,
    this.board,
    this.mode = 'all',
    this.avoidRepeats = true,
  });
  String get signature =>
      jsonEncode([subject, topic, board, mode, avoidRepeats]);
}

class QuestionDraw {
  final BankQuestion? question;
  final int eligible;
  final bool restarted;
  const QuestionDraw(this.question, this.eligible, this.restarted);
}

class ImportSummary {
  final int added, duplicates, excluded;
  const ImportSummary(this.added, this.duplicates, this.excluded);
}

class TopicPerformance {
  final String subject, topic;
  final String? dominantReason;
  final int answered, correct;
  const TopicPerformance(
    this.subject,
    this.topic,
    this.answered,
    this.correct, {
    this.dominantReason,
  });
  int get errors => answered - correct;
  double get accuracy => answered == 0 ? 0 : correct / answered;
  String get assessment => answered < 10
      ? 'Amostra inicial'
      : accuracy >= .8
      ? 'Ponto forte'
      : accuracy < .6
      ? 'Prioridade de revisão'
      : 'Em desenvolvimento';
}

class PracticeReport {
  final int attempts, correct, unique, bankSize;
  final List<TopicPerformance> topics;
  final List<Map<String, dynamic>> daily, reasons;
  const PracticeReport(
    this.attempts,
    this.correct,
    this.unique,
    this.bankSize,
    this.topics,
    this.daily,
    this.reasons,
  );
}

class QuestionBank {
  final Database db;
  final Random random;
  QuestionBank._(this.db, this.random);
  static const errorReasons = [
    'Não sabia o conteúdo',
    'Interpretação',
    'Distração',
    'Cálculo',
    'Chute',
  ];

  static Future<QuestionBank> open(
    String path, {
    DatabaseFactory? factory,
    Random? random,
  }) async {
    final db = await (factory ?? databaseFactory).openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: 1,
        onConfigure: (db) async => db.execute('PRAGMA foreign_keys = ON'),
        onCreate: (db, version) async {
          await db.execute('''CREATE TABLE questions (
            id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE,
            subject TEXT NOT NULL, topic TEXT NOT NULL, board TEXT NOT NULL,
            payload TEXT NOT NULL)''');
          await db.execute(
            'CREATE INDEX q_filters ON questions(subject,topic,board)',
          );
          await db.execute('''CREATE TABLE attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            question_id TEXT NOT NULL REFERENCES questions(id),
            choice INTEGER NOT NULL, correct INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL, answered_at TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '')''');
          await db.execute(
            'CREATE INDEX a_question ON attempts(question_id,id)',
          );
          await db.execute('CREATE INDEX a_date ON attempts(answered_at)');
          await db.execute(
            'CREATE TABLE draws (question_id TEXT PRIMARY KEY REFERENCES questions(id))',
          );
          await db.execute(
            'CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
          );
        },
      ),
    );
    return QuestionBank._(db, random ?? Random());
  }

  Future<int> count() async =>
      (await db.rawQuery('SELECT COUNT(*) n FROM questions')).first['n'] as int;

  Future<void> seed(String revision, Stream<String> records) async {
    final exists = await db.query(
      'metadata',
      where: 'key = ?',
      whereArgs: ['seed:$revision'],
    );
    if (exists.isNotEmpty) return;
    await _import(records, seedRevision: revision);
  }

  Future<ImportSummary> importLines(Stream<String> records) => _import(records);
  Future<ImportSummary> importJson(String content) async {
    final value = jsonDecode(content);
    final list = value is List
        ? value
        : value is Map && value['schemaVersion'] == 1
        ? value['questions']
        : null;
    if (list is! List) {
      throw const FormatException(
        'Use uma lista ou schemaVersion 1 com questions.',
      );
    }
    return importLines(Stream.fromIterable(list.map(jsonEncode)));
  }

  Future<ImportSummary> _import(
    Stream<String> lines, {
    String? seedRevision,
  }) => db.transaction((txn) async {
    final before =
        (await txn.rawQuery('SELECT COUNT(*) n FROM questions')).first['n']
            as int;
    var accepted = 0, excluded = 0, lineNumber = 0, buffered = 0;
    var batch = txn.batch();
    await for (final line in lines) {
      lineNumber++;
      if (line.trim().isEmpty) continue;
      if (line.length > 250000) {
        throw FormatException('Linha $lineNumber excede o tamanho permitido.');
      }
      try {
        final raw = jsonDecode(line);
        if (raw is! Map<String, dynamic>) {
          throw const FormatException('Objeto de questão esperado.');
        }
        if (raw['annulled'] == true) {
          excluded++;
          continue;
        }
        final q = BankQuestion.fromJson(raw);
        batch.insert('questions', {
          'id': q.id,
          'fingerprint': q.fingerprint,
          'subject': q.subject,
          'topic': q.topic,
          'board': q.board,
          'payload': jsonEncode(q.toJson()),
        }, conflictAlgorithm: ConflictAlgorithm.ignore);
        accepted++;
        buffered++;
        if (buffered >= 500) {
          await batch.commit(noResult: true);
          batch = txn.batch();
          buffered = 0;
        }
      } on FormatException catch (e) {
        throw FormatException('Linha $lineNumber: ${e.message}');
      } on TypeError {
        throw FormatException('Linha $lineNumber: tipo de campo inválido.');
      }
    }
    if (buffered > 0) await batch.commit(noResult: true);
    final after =
        (await txn.rawQuery('SELECT COUNT(*) n FROM questions')).first['n']
            as int;
    if (seedRevision != null) {
      await txn.insert('metadata', {
        'key': 'seed:$seedRevision',
        'value': 'done',
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }
    return ImportSummary(after - before, accepted - (after - before), excluded);
  });

  Future<List<String>> subjects() async => (await db.rawQuery(
    'SELECT DISTINCT subject FROM questions ORDER BY subject COLLATE NOCASE',
  )).map((r) => r['subject'] as String).toList();
  Future<List<String>> topics(String? subject) async => (await db.rawQuery(
    'SELECT DISTINCT topic FROM questions ${subject == null ? '' : 'WHERE subject = ?'} ORDER BY topic COLLATE NOCASE',
    subject == null ? [] : [subject],
  )).map((r) => r['topic'] as String).toList();
  Future<List<String>> boards() async => (await db.rawQuery(
    "SELECT DISTINCT board FROM questions WHERE board <> '' ORDER BY board",
  )).map((r) => r['board'] as String).toList();

  (String, List<Object?>) _where(QuestionFilter f) {
    final clauses = <String>['1=1'], args = <Object?>[];
    for (final entry in {
      'subject': f.subject,
      'topic': f.topic,
      'board': f.board,
    }.entries) {
      if (entry.value != null) {
        clauses.add('q.${entry.key} = ?');
        args.add(entry.value);
      }
    }
    if (f.mode == 'unanswered') {
      clauses.add(
        'NOT EXISTS (SELECT 1 FROM attempts a WHERE a.question_id=q.id)',
      );
    }
    if (f.mode == 'errors') {
      clauses.add(
        'EXISTS (SELECT 1 FROM attempts a WHERE a.question_id=q.id AND a.id=(SELECT MAX(b.id) FROM attempts b WHERE b.question_id=q.id) AND a.correct=0)',
      );
    }
    return (clauses.join(' AND '), args);
  }

  /// Count + random offset keeps all eligible items equally likely without
  /// shuffling question payloads or building an enormous IN (...) expression.
  Future<QuestionDraw> draw(QuestionFilter filter) => db.transaction((
    txn,
  ) async {
    final (where, args) = _where(filter);
    final eligible =
        (await txn.rawQuery(
              'SELECT COUNT(*) n FROM questions q WHERE $where',
              args,
            )).first['n']
            as int;
    if (eligible == 0) return const QuestionDraw(null, 0, false);
    final meta = await txn.query(
      'metadata',
      where: 'key=?',
      whereArgs: ['draw_filter'],
    );
    if (meta.isEmpty || meta.first['value'] != filter.signature) {
      await txn.delete('draws');
      await txn.insert('metadata', {
        'key': 'draw_filter',
        'value': filter.signature,
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }
    final withoutSeen = filter.avoidRepeats
        ? ' AND NOT EXISTS (SELECT 1 FROM draws d WHERE d.question_id=q.id)'
        : '';
    var available =
        (await txn.rawQuery(
              'SELECT COUNT(*) n FROM questions q WHERE $where$withoutSeen',
              args,
            )).first['n']
            as int;
    var restarted = false;
    if (available == 0) {
      await txn.delete('draws');
      available = eligible;
      restarted = true;
    }
    final selected = (await txn.rawQuery(
      'SELECT q.id FROM questions q WHERE $where$withoutSeen ORDER BY q.id LIMIT 1 OFFSET ?',
      [...args, random.nextInt(available)],
    )).single;
    final row = (await txn.query(
      'questions',
      columns: ['payload'],
      where: 'id=?',
      whereArgs: [selected['id']],
      limit: 1,
    )).single;
    final q = BankQuestion.fromJson(jsonDecode(row['payload'] as String));
    if (filter.avoidRepeats) {
      await txn.insert('draws', {
        'question_id': q.id,
      }, conflictAlgorithm: ConflictAlgorithm.ignore);
    }
    return QuestionDraw(q, eligible, restarted);
  });

  Future<bool> answer(
    BankQuestion question,
    int choice, {
    required String eventId,
    required int durationMs,
    String reason = '',
    DateTime? at,
  }) async {
    if (choice < 0 || choice >= question.options.length || eventId.isEmpty) {
      throw ArgumentError('Resposta inválida.');
    }
    final found = await db.query(
      'questions',
      columns: ['payload'],
      where: 'id=?',
      whereArgs: [question.id],
      limit: 1,
    );
    if (found.isEmpty) throw StateError('Questão ausente do banco.');
    final canonical = BankQuestion.fromJson(
      jsonDecode(found.single['payload'] as String),
    );
    if (choice >= canonical.options.length) {
      throw ArgumentError('Alternativa inválida.');
    }
    final correct = choice == canonical.answer;
    await db.insert('attempts', {
      'event_id': eventId,
      'question_id': question.id,
      'choice': choice,
      'correct': correct ? 1 : 0,
      'duration_ms': durationMs.clamp(0, 86400000),
      'answered_at': (at ?? DateTime.now()).toUtc().toIso8601String(),
      'reason': !correct && errorReasons.contains(reason) ? reason : '',
    }, conflictAlgorithm: ConflictAlgorithm.ignore);
    return correct;
  }

  Future<void> tagError(String eventId, String reason) async {
    if (!errorReasons.contains(reason)) throw ArgumentError('Motivo inválido.');
    await db.update(
      'attempts',
      {'reason': reason},
      where: 'event_id=? AND correct=0',
      whereArgs: [eventId],
    );
  }

  Future<BankQuestion> reclassify(
    BankQuestion question,
    String subject,
    String topic,
  ) async {
    final updated = BankQuestion.fromJson({
      ...question.toJson(),
      'subject': subject.trim(),
      'topic': topic.trim(),
      'classification': 'reviewed-by-user',
    });
    await db.update(
      'questions',
      {
        'subject': updated.subject,
        'topic': updated.topic,
        'payload': jsonEncode(updated.toJson()),
      },
      where: 'id=?',
      whereArgs: [updated.id],
    );
    return updated;
  }

  Future<PracticeReport> report({int days = 0, String? subject}) async {
    final cutoff = days > 0
        ? DateTime.now()
              .subtract(Duration(days: days))
              .toUtc()
              .toIso8601String()
        : '';
    final extra = subject == null ? '' : ' AND q.subject=?';
    final args = <Object?>[cutoff, ?subject];
    final summary = (await db.rawQuery(
      'SELECT COUNT(*) n,COALESCE(SUM(a.correct),0) c,COUNT(DISTINCT a.question_id) u FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.answered_at>=?$extra',
      args,
    )).single;
    final first = await db.rawQuery(
      '''SELECT q.subject,q.topic,COUNT(*) n,SUM(a.correct) c
      FROM attempts a JOIN questions q ON q.id=a.question_id
      WHERE a.answered_at>=?$extra AND a.id=(SELECT MIN(b.id) FROM attempts b WHERE b.question_id=a.question_id AND b.answered_at>=?)
      GROUP BY q.subject,q.topic ORDER BY CAST(SUM(a.correct) AS REAL)/COUNT(*),COUNT(*) DESC''',
      [...args, cutoff],
    );
    final daily = await db.rawQuery(
      '''SELECT date(a.answered_at,'localtime') day,COUNT(*) n,SUM(a.correct) c
      FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.answered_at>=?$extra GROUP BY day ORDER BY day''',
      args,
    );
    final reasons = await db.rawQuery(
      '''SELECT CASE WHEN a.reason='' THEN 'Não informado' ELSE a.reason END reason,COUNT(*) n
      FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.correct=0 AND a.answered_at>=?$extra GROUP BY reason ORDER BY n DESC''',
      args,
    );
    final byTopic = await db.rawQuery(
      '''SELECT q.subject,q.topic,a.reason,COUNT(*) n
      FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.correct=0
      AND a.reason<>'' AND a.answered_at>=?$extra GROUP BY q.subject,q.topic,a.reason ORDER BY n DESC''',
      args,
    );
    final dominant = <String, String>{};
    for (final row in byTopic) {
      dominant.putIfAbsent(
        jsonEncode([row['subject'], row['topic']]),
        () => row['reason'] as String,
      );
    }
    return PracticeReport(
      summary['n'] as int,
      summary['c'] as int,
      summary['u'] as int,
      await count(),
      first
          .map(
            (r) => TopicPerformance(
              r['subject'] as String,
              r['topic'] as String,
              r['n'] as int,
              r['c'] as int,
              dominantReason: dominant[jsonEncode([r['subject'], r['topic']])],
            ),
          )
          .toList(),
      daily,
      reasons,
    );
  }

  Future<String> exportReportCsv({int days = 0, String? subject}) async {
    final r = await report(days: days, subject: subject);
    String cell(Object value) {
      var text = value.toString();
      if (RegExp(r'^[=+\-@\t\r]').hasMatch(text)) text = "'$text";
      return '"${text.replaceAll('"', '""')}"';
    }

    return '\uFEFFassunto;topico;primeiras_respostas;acertos;erros;percentual_acertos\n${r.topics.map((t) => [t.subject, t.topic, t.answered, t.correct, t.errors, (100 * t.accuracy).toStringAsFixed(1)].map(cell).join(';')).join('\n')}';
  }

  Future<void> close() => db.close();
}

String improvementAdvice(TopicPerformance t, String? dominantReason) {
  if (t.answered < 10) {
    return 'Responda mais ${10 - t.answered} questões diferentes deste tópico antes de avaliar seu domínio.';
  }
  if (t.accuracy >= .8) {
    return 'Mantenha revisões espaçadas e teste questões novas para confirmar a retenção.';
  }
  if (dominantReason == 'Interpretação') {
    return 'Leia o comando antes das alternativas, destaque negações e explique por que cada alternativa está errada.';
  }
  if (dominantReason == 'Distração') {
    return 'Faça séries curtas e revise o comando e a alternativa marcada antes de confirmar.';
  }
  if (dominantReason == 'Cálculo') {
    return 'Refaça os passos sem consultar a solução e registre onde o cálculo saiu do caminho.';
  }
  if (t.subject.contains('Banco')) {
    return 'Pratique consultas em um banco de teste e compare o resultado esperado com cada alternativa.';
  }
  if (t.subject.contains('Desenvolvimento') ||
      t.subject.contains('Arquitetura')) {
    return 'Monte um exemplo pequeno do conceito, execute-o e explique a diferença entre as alternativas.';
  }
  return 'Revise a teoria deste tópico, registre a causa de cada erro e volte com uma série de questões diferentes.';
}
