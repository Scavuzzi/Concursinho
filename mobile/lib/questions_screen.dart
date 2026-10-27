import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'question_bank.dart';
import 'question_excerpt.dart';
import 'reader_screen.dart';
import 'study_state.dart';

const _green = Color(0xff244c3b),
    _red = Color(0xffa44e39),
    _ochre = Color(0xffa87331);

class QuestionsScreen extends StatefulWidget {
  final StudyState study;
  final QuestionBank? bank;
  const QuestionsScreen({super.key, required this.study, this.bank});
  @override
  State<QuestionsScreen> createState() => _QuestionsScreenState();
}

class _QuestionsScreenState extends State<QuestionsScreen> {
  QuestionBank? _bank;
  String? _error;
  bool _busy = true, _analytics = false, _original = true;
  QuestionFilter _filter = const QuestionFilter();
  QuestionDraw? _draw;
  int? _choice;
  bool? _correct;
  String? _reason;
  String _event = '';
  final _watch = Stopwatch();
  final _scroll = ScrollController();
  List<String> _subjects = [], _boards = [];
  Future<PracticeReport>? _report;
  int _days = 0, _bankSize = 0;
  String? _statSubject;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    QuestionBank? bank;
    try {
      bank =
          widget.bank ??
          await QuestionBank.open(
            '${widget.study.directory.path}/question-bank.sqlite3',
          );
      if (widget.bank == null) {
        await bank.seed(
          'fgv-2026-10-27-v1',
          Stream.fromIterable(
            const LineSplitter().convert(
              await rootBundle.loadString('assets/data/questoes.jsonl'),
            ),
          ),
        );
      }
      final subjects = await bank.subjects(),
          boards = await bank.boards(),
          count = await bank.count();
      if (!mounted) {
        if (widget.bank == null) await bank.close();
        return;
      }
      setState(() {
        _bank = bank;
        _subjects = subjects;
        _boards = boards;
        _bankSize = count;
        _busy = false;
        _refreshReport();
      });
    } catch (_) {
      if (widget.bank == null) await bank?.close();
      if (mounted) {
        setState(() {
          _busy = false;
          _error =
              'Não foi possível abrir o banco. Seus PDFs e o plano continuam disponíveis.';
        });
      }
    }
  }

  void _message(String text) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    }
  }

  void _refreshReport() {
    _report = _bank?.report(days: _days, subject: _statSubject);
  }

  Future<void> _next() async {
    if (_busy || _bank == null) return;
    setState(() => _busy = true);
    try {
      final draw = await _bank!.draw(_filter);
      if (!mounted) return;
      setState(() {
        _draw = draw;
        _choice = null;
        _correct = null;
        _reason = null;
        _busy = false;
        _event =
            '${DateTime.now().microsecondsSinceEpoch}:${Random().nextInt(0x7fffffff)}';
        _watch
          ..reset()
          ..start();
      });
      if (_scroll.hasClients) _scroll.jumpTo(0);
      if (draw.restarted) {
        _message(
          'Você percorreu o conjunto filtrado. Um novo ciclo aleatório começou.',
        );
      }
    } catch (_) {
      if (mounted) setState(() => _busy = false);
      _message('Não foi possível sortear. Tente novamente.');
    }
  }

  Future<void> _answer() async {
    final q = _draw?.question;
    if (_busy || _choice == null || q == null || _correct != null) return;
    setState(() => _busy = true);
    try {
      final correct = await _bank!.answer(
        q,
        _choice!,
        eventId: _event,
        durationMs: _watch.elapsedMilliseconds,
      );
      _watch.stop();
      if (!mounted) return;
      setState(() {
        _correct = correct;
        _busy = false;
        _refreshReport();
      });
    } catch (_) {
      if (mounted) setState(() => _busy = false);
      _message('A resposta não foi salva. Tente confirmar novamente.');
    }
  }

  Future<void> _import() async {
    if (_busy || _bank == null) return;
    try {
      final file = await FilePicker.pickFile(
        type: FileType.custom,
        allowedExtensions: ['jsonl', 'ndjson', 'json'],
      );
      if (file == null || !mounted) return;
      setState(() => _busy = true);
      late ImportSummary result;
      if (file.name.toLowerCase().endsWith('.json')) {
        final chunks = <int>[];
        await for (final chunk in file.readAsByteStream()) {
          chunks.addAll(chunk);
          if (chunks.length > 30 * 1024 * 1024) {
            throw const FormatException(
              'Para lotes maiores que 30 MB, use JSONL.',
            );
          }
        }
        result = await _bank!.importJson(utf8.decode(chunks));
      } else {
        result = await _bank!.importLines(
          file
              .readAsByteStream()
              .map<List<int>>((chunk) => chunk)
              .transform(utf8.decoder)
              .transform(const LineSplitter()),
        );
      }
      final subjects = await _bank!.subjects(),
          boards = await _bank!.boards(),
          count = await _bank!.count();
      if (!mounted) return;
      setState(() {
        _subjects = subjects;
        _boards = boards;
        _bankSize = count;
        _busy = false;
        _refreshReport();
      });
      _message(
        '${result.added} novas; ${result.duplicates} já existentes; ${result.excluded} anuladas excluídas.',
      );
    } on FormatException catch (e) {
      if (mounted) setState(() => _busy = false);
      _message('${e.message} Nenhuma questão desse lote foi adicionada.');
    } catch (_) {
      if (mounted) setState(() => _busy = false);
      _message(
        'Não foi possível importar. Use o formato JSON/JSONL do Concursinho.',
      );
    }
  }

  Future<void> _exportStats() async {
    try {
      final csv = await _bank!.exportReportCsv(
        days: _days,
        subject: _statSubject,
      );
      await FilePicker.saveFile(
        fileName: 'concursinho-desempenho.csv',
        bytes: utf8.encode(csv),
      );
    } catch (_) {
      _message('Não foi possível exportar os indicadores.');
    }
  }

  Future<void> _filters() async {
    if (_busy || _bank == null) return;
    var subject = _filter.subject, topic = _filter.topic, board = _filter.board;
    var mode = _filter.mode, avoid = _filter.avoidRepeats;
    var topics = await _bank!.topics(subject);
    if (!mounted) return;
    final result = await showModalBottomSheet<QuestionFilter>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Escolha o recorte.',
                  style: TextStyle(fontFamily: 'SourceSerif', fontSize: 28),
                ),
                const SizedBox(height: 20),
                DropdownButtonFormField<String>(
                  key: ValueKey('subject:$subject'),
                  initialValue: subject,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Assunto'),
                  items: [
                    const DropdownMenuItem(
                      value: null,
                      child: Text('Todos os assuntos'),
                    ),
                    ..._subjects.map(
                      (s) => DropdownMenuItem(
                        value: s,
                        child: Text(s, overflow: TextOverflow.ellipsis),
                      ),
                    ),
                  ],
                  onChanged: (v) async {
                    final list = await _bank!.topics(v);
                    if (context.mounted) {
                      update(() {
                        subject = v;
                        topic = null;
                        topics = list;
                      });
                    }
                  },
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  key: ValueKey('topic:$subject:$topic'),
                  initialValue: topic,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Tópico'),
                  items: [
                    const DropdownMenuItem(
                      value: null,
                      child: Text('Todos os tópicos'),
                    ),
                    ...topics.map(
                      (s) => DropdownMenuItem(
                        value: s,
                        child: Text(s, overflow: TextOverflow.ellipsis),
                      ),
                    ),
                  ],
                  onChanged: (v) => update(() => topic = v),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  initialValue: board,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Banca'),
                  items: [
                    const DropdownMenuItem(
                      value: null,
                      child: Text('Todas as bancas'),
                    ),
                    ..._boards.map(
                      (s) => DropdownMenuItem(value: s, child: Text(s)),
                    ),
                  ],
                  onChanged: (v) => update(() => board = v),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  initialValue: mode,
                  decoration: const InputDecoration(
                    labelText: 'Quais questões?',
                  ),
                  items: const [
                    DropdownMenuItem(value: 'all', child: Text('Todas')),
                    DropdownMenuItem(
                      value: 'unanswered',
                      child: Text('Ainda não respondidas'),
                    ),
                    DropdownMenuItem(
                      value: 'errors',
                      child: Text('Errei na última tentativa'),
                    ),
                  ],
                  onChanged: (v) => update(() => mode = v!),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Evitar repetição no ciclo'),
                  subtitle: const Text(
                    'Desative para sorteios independentes, com possibilidade de repetir.',
                  ),
                  value: avoid,
                  onChanged: (v) => update(() => avoid = v),
                ),
                const SizedBox(height: 18),
                FilledButton(
                  onPressed: () => Navigator.pop(
                    context,
                    QuestionFilter(
                      subject: subject,
                      topic: topic,
                      board: board,
                      mode: mode,
                      avoidRepeats: avoid,
                    ),
                  ),
                  child: const Text('Aplicar filtros'),
                ),
                TextButton(
                  onPressed: () =>
                      Navigator.pop(context, const QuestionFilter()),
                  child: const Text('Limpar todos os filtros'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (result != null && mounted) {
      setState(() {
        _filter = result;
        _draw = null;
        _choice = null;
        _correct = null;
        _refreshReport();
      });
      await _next();
    }
  }

  void _source(BankQuestion q) {
    final original = widget.study.document(q.documentId);
    if (original != null) {
      Navigator.push(
        context,
        MaterialPageRoute<void>(
          builder: (_) => ReaderScreen(
            state: widget.study,
            item: original,
            initialPage: q.clips.isEmpty ? 1 : q.clips.first['page'] as int,
          ),
        ),
      );
    }
  }

  Future<void> _reclassify(BankQuestion q) async {
    final subject = TextEditingController(text: q.subject),
        topic = TextEditingController(text: q.topic);
    final result = await showDialog<List<String>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Ajustar classificação'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: subject,
              maxLength: 120,
              decoration: const InputDecoration(labelText: 'Assunto'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: topic,
              maxLength: 160,
              decoration: const InputDecoration(labelText: 'Tópico'),
            ),
            const SizedBox(height: 10),
            const Text(
              'Os indicadores anteriores desta questão também passam a usar a classificação corrigida.',
              style: TextStyle(fontSize: 12),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () {
              if (subject.text.trim().isNotEmpty &&
                  topic.text.trim().isNotEmpty) {
                Navigator.pop(context, [
                  subject.text.trim(),
                  topic.text.trim(),
                ]);
              }
            },
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
    await Future<void>.delayed(const Duration(milliseconds: 300));
    subject.dispose();
    topic.dispose();
    if (result == null || !mounted) return;
    setState(() => _busy = true);
    try {
      final updated = await _bank!.reclassify(q, result[0], result[1]);
      final subjects = await _bank!.subjects();
      if (!mounted) return;
      setState(() {
        _draw = QuestionDraw(updated, _draw!.eligible, false);
        _subjects = subjects;
        _filter = const QuestionFilter();
        _statSubject = null;
        _busy = false;
        _refreshReport();
      });
      _message('Classificação atualizada. Os filtros foram limpos.');
    } catch (_) {
      if (mounted) setState(() => _busy = false);
      _message('Não foi possível atualizar a classificação.');
    }
  }

  Widget _practice() {
    final q = _draw?.question;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                _filter.subject ?? 'Todos os assuntos',
                style: const TextStyle(
                  color: _green,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            TextButton.icon(
              onPressed: _busy ? null : _filters,
              icon: const Icon(Icons.tune, size: 18),
              label: const Text('Filtros'),
            ),
          ],
        ),
        if (_filter.topic != null)
          Text(
            _filter.topic!,
            style: const TextStyle(color: Color(0xff67796d)),
          ),
        if (_filter.mode != 'all')
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Text(
              _filter.mode == 'errors'
                  ? 'Revisão dos últimos erros'
                  : 'Só questões não respondidas',
            ),
          ),
        if (q == null) ...[
          const SizedBox(height: 24),
          const Text(
            'Uma questão.\nUm passo.',
            style: TextStyle(
              fontFamily: 'SourceSerif',
              fontSize: 38,
              height: 1.1,
              color: _green,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            _draw == null
                ? '$_bankSize questões no banco. Você pode misturar assuntos ou escolher um recorte.'
                : 'Nenhuma questão corresponde aos filtros atuais. Tente ampliar o recorte.',
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            key: const Key('draw-question'),
            onPressed: _busy ? null : _next,
            icon: const Icon(Icons.shuffle),
            label: const Text('Sortear questão'),
          ),
        ] else ...[
          const SizedBox(height: 12),
          Text(
            q.source,
            style: const TextStyle(fontSize: 12, color: Color(0xff67796d)),
          ),
          const SizedBox(height: 6),
          Text(
            '${q.subject} · ${q.topic}',
            style: const TextStyle(fontSize: 12, color: _ochre),
          ),
          if (q.classification == 'suggested')
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'Classificação inicial sugerida — confira o assunto na prova.',
                style: TextStyle(fontSize: 11, color: Color(0xff67796d)),
              ),
            ),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: _busy ? null : () => _reclassify(q),
              child: const Text('Ajustar assunto e tópico'),
            ),
          ),
          const SizedBox(height: 16),
          if (q.clips.isNotEmpty &&
              widget.study.document(q.documentId) != null) ...[
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => setState(() => _original = !_original),
                child: Text(_original ? 'Ler como texto' : 'Mostrar original'),
              ),
            ),
            if (_original)
              QuestionExcerpt(
                key: ValueKey(q.id),
                question: q,
                study: widget.study,
              ),
          ],
          if (!_original ||
              q.clips.isEmpty ||
              widget.study.document(q.documentId) == null)
            SelectableText(
              q.stem,
              key: const Key('question-stem'),
              style: const TextStyle(fontSize: 18, height: 1.55),
            ),
          const SizedBox(height: 18),
          for (var i = 0; i < q.options.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: OutlinedButton(
                key: Key('answer-$i'),
                style: OutlinedButton.styleFrom(
                  alignment: Alignment.centerLeft,
                  padding: const EdgeInsets.all(16),
                  foregroundColor: _correct != null && i == q.answer
                      ? _green
                      : _correct == false && i == _choice
                      ? _red
                      : _green,
                  backgroundColor: _correct != null && i == q.answer
                      ? _green.withValues(alpha: .1)
                      : _correct == false && i == _choice
                      ? _red.withValues(alpha: .1)
                      : _choice == i
                      ? _green.withValues(alpha: .08)
                      : Colors.white,
                  side: BorderSide(
                    color: _choice == i || _correct != null && i == q.answer
                        ? _green
                        : const Color(0xffd4dbd0),
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                onPressed: _busy || _correct != null
                    ? null
                    : () => setState(() => _choice = i),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      String.fromCharCode(65 + i),
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Text(
                        _original &&
                                q.clips.isNotEmpty &&
                                widget.study.document(q.documentId) != null
                            ? 'Marcar alternativa ${String.fromCharCode(65 + i)}'
                            : q.options[i],
                        style: const TextStyle(height: 1.45),
                      ),
                    ),
                    if (_correct != null && i == q.answer)
                      const Icon(Icons.check_circle, color: _green, size: 20),
                  ],
                ),
              ),
            ),
          if (_correct == null)
            FilledButton(
              onPressed: _busy || _choice == null ? null : _answer,
              child: const Text('Confirmar resposta'),
            ),
          if (_correct != null) ...[
            const SizedBox(height: 8),
            Semantics(
              liveRegion: true,
              child: Text(
                _correct! ? 'Você acertou.' : 'Vamos entender esse erro.',
                style: TextStyle(
                  fontFamily: 'SourceSerif',
                  fontSize: 27,
                  color: _correct! ? _green : _red,
                ),
              ),
            ),
            const SizedBox(height: 10),
            Text('Gabarito: ${String.fromCharCode(65 + q.answer)}'),
            const SizedBox(height: 10),
            SelectableText(
              q.explanation.isEmpty
                  ? 'Sem comentário revisado para esta questão.'
                  : q.explanation,
              style: const TextStyle(height: 1.5),
            ),
            if (!_correct!) ...[
              const SizedBox(height: 18),
              const Text('O que mais pesou neste erro?'),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: QuestionBank.errorReasons
                    .map(
                      (r) => ChoiceChip(
                        label: Text(r),
                        selected: _reason == r,
                        onSelected: (_) async {
                          try {
                            await _bank!.tagError(_event, r);
                            if (mounted) {
                              setState(() {
                                _reason = r;
                                _refreshReport();
                              });
                            }
                          } catch (_) {
                            _message('Não foi possível guardar o motivo.');
                          }
                        },
                      ),
                    )
                    .toList(),
              ),
            ],
            const SizedBox(height: 20),
            FilledButton.icon(
              key: const Key('next-question'),
              onPressed: _busy ? null : _next,
              icon: const Icon(Icons.shuffle),
              label: const Text('Próxima aleatória'),
            ),
          ],
          TextButton(
            onPressed: _busy ? null : _next,
            child: Text(
              _correct == null
                  ? 'Pular sem registrar resposta'
                  : 'Pular para outra',
            ),
          ),
          if (widget.study.document(q.documentId) != null)
            TextButton.icon(
              onPressed: () => _source(q),
              icon: const Icon(Icons.picture_as_pdf_outlined),
              label: const Text('Ver prova na página original'),
            ),
          ExpansionTile(
            key: PageStorageKey('question-source:${q.id}'),
            tilePadding: EdgeInsets.zero,
            title: const Text('Origem e gabarito'),
            children: [
              SelectableText(
                '${q.source}\n${q.sourceUrl}\nGabarito definitivo: ${q.answerSourceUrl}',
                style: const TextStyle(fontSize: 12, height: 1.5),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _bar(double fraction, Color color) => Semantics(
    label: '${(fraction * 100).round()} por cento',
    child: ClipRRect(
      borderRadius: BorderRadius.circular(3),
      child: LinearProgressIndicator(
        value: fraction,
        minHeight: 10,
        color: color,
        backgroundColor: color == _green
            ? _red.withValues(alpha: .22)
            : _green.withValues(alpha: .1),
      ),
    ),
  );

  Widget _performance() => FutureBuilder<PracticeReport>(
    future: _report,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return const Text('Não foi possível calcular os indicadores.');
      }
      if (!snapshot.hasData) {
        return const Center(child: CircularProgressIndicator());
      }
      final r = snapshot.data!;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Encontre o\npróximo avanço.',
            style: TextStyle(
              fontFamily: 'SourceSerif',
              fontSize: 34,
              height: 1.1,
              color: _green,
            ),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 8,
            children: [
              for (final d in [0, 7, 30])
                ChoiceChip(
                  label: Text(d == 0 ? 'Tudo' : '$d dias'),
                  selected: _days == d,
                  onSelected: (_) => setState(() {
                    _days = d;
                    _refreshReport();
                  }),
                ),
            ],
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            key: ValueKey('stats:$_statSubject'),
            initialValue: _statSubject,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Indicadores do assunto',
            ),
            items: [
              const DropdownMenuItem(
                value: null,
                child: Text('Todos os assuntos'),
              ),
              ..._subjects.map(
                (s) => DropdownMenuItem(
                  value: s,
                  child: Text(s, overflow: TextOverflow.ellipsis),
                ),
              ),
            ],
            onChanged: (v) => setState(() {
              _statSubject = v;
              _refreshReport();
            }),
          ),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              color: _green,
              borderRadius: BorderRadius.circular(22),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${r.attempts}',
                  style: const TextStyle(
                    fontFamily: 'SourceSerif',
                    fontSize: 52,
                    color: Colors.white,
                  ),
                ),
                const Text(
                  'tentativas registradas',
                  style: TextStyle(color: Colors.white),
                ),
                const SizedBox(height: 12),
                Text(
                  '${r.correct} acertos · ${r.attempts - r.correct} erros\n${r.unique} questões diferentes',
                  style: const TextStyle(color: Color(0xffd5e1d3), height: 1.5),
                ),
              ],
            ),
          ),
          if (r.attempts == 0)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Text(
                'Responda questões para começar a enxergar seus pontos fortes e prioridades. Assuntos sem respostas ainda não têm desempenho medido.',
              ),
            ),
          if (r.topics.isNotEmpty) ...[
            const SizedBox(height: 26),
            const Text(
              'Por assunto e tópico',
              style: TextStyle(fontFamily: 'SourceSerif', fontSize: 26),
            ),
            const SizedBox(height: 8),
            const Text(
              'A barra usa a primeira resposta de cada questão dentro do período. Verde = acertos; fundo vermelho = erros. Menos de 10 questões é amostra inicial.',
              style: TextStyle(
                fontSize: 12,
                height: 1.5,
                color: Color(0xff67796d),
              ),
            ),
            const SizedBox(height: 8),
            for (final t in r.topics)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      t.subject,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    Text(
                      t.topic,
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xff67796d),
                      ),
                    ),
                    const SizedBox(height: 10),
                    _bar(t.accuracy, _green),
                    const SizedBox(height: 8),
                    Text(
                      '${(100 * t.accuracy).round()}% · ${t.correct} acertos / ${t.errors} erros · ${t.answered} diferentes',
                      style: const TextStyle(fontSize: 12),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      t.assessment,
                      style: TextStyle(
                        color: t.answered < 10
                            ? _ochre
                            : t.accuracy < .6
                            ? _red
                            : _green,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      improvementAdvice(t, t.dominantReason),
                      style: const TextStyle(fontSize: 13, height: 1.45),
                    ),
                    TextButton(
                      onPressed: () {
                        setState(() {
                          _filter = QuestionFilter(
                            subject: t.subject,
                            topic: t.topic,
                          );
                          _analytics = false;
                          _draw = null;
                        });
                        _next();
                      },
                      child: const Text('Treinar este tópico'),
                    ),
                    const Divider(),
                  ],
                ),
              ),
            const SizedBox(height: 16),
            const Text(
              'Erros que você identificou',
              style: TextStyle(fontFamily: 'SourceSerif', fontSize: 25),
            ),
            const SizedBox(height: 8),
            const Text(
              'Motivos informados após errar, contando todas as tentativas.',
              style: TextStyle(fontSize: 12, color: Color(0xff67796d)),
            ),
            for (final reason in r.reasons)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 9),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${reason['reason']} · ${reason['n']}'),
                    const SizedBox(height: 6),
                    _bar(
                      (reason['n'] as int) / (r.attempts - r.correct),
                      _ochre,
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 24),
            const Text(
              'Evolução diária',
              style: TextStyle(fontFamily: 'SourceSerif', fontSize: 25),
            ),
            const Text(
              'Todas as tentativas por dia: compare volume e percentual juntos.',
              style: TextStyle(fontSize: 12, color: Color(0xff67796d)),
            ),
            for (final day in r.daily.skip(max(0, r.daily.length - 14)))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 7),
                child: Row(
                  children: [
                    SizedBox(
                      width: 83,
                      child: Text(
                        (day['day'] as String).substring(5),
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                    Expanded(
                      child: _bar(
                        (day['c'] as int) / (day['n'] as int),
                        _green,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      '${day['c']}/${day['n']}',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: () {
                setState(() {
                  _filter = QuestionFilter(
                    subject: _statSubject,
                    mode: 'errors',
                  );
                  _analytics = false;
                  _draw = null;
                });
                _next();
              },
              icon: const Icon(Icons.replay),
              label: const Text('Revisar últimos erros'),
            ),
            TextButton.icon(
              onPressed: _exportStats,
              icon: const Icon(Icons.file_download_outlined),
              label: const Text('Exportar indicadores em CSV'),
            ),
          ],
        ],
      );
    },
  );

  @override
  Widget build(BuildContext context) => ListView(
    controller: _scroll,
    key: const PageStorageKey('questions-scroll'),
    padding: const EdgeInsets.fromLTRB(24, 14, 24, 36),
    children: [
      Row(
        children: [
          const Expanded(
            child: Text(
              'QUESTÕES',
              style: TextStyle(
                letterSpacing: 2,
                color: _ochre,
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          IconButton(
            tooltip: 'Importar banco de questões',
            onPressed: _busy || _bank == null ? null : _import,
            icon: const Icon(Icons.add_to_photos_outlined),
          ),
        ],
      ),
      const SizedBox(height: 12),
      SegmentedButton<bool>(
        segments: const [
          ButtonSegment(
            value: false,
            label: Text('Praticar'),
            icon: Icon(Icons.shuffle),
          ),
          ButtonSegment(
            value: true,
            label: Text('Desempenho'),
            icon: Icon(Icons.bar_chart),
          ),
        ],
        selected: {_analytics},
        onSelectionChanged: (s) {
          setState(() {
            _analytics = s.first;
            _refreshReport();
          });
          if (_scroll.hasClients) _scroll.jumpTo(0);
        },
      ),
      const SizedBox(height: 22),
      if (_error != null)
        Text(_error!)
      else if (_bank == null)
        const Center(child: CircularProgressIndicator())
      else ...[
        if (_busy)
          const Padding(
            padding: EdgeInsets.only(bottom: 15),
            child: LinearProgressIndicator(),
          ),
        _analytics ? _performance() : _practice(),
        const SizedBox(height: 20),
        const Text(
          'Base inicial de provas públicas, com classificação sugerida e gabaritos definitivos, ainda sem comentários revisados. Questões importadas usam as informações do lote. Seus resultados ficam neste aparelho.',
          style: TextStyle(fontSize: 11, height: 1.5, color: Color(0xff67796d)),
        ),
      ],
    ],
  );
  @override
  void dispose() {
    if (widget.bank == null) unawaited(_bank?.close());
    _watch.stop();
    _scroll.dispose();
    super.dispose();
  }
}
