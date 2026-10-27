import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';
import 'question_bank.dart';
import 'study_state.dart';

/// Rasterize only the source rectangles, retaining diagrams, mathematical
/// notation and underlining without shipping another image copy of each PDF.
class QuestionExcerpt extends StatefulWidget {
  final BankQuestion question;
  final StudyState study;
  const QuestionExcerpt({
    super.key,
    required this.question,
    required this.study,
  });
  @override
  State<QuestionExcerpt> createState() => _QuestionExcerptState();
}

class _QuestionExcerptState extends State<QuestionExcerpt> {
  List<ui.Image>? _images;
  String? _error;
  @override
  void initState() {
    super.initState();
    _render();
  }

  Future<void> _render() async {
    PdfDocument? document;
    final images = <ui.Image>[];
    try {
      final source = widget.study.document(widget.question.documentId);
      if (source == null) throw StateError('Fonte ausente.');
      document = await PdfDocument.openFile(
        await widget.study.localPath(source),
      );
      for (final clip in widget.question.clips) {
        final page = document.pages[(clip['page'] as int) - 1];
        final rect = (clip['rect'] as List).cast<num>();
        final scale = 1000 / (rect[2] - rect[0]);
        final bitmap = await page.render(
          x: (rect[0] * scale).round(),
          y: (rect[1] * scale).round(),
          width: 1000,
          height: ((rect[3] - rect[1]) * scale).ceil(),
          fullWidth: page.width * scale,
          fullHeight: page.height * scale,
        );
        if (bitmap == null) throw StateError('Recorte vazio.');
        try {
          images.add(await bitmap.createImage());
        } finally {
          bitmap.dispose();
        }
      }
      if (!mounted) {
        for (final image in images) {
          image.dispose();
        }
        return;
      }
      setState(() => _images = images);
    } catch (_) {
      for (final image in images) {
        image.dispose();
      }
      if (mounted) {
        setState(
          () => _error =
              'Não foi possível desenhar o recorte. Use Texto ou abra a prova completa.',
        );
      }
    } finally {
      await document?.dispose();
    }
  }

  Widget _pages() => Column(
    children: [
      for (final image in _images!)
        AspectRatio(
          aspectRatio: image.width / image.height,
          child: RawImage(image: image, fit: BoxFit.contain),
        ),
    ],
  );
  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Padding(padding: const EdgeInsets.all(20), child: Text(_error!));
    }
    if (_images == null) {
      return const Padding(
        padding: EdgeInsets.all(28),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    return Semantics(
      label:
          'Questão original. Toque para ampliar. O modo Texto oferece conteúdo selecionável.',
      child: InkWell(
        onTap: () => showDialog<void>(
          context: context,
          builder: (context) => Dialog.fullscreen(
            child: Scaffold(
              appBar: AppBar(title: const Text('Questão original')),
              body: InteractiveViewer(
                minScale: 1,
                maxScale: 4,
                child: SingleChildScrollView(child: _pages()),
              ),
            ),
          ),
        ),
        child: ColoredBox(color: Colors.white, child: _pages()),
      ),
    );
  }

  @override
  void dispose() {
    for (final image in _images ?? <ui.Image>[]) {
      image.dispose();
    }
    super.dispose();
  }
}
