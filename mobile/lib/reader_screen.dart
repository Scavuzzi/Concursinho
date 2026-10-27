import 'dart:async';
import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';
import 'study_state.dart';

class ReadingPalette {
  final Color background, ink, muted, accent;
  const ReadingPalette(this.background, this.ink, this.muted, this.accent);
  static ReadingPalette forTheme(String theme) => switch (theme) {
    'night' => const ReadingPalette(
      Color(0xff191e23),
      Color(0xffe1e2dd),
      Color(0xffa4ada9),
      Color(0xffb2d3b8),
    ),
    'sepia' => const ReadingPalette(
      Color(0xffeee0c3),
      Color(0xff42362b),
      Color(0xff74634e),
      Color(0xff665d34),
    ),
    _ => const ReadingPalette(
      Color(0xfff9f7f1),
      Color(0xff25362e),
      Color(0xff71796c),
      Color(0xff285242),
    ),
  };
}

class ReaderScreen extends StatefulWidget {
  final StudyState state;
  final StudyDocument item;
  const ReaderScreen({super.key, required this.state, required this.item});
  @override
  State<ReaderScreen> createState() => _ReaderScreenState();
}

class _ReaderScreenState extends State<ReaderScreen> {
  final _controller = PdfViewerController();
  final _textScroll = ScrollController();
  final Map<int, Future<String>> _texts = {};
  PdfDocument? _document;
  PdfDocumentRef? _reference;
  String? _error;
  bool _reading = false;
  late int _page;
  @override
  void initState() {
    super.initState();
    _page = widget.state.positions[widget.item.id] ?? widget.item.initialPage;
    unawaited(_load());
  }

