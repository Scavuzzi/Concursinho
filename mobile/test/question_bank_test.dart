import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:concursinho_mobile/question_bank.dart';

Map<String, dynamic> fixture(
  int i, {
  String subject = 'Banco de dados',
  String topic = 'SQL',
  int answer = 0,
}) => {
  'id': 'test:$i',
  'subject': subject,
  'topic': topic,
  'stem': 'Enunciado independente número $i?',
  'options': ['Alternativa correta $i', 'Outra alternativa $i'],
  'answer': answer,
  'source': 'Questão fictícia exclusiva para teste',
  'board': 'Teste',
};
Stream<String> batch(Iterable<Map<String, dynamic>> data) =>
    Stream.fromIterable(data.map(jsonEncode));

void main() {
  setUpAll(sqfliteFfiInit);
  late Directory dir;
  late QuestionBank bank;
  setUp(() async {
    dir = await Directory.systemTemp.createTemp('question-bank-test-');
    bank = await QuestionBank.open(
      '${dir.path}/bank.db',
      factory: databaseFactoryFfi,
      random: Random(43),
    );
  });
  tearDown(() async {
    await bank.close();
    await dir.delete(recursive: true);
  });

  test(
    'Importação é atômica mesmo com falha depois de um lote já processado',
    () async {
      final items = [
        ...List.generate(501, fixture),
        {'id': 'broken'},
      ];
      await expectLater(bank.importLines(batch(items)), throwsFormatException);
      expect(await bank.count(), 0);
    },
  );
  test(
    'Deduplicação por conteúdo e por ID preserva a questão já existente',
    () async {
      final q = fixture(1);
      await bank.importLines(batch([q]));
      final result = await bank.importLines(
        batch([
          {...q, 'id': 'different'},
          fixture(1, answer: 1),
          fixture(2),
        ]),
      );
      expect(result.added, 1);
      expect(result.duplicates, 2);
      final all = await bank.db.query('questions');
      expect(all.length, 2);
      expect(
        BankQuestion.fromJson(
          jsonDecode(all.first['payload'] as String),
        ).answer,
        0,
      );
    },
  );
  test('Ciclo aleatório visita todas uma vez e só depois reinicia', () async {
    await bank.importLines(batch(List.generate(12, fixture)));
    final ids = <String>{};
    for (var i = 0; i < 12; i++) {
      final draw = await bank.draw(const QuestionFilter());
      expect(draw.restarted, isFalse);
      expect(ids.add(draw.question!.id), isTrue);
    }
    expect((await bank.draw(const QuestionFilter())).restarted, isTrue);
  });
  test(
    'Sorteio filtra assunto/tópico, aceita resultados vazios e troca recorte',
    () async {
      await bank.importLines(
        batch([fixture(1), fixture(2, subject: 'Segurança', topic: 'OWASP')]),
      );
      expect(
        (await bank.draw(
          const QuestionFilter(subject: 'Segurança', topic: 'OWASP'),
        )).question!.id,
        'test:2',
      );
      expect(
        (await bank.draw(const QuestionFilter(subject: 'Não existe'))).question,
        isNull,
      );
      expect(
        (await bank.draw(
          const QuestionFilter(subject: 'Banco de dados'),
        )).question!.id,
        'test:1',
      );
    },
  );
  test(
    'Sorteios independentes permitem repetir sem anunciar reinício de ciclo',
    () async {
      await bank.importLines(batch([fixture(1)]));
      for (var i = 0; i < 4; i++) {
        final draw = await bank.draw(const QuestionFilter(avoidRepeats: false));
        expect(draw.question!.id, 'test:1');
        expect(draw.restarted, isFalse);
      }
    },
  );
  test(
    'Confirmação duplicada não duplica tentativa; primeira resposta não é inflada',
    () async {
      await bank.importLines(batch([fixture(1)]));
      final q = (await bank.draw(const QuestionFilter())).question!;
      await bank.answer(q, 1, eventId: 'one', durationMs: 1000);
      await bank.answer(q, 1, eventId: 'one', durationMs: 1000);
      await bank.answer(q, 0, eventId: 'two', durationMs: 500);
      final r = await bank.report();
      expect(r.attempts, 2);
      expect(r.correct, 1);
      expect(r.unique, 1);
      expect(r.topics.single.answered, 1);
      expect(r.topics.single.correct, 0);
      expect(r.topics.single.assessment, 'Amostra inicial');
      expect(
        (await bank.draw(const QuestionFilter(mode: 'errors'))).question,
        isNull,
      );
      expect(
        (await bank.draw(const QuestionFilter(mode: 'unanswered'))).question,
        isNull,
      );
    },
  );
  test('Erros usa a última resposta e registra motivo só para erro', () async {
    await bank.importLines(batch([fixture(1), fixture(2)]));
    final q = (await bank.draw(const QuestionFilter())).question!;
    await bank.answer(q, 1, eventId: 'bad', durationMs: 50);
    await bank.tagError('bad', 'Interpretação');
    final r = await bank.report();
    expect(r.reasons.single['reason'], 'Interpretação');
    expect(
      (await bank.draw(const QuestionFilter(mode: 'errors'))).question!.id,
      q.id,
    );
  });
  test(
    'Anuladas ficam fora; alternativas e gabarito inválidos são rejeitados',
    () async {
      final r = await bank.importLines(
        batch([
          {...fixture(1), 'annulled': true},
        ]),
      );
      expect(r.excluded, 1);
      expect(await bank.count(), 0);
      await expectLater(
        bank.importLines(batch([fixture(2, answer: 2)])),
        throwsFormatException,
      );
      await expectLater(
        bank.importLines(
          batch([
            {
              ...fixture(3),
              'options': ['A'],
            },
          ]),
        ),
        throwsFormatException,
      );
    },
  );
  test('Progresso e ciclo sobrevivem à reabertura do SQLite', () async {
    await bank.importLines(batch([fixture(1), fixture(2)]));
    final first = (await bank.draw(const QuestionFilter())).question!;
    await bank.answer(first, 0, eventId: 'persist', durationMs: 1);
    await bank.close();
    bank = await QuestionBank.open(
      '${dir.path}/bank.db',
      factory: databaseFactoryFfi,
    );
    expect((await bank.report()).attempts, 1);
    expect(
      (await bank.draw(const QuestionFilter())).question!.id,
      isNot(first.id),
    );
  });
  test('Período e assunto limitam corretamente a primeira resposta', () async {
    await bank.importLines(
      batch([fixture(1), fixture(2, subject: 'Segurança')]),
    );
    final q = BankQuestion.fromJson(fixture(1));
    await bank.answer(
      q,
      1,
      eventId: 'old',
      durationMs: 1,
      at: DateTime.now().subtract(const Duration(days: 40)),
    );
    await bank.answer(q, 0, eventId: 'new', durationMs: 1);
    expect((await bank.report()).topics.single.correct, 0);
    expect((await bank.report(days: 7)).topics.single.correct, 1);
    expect((await bank.report(subject: 'Segurança')).attempts, 0);
  });
  test(
    'Nova revisão da base preserva respostas e classificação pessoal',
    () async {
      await bank.seed('v1', batch([fixture(1)]));
      final q = BankQuestion.fromJson(fixture(1));
      await bank.answer(q, 1, eventId: 'before-upgrade', durationMs: 1);
      await bank.reclassify(q, 'Minha disciplina', 'Meu tópico');
      await bank.seed('v2', batch([fixture(1), fixture(2)]));
      await bank.seed('v2', batch([fixture(1), fixture(2)]));
      expect(await bank.count(), 2);
      final report = await bank.report();
      expect(report.attempts, 1);
      expect(report.topics.single.subject, 'Minha disciplina');
    },
  );
  test(
    'Banco com 10000 itens mantém sorteio, filtros e deduplicação funcionais',
    () async {
      await bank.importLines(
        batch(
          List.generate(
            10000,
            (i) => fixture(i, subject: i.isEven ? 'SQL' : 'Redes'),
          ),
        ),
      );
      expect(await bank.count(), 10000);
      for (var i = 0; i < 8; i++) {
        final q = (await bank.draw(
          const QuestionFilter(subject: 'SQL'),
        )).question!;
        expect(q.subject, 'SQL');
      }
    },
  );
}
