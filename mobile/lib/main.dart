import 'dart:async';
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:pdfrx/pdfrx.dart';
import 'package:flutter/foundation.dart';
import 'reader_screen.dart';
import 'study_state.dart';

const paper = Color(0xfff5f3eb),
    forest = Color(0xff244c3b),
    ink = Color(0xff253b30),
    ochre = Color(0xffb87d3e);
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await pdfrxFlutterInitialize();
    LicenseRegistry.addLicense(() async* {
      for (final font in ['DMSans', 'SourceSerif', 'JetBrainsMono']) {
        yield LicenseEntryWithLineBreaks([
          font,
        ], await rootBundle.loadString('assets/licenses/$font-OFL.txt'));
      }
    });
    final directory = await getApplicationDocumentsDirectory();
    final state = StudyState(
      await StudyCatalog.load(),
      FileStudyStorage(directory),
      directory,
    );
    await state.load();
    runApp(ConcursinhoApp(state: state));
  } catch (_) {
    runApp(
      const MaterialApp(
        home: Scaffold(
          body: Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Não foi possível carregar o Concursinho. Feche e abra o aplicativo novamente.',
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ConcursinhoApp extends StatelessWidget {
  final StudyState state;
  const ConcursinhoApp({super.key, required this.state});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Concursinho',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      fontFamily: 'DMSans',
      scaffoldBackgroundColor: paper,
      colorScheme: ColorScheme.fromSeed(
        seedColor: forest,
        primary: forest,
        surface: paper,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: paper,
        foregroundColor: ink,
        elevation: 0,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: paper,
        indicatorColor: forest.withValues(alpha: .12),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white.withValues(alpha: .65),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
      ),
      dividerColor: forest.withValues(alpha: .12),
    ),
    home: StudyHome(state: state),
  );
}

class StudyHome extends StatefulWidget {
  final StudyState state;
  const StudyHome({super.key, required this.state});
  @override
  State<StudyHome> createState() => _StudyHomeState();
}

class _StudyHomeState extends State<StudyHome> with WidgetsBindingObserver {
  int _tab = 0;
  String _topicQuery = '', _examQuery = '';
  StudyState get study => widget.state;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) study.tick();
  }

  void _message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  void _read(StudyDocument? doc) {
    if (doc != null) {
      Navigator.push(
        context,
        MaterialPageRoute<void>(
          builder: (_) => ReaderScreen(state: study, item: doc),
        ),
      );
    }
  }

  Future<void> _importPdf() async {
    try {
      final result = await FilePicker.pickFile(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
      );
      if (result == null) return;
      final chosen = result;
      final bytes = await chosen.readAsBytes();
      final doc = await study.importPdf(bytes, chosen.name);
      if (mounted) _read(doc);
    } catch (_) {
      if (mounted) {
        _message(
          'Não foi possível importar o PDF. Escolha um arquivo disponível no aparelho.',
        );
      }
    }
  }

  Future<void> _export() async {
    try {
      final result = await FilePicker.saveFile(
        dialogTitle: 'Guardar progresso',
        fileName: 'tjpb-progresso.json',
        bytes: Uint8List.fromList(
          utf8.encode(jsonEncode(study.completed.toList())),
        ),
      );
      if (result != null && mounted) {
        _message(
          'Progresso exportado. Esse JSON também pode ser usado no Concursinho do computador.',
        );
      }
    } catch (_) {
      if (mounted) _message('Não foi possível exportar o progresso.');
    }
  }

  Future<void> _importProgress() async {
    try {
      final result = await FilePicker.pickFile(type: FileType.any);
      if (result == null) return;
      final file = result;
      final content = utf8.decode(await file.readAsBytes());
      final count = await study.importProgress(content);
      if (mounted) {
        _message(
          '$count marcações reconhecidas. Seu progresso anterior foi preservado.',
        );
      }
    } catch (_) {
      if (mounted) {
        _message(
          'Arquivo de progresso inválido. Selecione o JSON exportado pelo Concursinho.',
        );
      }
    }
  }

  void _options() => showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (context) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const ListTile(
            title: Text(
              'Seu progresso, com você.',
              style: TextStyle(fontFamily: 'SourceSerif', fontSize: 25),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.file_upload_outlined),
            title: const Text('Exportar marcações'),
            subtitle: const Text(
              'Guardar uma cópia ou transferir para o computador',
            ),
            onTap: () {
              Navigator.pop(context);
              _export();
            },
          ),
          ListTile(
            leading: const Icon(Icons.file_download_outlined),
            title: const Text('Importar marcações'),
            subtitle: const Text('Adicionar progresso de outro Concursinho'),
            onTap: () {
              Navigator.pop(context);
              _importProgress();
            },
          ),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('Sobre este acervo'),
            subtitle: const Text(
              'TJPB · revisão de 26/10/2026 · fontes oficiais nos documentos',
            ),
            onTap: () {
              Navigator.pop(context);
              showLicensePage(
                context: context,
                applicationName: 'Concursinho',
                applicationVersion: '1.0.0',
              );
            },
          ),
          const Padding(
            padding: EdgeInsets.fromLTRB(24, 0, 24, 20),
            child: Text(
              'O estudo e as preferências ficam neste aparelho. A transferência com o computador é feita pelo arquivo de progresso.',
              style: TextStyle(fontSize: 12),
            ),
          ),
        ],
      ),
    ),
  );
  Widget _brand() => Padding(
    padding: const EdgeInsets.fromLTRB(24, 12, 12, 8),
    child: Row(
      children: [
        const Expanded(
          child: Text(
            'concursinho.',
            style: TextStyle(
              fontFamily: 'SourceSerif',
              fontSize: 27,
              color: forest,
            ),
          ),
        ),
        const Text(
          'TJPB 2026',
          style: TextStyle(
            fontSize: 11,
            letterSpacing: 1.5,
            fontWeight: FontWeight.w700,
            color: forest,
          ),
        ),
        IconButton(
          tooltip: 'Progresso e opções',
          onPressed: _options,
          icon: const Icon(Icons.more_horiz, color: forest),
        ),
      ],
    ),
  );
  Widget _eyebrow(String text) => Text(
    text,
    style: const TextStyle(
      fontSize: 11,
      letterSpacing: 2,
      color: ochre,
      fontWeight: FontWeight.w700,
    ),
  );
  Widget _headline(String text) => Text(
    text,
    style: const TextStyle(
      fontFamily: 'SourceSerif',
      fontSize: 35,
      height: 1.15,
      color: ink,
    ),
  );
  Widget _plan() {
    final done = study.topicCount, total = study.catalog.topics.length;
    final days = DateTime(
      2027,
      1,
      24,
    ).difference(DateUtils.dateOnly(DateTime.now())).inDays;
    final last = study.document(study.lastDocument);
    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 28),
      children: [
        _eyebrow('SEU PLANO DE ESTUDO'),
        const SizedBox(height: 10),
        _headline('Um pouco hoje.\nMais perto amanhã.'),
        const SizedBox(height: 12),
        Text(
          'Desenvolvimento de Sistemas · FGV\n${days >= 0 ? '$days dias até' : 'Data prevista:'} 24 de janeiro de 2027',
          style: const TextStyle(color: Color(0xff67796d), height: 1.6),
        ),
        const SizedBox(height: 24),
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: forest,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '$done',
                    style: const TextStyle(
                      fontFamily: 'SourceSerif',
                      fontSize: 48,
                      height: 1,
                      color: Colors.white,
                    ),
                  ),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(left: 8, bottom: 5),
                      child: Text(
                        '/ $total tópicos',
                        style: const TextStyle(color: Color(0xffc7d7cb)),
                      ),
                    ),
                  ),
                  const Icon(
                    Icons.spa_outlined,
                    color: Color(0xffd6bd83),
                    size: 34,
                  ),
                ],
              ),
              const SizedBox(height: 18),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: total == 0 ? 0 : done / total,
                  minHeight: 5,
                  color: const Color(0xffd6bd83),
                  backgroundColor: Colors.white24,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Uma marcação quando você conseguir explicar e resolver.',
                style: TextStyle(color: Color(0xffdce5dc), fontSize: 12),
              ),
            ],
          ),
        ),
        if (study.saveError != null)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(
              study.saveError!,
              style: const TextStyle(color: Colors.red),
            ),
          ),
        if (last != null) ...[
          const SizedBox(height: 18),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.auto_stories_outlined, color: forest),
            title: const Text('Continuar de onde parou'),
            subtitle: Text(
              last.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: const Icon(Icons.arrow_forward),
            onTap: () => _read(last),
          ),
        ],
        const SizedBox(height: 20),
        TextField(
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search),
            hintText: 'Buscar um assunto',
          ),
          onChanged: (value) =>
              setState(() => _topicQuery = value.toLowerCase()),
        ),
        const SizedBox(height: 16),
        for (final group in study.catalog.groups)
          if (study.catalog.topics.any(
            (t) =>
                t.group == group &&
                '$group ${t.text}'.toLowerCase().contains(_topicQuery),
          ))
            _group(group),
        const SizedBox(height: 24),
        OutlinedButton.icon(
          onPressed: () => _read(
            study.catalog.documents.firstWhere((d) => d.kind == 'edital'),
          ),
          icon: const Icon(Icons.description_outlined),
          label: const Text('Ler o edital atualizado'),
        ),
        const SizedBox(height: 8),
        const Text(
          '146 tópicos em 14 blocos. O acervo foi revisado em 26/10/2026; futuras retificações precisam ser conferidas na FGV.',
          style: TextStyle(fontSize: 11, height: 1.6, color: Color(0xff67796d)),
        ),
      ],
    );
  }

  Widget _group(String group) {
    final all = study.catalog.topics.where((e) => e.group == group).toList();
    final filtered = all
        .where((e) => '$group ${e.text}'.toLowerCase().contains(_topicQuery))
        .toList();
    final count = all.where((e) => study.completed.contains(e.id)).length;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: .6),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: forest.withValues(alpha: .1)),
      ),
      child: ExpansionTile(
        key: PageStorageKey(group),
        initiallyExpanded: _topicQuery.isNotEmpty,
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
        shape: const Border(),
        collapsedShape: const Border(),
        title: Text(
          group,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
        subtitle: Text(
          '$count de ${all.length} estudados',
          style: const TextStyle(fontSize: 12),
        ),
        children: [
          for (final topic in filtered)
            CheckboxListTile(
              value: study.completed.contains(topic.id),
              onChanged: (_) => study.toggle(topic.id),
              controlAffinity: ListTileControlAffinity.leading,
              title: Text(
                topic.text,
                style: const TextStyle(fontSize: 14, height: 1.5),
              ),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 3,
              ),
            ),
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: TextButton.icon(
              onPressed: () {
                study.focusSubject = group;
                setState(() => _tab = 2);
              },
              icon: const Icon(Icons.timer_outlined, size: 18),
              label: const Text('Focar neste bloco'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _exams() => ListView(
    padding: const EdgeInsets.fromLTRB(24, 16, 24, 28),
    children: [
      _eyebrow('PRATICAR É PARTE DO CAMINHO'),
      const SizedBox(height: 10),
      _headline('Provas na mão.'),
      const SizedBox(height: 12),
      Text(
        '${study.examCount} de 9 provas resolvidas · disponíveis offline',
        style: const TextStyle(color: Color(0xff67796d)),
      ),
      const SizedBox(height: 18),
      TextField(
        decoration: const InputDecoration(
          prefixIcon: Icon(Icons.search),
          hintText: 'Buscar tribunal ou ano',
        ),
        onChanged: (value) => setState(() => _examQuery = value.toLowerCase()),
      ),
      const SizedBox(height: 18),
      for (final exam in study.catalog.exams.where(
        (e) => e.title.toLowerCase().contains(_examQuery),
      ))
        _exam(exam),
      const SizedBox(height: 20),
      _eyebrow('SUA ESTANTE'),
      const SizedBox(height: 12),
      for (final doc in study.imported)
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.picture_as_pdf_outlined),
          title: Text(doc.title),
          trailing: const Icon(Icons.arrow_forward),
          onTap: () => _read(doc),
        ),
      OutlinedButton.icon(
        onPressed: _importPdf,
        icon: const Icon(Icons.add),
        label: const Text('Adicionar um PDF do aparelho'),
      ),
      const SizedBox(height: 24),
      _eyebrow('DISCURSIVA'),
      const SizedBox(height: 10),
      const Text(
        'Escreva antes de conferir.',
        style: TextStyle(fontFamily: 'SourceSerif', fontSize: 26, color: ink),
      ),
      const SizedBox(height: 10),
      const Text(
        'No TJPB: uma questão, 30 linhas e 40 pontos. Treine a resposta com tempo controlado. Os espelhos do TJRN e TJDFT ajudam a revisar o que você escreveu; seus critérios pertencem àqueles concursos.',
        style: TextStyle(height: 1.7),
      ),
      const SizedBox(height: 14),
      const Text(
        'A prova de 2012 é da FAPERP; as demais são da FGV. Confira a atualização das normas e tecnologias ao usar questões antigas.',
        style: TextStyle(fontSize: 12, height: 1.6, color: Color(0xff67796d)),
      ),
    ],
  );
  Widget _exam(StudyExam exam) => Container(
    margin: const EdgeInsets.only(bottom: 14),
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: .7),
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: forest.withValues(alpha: .12)),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          exam.description.toUpperCase(),
          style: const TextStyle(
            fontSize: 10,
            letterSpacing: 1.6,
            color: ochre,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          exam.title,
          style: const TextStyle(
            fontFamily: 'SourceSerif',
            fontSize: 23,
            height: 1.2,
            color: ink,
          ),
        ),
        const SizedBox(height: 14),
        FilledButton.icon(
          onPressed: () => _read(study.document(exam.documents['prova'])),
          icon: const Icon(Icons.menu_book_outlined, size: 18),
          label: const Text('Abrir prova'),
        ),
        Wrap(
          spacing: 8,
          children: [
            TextButton(
              onPressed: () =>
                  _read(study.document(exam.documents['gabarito_definitivo'])),
              child: const Text('Gabarito definitivo'),
            ),
            if (exam.documents.containsKey('espelho_discursiva'))
              TextButton(
                onPressed: () =>
                    _read(study.document(exam.documents['espelho_discursiva'])),
                child: const Text('Espelho'),
              ),
          ],
        ),
        const Divider(height: 16),
        Row(
          children: [
            Checkbox(
              value: study.completed.contains(exam.id),
              onChanged: (_) => study.toggle(exam.id),
            ),
            const Text('Prova resolvida'),
          ],
        ),
      ],
    ),
  );
  Widget _focus() {
    final minutes = (study.remaining ~/ 60).toString().padLeft(2, '0'),
        seconds = (study.remaining % 60).toString().padLeft(2, '0');
    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 28),
      children: [
        _eyebrow('UMA COISA DE CADA VEZ'),
        const SizedBox(height: 10),
        _headline('Agora, presença.'),
        const SizedBox(height: 24),
        DropdownButtonFormField<String>(
          key: ValueKey(study.focusSubject),
          initialValue: study.focusSubject,
          decoration: const InputDecoration(
            labelText: 'Qual é o foco de hoje?',
          ),
          isExpanded: true,
          items: ['Revisão geral', 'Provas anteriores', ...study.catalog.groups]
              .map(
                (s) => DropdownMenuItem(
                  value: s,
                  child: Text(s, overflow: TextOverflow.ellipsis),
                ),
              )
              .toList(),
          onChanged: study.focusEnd != null
              ? null
              : (value) {
                  if (value != null) {
                    study.focusSubject = value;
                    unawaited(study.persist());
                  }
                },
        ),
        const SizedBox(height: 34),
        Center(
          child: SizedBox(
            width: 264,
            height: 264,
            child: Stack(
              alignment: Alignment.center,
              children: [
                SizedBox.expand(
                  child: CircularProgressIndicator(
                    value: study.remaining / study.focusDuration,
                    strokeWidth: 3,
                    color: forest,
                    backgroundColor: forest.withValues(alpha: .12),
                  ),
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '$minutes:$seconds',
                      key: const Key('focus-clock'),
                      style: const TextStyle(
                        fontFamily: 'SourceSerif',
                        fontSize: 60,
                        color: ink,
                      ),
                    ),
                    Text(
                      study.focusEnd != null
                          ? 'EM FOCO'
                          : study.remaining == 0
                          ? 'SESSÃO CONCLUÍDA'
                          : 'NO SEU RITMO',
                      style: const TextStyle(
                        fontSize: 10,
                        letterSpacing: 2,
                        color: ochre,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 26),
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 8,
          children: [
            for (final duration in [15, 25, 40, 50])
              ChoiceChip(
                label: Text('${duration}min'),
                selected: study.focusDuration == duration * 60,
                onSelected: study.focusEnd != null
                    ? null
                    : (_) => study.setDuration(duration),
              ),
          ],
        ),
        const SizedBox(height: 24),
        FilledButton.icon(
          onPressed: study.focusEnd == null
              ? study.startFocus
              : study.pauseFocus,
          icon: Icon(study.focusEnd == null ? Icons.play_arrow : Icons.pause),
          label: Text(study.focusEnd == null ? 'Começar foco' : 'Pausar'),
        ),
        TextButton(
          onPressed: study.resetFocus,
          child: const Text('Reiniciar sessão'),
        ),
        const SizedBox(height: 18),
        Center(
          child: Text(
            '${study.focusMinutes} minutos em sessões concluídas',
            style: const TextStyle(color: Color(0xff67796d)),
          ),
        ),
        const SizedBox(height: 14),
        const Text(
          'O relógio retoma pelo horário ao voltar ao app. Esta versão não toca um alarme quando o Android suspende ou fecha o aplicativo.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12, height: 1.5, color: Color(0xff67796d)),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: study,
    builder: (context, _) => Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _brand(),
            Expanded(
              child: IndexedStack(
                index: _tab,
                children: [_plan(), _exams(), _focus()],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (index) => setState(() => _tab = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.route_outlined),
            selectedIcon: Icon(Icons.route),
            label: 'Plano',
          ),
          NavigationDestination(
            icon: Icon(Icons.library_books_outlined),
            selectedIcon: Icon(Icons.library_books),
            label: 'Provas',
          ),
          NavigationDestination(
            icon: Icon(Icons.timer_outlined),
            selectedIcon: Icon(Icons.timer),
            label: 'Foco',
          ),
        ],
      ),
    ),
  );
  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}