  Future<void> _load() async {
    try {
      final path = await widget.state.localPath(widget.item);
      final document = await PdfDocument.openFile(path);
      if (!mounted) {
        document.dispose();
        return;
      }
      if (document.pages.isEmpty) {
        document.dispose();
        throw StateError('PDF sem páginas.');
      }
      setState(() {
        _document = document;
        _reference = PdfDocumentRefDirect(document);
        _page = _page.clamp(1, document.pages.length);
      });
      widget.state.setPosition(widget.item.id, _page);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Não foi possível abrir este PDF. Ele pode estar protegido por senha ou danificado.',
        );
      }
    }
  }

  Future<String> _text(int page) => _texts.putIfAbsent(page, () async {
    final raw = await _document!.pages[page - 1].loadText();
    return readablePdfText(raw?.fullText ?? '');
  });
  void _go(int page) {
    if (_document == null) return;
    final target = page.clamp(1, _document!.pages.length);
    setState(() => _page = target);
    if (_controller.isReady) {
      unawaited(_controller.goToPage(pageNumber: target));
    }
    if (_textScroll.hasClients) _textScroll.jumpTo(0);
    widget.state.setPosition(widget.item.id, target);
  }

  Future<void> _jump() async {
    final field = TextEditingController(text: '$_page');
    final number = await showDialog<int>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Ir para a página'),
        content: TextField(
          controller: field,
          keyboardType: TextInputType.number,
          autofocus: true,
          decoration: InputDecoration(
            labelText: 'De 1 a ${_document!.pages.length}',
          ),
          onSubmitted: (value) => Navigator.pop(context, int.tryParse(value)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, int.tryParse(field.text)),
            child: const Text('Ir'),
          ),
        ],
      ),
    );
    // Dialog routes retain their text fields during their closing animation.
    if (number != null && mounted) _go(number);
    await Future<void>.delayed(const Duration(milliseconds: 300));
    field.dispose();
  }

  void _marks() {
    final marks = widget.state.bookmarks[widget.item.id] ?? [];
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(
              title: Text(
                'Páginas marcadas',
                style: TextStyle(fontSize: 22, fontFamily: 'SourceSerif'),
              ),
            ),
            if (marks.isEmpty)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Toque no marcador no topo para guardar uma página.',
                ),
              ),
            for (final page in marks)
              ListTile(
                leading: const Icon(Icons.bookmark_outline),
                title: Text('Página $page'),
                onTap: () {
                  Navigator.pop(context);
                  _go(page);
                },
              ),
          ],
        ),
      ),
    );
  }

  void _settings() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => AnimatedBuilder(
        animation: widget.state,
        builder: (context, _) {
          final settings = widget.state.reader;
          void change(VoidCallback action) {
            action();
            widget.state.updateReader();
          }

          Widget slider(
            String label,
            double value,
            double min,
            double max,
            ValueChanged<double> onChanged,
          ) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label),
              Slider(value: value, min: min, max: max, onChanged: onChanged),
            ],
          );
          return SafeArea(
            child: SingleChildScrollView(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Do seu jeito.',
                      style: TextStyle(fontFamily: 'SourceSerif', fontSize: 30),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Fonte e espaçamento se aplicam ao modo Leitura. A página original mantém sua diagramação.',
                    ),
                    const SizedBox(height: 18),
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(value: 'paper', label: Text('Claro')),
                        ButtonSegment(value: 'sepia', label: Text('Sépia')),
                        ButtonSegment(value: 'night', label: Text('Noite')),
                      ],
                      selected: {settings.theme},
                      onSelectionChanged: (value) =>
                          change(() => settings.theme = value.first),
                    ),
                    const SizedBox(height: 18),
                    DropdownButtonFormField<String>(
                      initialValue: settings.font,
                      decoration: const InputDecoration(
                        labelText: 'Fonte de leitura',
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'SourceSerif',
                          child: Text(
                            'Serifada · Source Serif',
                            style: TextStyle(fontFamily: 'SourceSerif'),
                          ),
                        ),
                        DropdownMenuItem(
                          value: 'DMSans',
                          child: Text('Sem serifa · DM Sans'),
                        ),
                        DropdownMenuItem(
                          value: 'JetBrainsMono',
                          child: Text(
                            'Monoespaçada',
                            style: TextStyle(fontFamily: 'JetBrainsMono'),
                          ),
                        ),
                      ],
                      onChanged: (value) {
                        if (value != null) change(() => settings.font = value);
                      },
                    ),
                    const SizedBox(height: 18),
                    slider(
                      'Tamanho · ${settings.size.round()}',
                      settings.size,
                      14,
                      34,
                      (value) => change(() => settings.size = value),
                    ),
                    slider(
                      'Entrelinhas · ${settings.lineHeight.toStringAsFixed(1)}',
                      settings.lineHeight,
                      1.2,
                      2.2,
                      (value) => change(() => settings.lineHeight = value),
                    ),
                    slider(
                      'Margens · ${settings.margin.round()}',
                      settings.margin,
                      12,
                      48,
                      (value) => change(() => settings.margin = value),
                    ),
                    slider(
                      'Suavizar a luz da página',
                      settings.dim,
                      0,
                      .5,
                      (value) => change(() => settings.dim = value),
                    ),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Justificar o texto'),
                      value: settings.justify,
                      onChanged: (value) =>
                          change(() => settings.justify = value),
                    ),
                    const SizedBox(height: 8),
                    FilledButton.icon(
                      onPressed: () {
                        Navigator.pop(context);
                        setState(() => _reading = true);
                      },
                      icon: const Icon(Icons.auto_stories_outlined),
                      label: const Text('Usar o modo Leitura'),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.state,
    builder: (context, _) {
      final settings = widget.state.reader,
          palette = ReadingPalette.forTheme(settings.theme);
      final marked = (widget.state.bookmarks[widget.item.id] ?? []).contains(
        _page,
      );
      return Theme(
        data: Theme.of(context).copyWith(
          scaffoldBackgroundColor: palette.background,
          colorScheme: ColorScheme.fromSeed(
            seedColor: palette.accent,
            brightness: settings.theme == 'night'
                ? Brightness.dark
                : Brightness.light,
            surface: palette.background,
          ),
        ),
        child: Scaffold(
          appBar: AppBar(
            backgroundColor: palette.background,
            foregroundColor: palette.ink,
            title: Text(
              widget.item.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 14),
            ),
            actions: [
              IconButton(
                tooltip: 'Marcar página',
                onPressed: _document == null
                    ? null
                    : () => widget.state.toggleBookmark(widget.item.id, _page),
                icon: Icon(marked ? Icons.bookmark : Icons.bookmark_outline),
              ),
              IconButton(
                tooltip: 'Preferências de leitura',
                onPressed: _settings,
                icon: const Icon(Icons.text_fields),
              ),
              PopupMenuButton<String>(
                tooltip: 'Mais opções',
                onSelected: (_) => _marks(),
                itemBuilder: (_) => [
                  const PopupMenuItem(
                    value: 'marks',
                    child: Text('Páginas marcadas'),
                  ),
                ],
              ),
            ],
          ),
          body: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                child: Row(
                  children: [
                    Expanded(
                      child: SegmentedButton<bool>(
                        segments: const [
                          ButtonSegment(
                            value: false,
                            label: Text('Original'),
                            icon: Icon(Icons.picture_as_pdf_outlined),
                          ),
                          ButtonSegment(
                            value: true,
                            label: Text('Leitura'),
                            icon: Icon(Icons.auto_stories_outlined),
                          ),
                        ],
                        selected: {_reading},
                        onSelectionChanged: (values) =>
                            setState(() => _reading = values.first),
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: _error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(28),
                          child: Text(_error!),
                        ),
                      )
                    : _document == null
                    ? const Center(child: CircularProgressIndicator())
                    : Stack(
                        children: [
                          Positioned.fill(
                            child: IndexedStack(
                              index: _reading ? 1 : 0,
                              children: [
                                ColorFiltered(
                                  colorFilter: settings.theme == 'night'
                                      ? const ColorFilter.matrix([
                                          -1,
                                          0,
                                          0,
                                          0,
                                          255,
                                          0,
                                          -1,
                                          0,
                                          0,
                                          255,
                                          0,
                                          0,
                                          -1,
                                          0,
                                          255,
                                          0,
                                          0,
                                          0,
                                          1,
                                          0,
                                        ])
                                      : ColorFilter.mode(
                                          settings.theme == 'sepia'
                                              ? const Color(0xffeee0c3)
                                              : Colors.white,
                                          BlendMode.modulate,
                                        ),
                                  child: PdfViewer(
                                    _reference!,
                                    controller: _controller,
                                    initialPageNumber: _page,
                                    params: PdfViewerParams(
                                      backgroundColor: settings.theme == 'paper'
                                          ? palette.background
                                          : Colors.white,
                                      pageDropShadow: null,
                                      onPageChanged: (page) {
                                        if (page != null &&
                                            mounted &&
                                            !_reading &&
                                            page != _page) {
                                          setState(() => _page = page);
                                          widget.state.setPosition(
                                            widget.item.id,
                                            page,
                                          );
                                        }
                                      },
                                    ),
                                  ),
                                ),
                                FutureBuilder<String>(
                                  future: _text(_page),
                                  builder: (context, snapshot) {
                                    if (snapshot.hasError) {
                                      return const Center(
                                        child: Padding(
                                          padding: EdgeInsets.all(24),
                                          child: Text(
                                            'Não foi possível extrair o texto. Use a visualização Original.',
                                          ),
                                        ),
                                      );
                                    }
                                    if (!snapshot.hasData) {
                                      return const Center(
                                        child: CircularProgressIndicator(),
                                      );
                                    }
                                    if (snapshot.data!.isEmpty) {
                                      return Center(
                                        child: Padding(
                                          padding: const EdgeInsets.all(28),
                                          child: Text(
                                            'Esta página não tem texto selecionável. Use Original para ler a imagem.',
                                            style: TextStyle(
                                              color: palette.ink,
                                            ),
                                          ),
                                        ),
                                      );
                                    }
                                    return SingleChildScrollView(
                                      controller: _textScroll,
                                      key: ValueKey('text-page-$_page'),
                                      padding: EdgeInsets.fromLTRB(
                                        settings.margin,
                                        16,
                                        settings.margin,
                                        40,
                                      ),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            'PÁGINA $_page',
                                            style: TextStyle(
                                              fontFamily: 'DMSans',
                                              fontSize: 11,
                                              letterSpacing: 2,
                                              color: palette.muted,
                                            ),
                                          ),
                                          const SizedBox(height: 18),
                                          SelectableText(
                                            snapshot.data!,
                                            key: const Key('reflow-text'),
                                            textAlign: settings.justify
                                                ? TextAlign.justify
                                                : TextAlign.start,
                                            style: TextStyle(
                                              fontFamily: settings.font,
                                              fontSize: settings.size,
                                              height: settings.lineHeight,
                                              color: palette.ink,
                                            ),
                                          ),
                                          const SizedBox(height: 28),
                                          Text(
                                            'Texto extraído do PDF. Confira tabelas, figuras e a ordem das colunas em Original.',
                                            style: TextStyle(
                                              fontSize: 12,
                                              color: palette.muted,
                                            ),
                                          ),
                                        ],
                                      ),
                                    );
                                  },
                                ),
                              ],
                            ),
                          ),
                          if (settings.dim > 0)
                            Positioned.fill(
                              child: IgnorePointer(
                                child: ColoredBox(
                                  color: Colors.black.withValues(
                                    alpha: settings.dim,
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
              ),
            ],
          ),
          bottomNavigationBar: SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  IconButton(
                    tooltip: 'Página anterior',
                    onPressed: _document != null && _page > 1
                        ? () => _go(_page - 1)
                        : null,
                    icon: const Icon(Icons.arrow_back),
                  ),
                  TextButton(
                    onPressed: _document != null ? _jump : null,
                    child: Text(
                      _document == null
                          ? 'Abrindo…'
                          : '$_page / ${_document!.pages.length}',
                    ),
                  ),
                  IconButton(
                    tooltip: 'Próxima página',
                    onPressed:
                        _document != null && _page < _document!.pages.length
                        ? () => _go(_page + 1)
                        : null,
                    icon: const Icon(Icons.arrow_forward),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    },
  );
  @override
  void dispose() {
    _textScroll.dispose();
    super.dispose();
  }
}
