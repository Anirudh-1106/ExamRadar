import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image/image.dart' as img;

import '../api/models.g.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Exact age in years, months and days on a cut-off date.
(int, int, int) ageParts(DateTime dob, DateTime on) {
  var y = on.year - dob.year, m = on.month - dob.month, d = on.day - dob.day;
  if (d < 0) {
    m -= 1;
    d += DateTime(on.year, on.month, 0).day;
  }
  if (m < 0) {
    y -= 1;
    m += 12;
  }
  return (y, m, d);
}

class AgeCalcScreen extends ConsumerStatefulWidget {
  const AgeCalcScreen({super.key});
  @override
  ConsumerState<AgeCalcScreen> createState() => _AgeCalcState();
}

class _AgeCalcState extends ConsumerState<AgeCalcScreen> {
  DateTime? _dob;
  DateTime _on = DateTime(DateTime.now().year, 1, 1);

  @override
  void initState() {
    super.initState();
    ref.read(profileProvider.future).then((p) => mounted && p?.dateOfBirth != null ? setState(() => _dob = p!.dateOfBirth) : null);
  }

  Future<DateTime?> _pick(DateTime init) =>
      showDatePicker(context: context, initialDate: init, firstDate: DateTime(1950), lastDate: DateTime(2040));

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final parts = _dob == null ? null : ageParts(_dob!, _on);
    return Scaffold(
      appBar: AppBar(title: Text(context.t('ageCalc'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(context.t('dob')),
            subtitle: Text(_dob == null ? context.t('chooseDate') : fmtDate(context, _dob)),
            trailing: const Icon(Icons.edit_calendar_outlined),
            onTap: () async => (await _pick(_dob ?? DateTime(2000))).let((d) => setState(() => _dob = d)),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(context.t('cutoff')),
            subtitle: Text(fmtDate(context, _on)),
            trailing: const Icon(Icons.edit_calendar_outlined),
            onTap: () async => (await _pick(_on)).let((d) => setState(() => _on = d)),
          ),
          const SizedBox(height: 16),
          if (parts != null)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: p.greenSoft, borderRadius: BorderRadius.circular(10)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(context.t('ageOn', {'date': fmtDate(context, _on)}), style: TextStyle(color: p.green)),
                  const SizedBox(height: 4),
                  Text(
                    context.t('ymd', {'y': parts.$1, 'm': parts.$2, 'd': parts.$3}),
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: p.ink, fontFeatures: tabular),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 16),
          Text(context.t('eligibilityBasis'), style: TextStyle(color: p.muted, fontSize: 12.5)),
        ],
      ),
    );
  }
}

extension _Let<T> on T? {
  void let(void Function(T) f) {
    final v = this;
    if (v != null) f(v);
  }
}

/// Normalised comparison of names as printed on different documents.
String normName(String s) => s.toUpperCase().replaceAll(RegExp(r'[^A-Z ]'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();

List<String> nameDifferences(String a, String b) {
  final na = normName(a), nb = normName(b);
  if (na == nb) return [];
  final out = <String>[];
  final ta = na.split(' '), tb = nb.split(' ');
  if ((ta.toSet()..removeAll(tb)).isEmpty && (tb.toSet()..removeAll(ta)).isEmpty) {
    out.add('word order');
  } else {
    final ia = ta.where((w) => w.length == 1).toSet(), ib = tb.where((w) => w.length == 1).toSet();
    if (ia.isNotEmpty || ib.isNotEmpty) out.add('initials');
    if (na.replaceAll(' ', '') == nb.replaceAll(' ', '')) {
      out.add('spacing');
    } else {
      out.add('spelling');
    }
  }
  return out;
}

class NameCheckScreen extends StatefulWidget {
  const NameCheckScreen({super.key});
  @override
  State<NameCheckScreen> createState() => _NameCheckState();
}

class _Doc {
  _Doc(String label) : label = TextEditingController(text: label);
  final TextEditingController label;
  final name = TextEditingController();
  DateTime? dob;
}

class _NameCheckState extends State<NameCheckScreen> {
  final _docs = [_Doc('SSLC'), _Doc('Plus Two'), _Doc('Degree')];

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final filled = _docs.where((d) => d.name.text.trim().isNotEmpty).toList();
    final issues = <String>[];
    for (var i = 0; i < filled.length; i++) {
      for (var j = i + 1; j < filled.length; j++) {
        final a = filled[i], b = filled[j];
        final diff = nameDifferences(a.name.text, b.name.text);
        if (a.dob != null && b.dob != null && a.dob != b.dob) diff.add(context.t('dob'));
        if (diff.isNotEmpty) issues.add(context.t('mismatch', {'a': a.label.text, 'b': b.label.text, 'what': diff.join(', ')}));
      }
    }
    return Scaffold(
      appBar: AppBar(title: Text(context.t('nameCheck'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(context.t('nameCheckIntro')),
          const SizedBox(height: 12),
          for (final d in _docs)
            Card(
              margin: const EdgeInsets.only(bottom: 10),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    TextField(
                      controller: d.label,
                      decoration: InputDecoration(labelText: context.t('docName')),
                      onChanged: (_) => setState(() {}),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: d.name,
                      textCapitalization: TextCapitalization.characters,
                      decoration: InputDecoration(labelText: context.t('nameAsPrinted')),
                      onChanged: (_) => setState(() {}),
                    ),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(context.t('dob')),
                      subtitle: Text(d.dob == null ? context.t('notSet') : fmtDate(context, d.dob)),
                      onTap: () async {
                        final v = await showDatePicker(
                          context: context,
                          initialDate: d.dob ?? DateTime(2000),
                          firstDate: DateTime(1950),
                          lastDate: DateTime.now(),
                        );
                        if (v != null) setState(() => d.dob = v);
                      },
                    ),
                  ],
                ),
              ),
            ),
          OutlinedButton.icon(
            onPressed: () => setState(() => _docs.add(_Doc(''))),
            icon: const Icon(Icons.add),
            label: Text(context.t('addDocument')),
          ),
          const SizedBox(height: 16),
          if (filled.length >= 2)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: issues.isEmpty ? p.greenSoft : p.amberSoft, borderRadius: BorderRadius.circular(10)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (issues.isEmpty) Text(context.t('allMatch'), style: TextStyle(color: p.green, fontWeight: FontWeight.w700)),
                  for (final s in issues)
                    Padding(padding: const EdgeInsets.only(bottom: 4), child: Text(s, style: TextStyle(color: p.amber))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class PhotoCheckResult {
  PhotoCheckResult(this.format, this.kb, this.width, this.height);
  final String format;
  final double kb;
  final int width, height;
}

PhotoCheckResult? inspectImage(Uint8List bytes, String name) {
  final decoder = img.findDecoderForData(bytes);
  if (decoder == null) return null;
  final info = decoder.startDecode(bytes);
  if (info == null) return null;
  final ext = name.split('.').last.toLowerCase();
  return PhotoCheckResult(ext, bytes.length / 1024, info.width, info.height);
}

/// On-device validation against a specification extracted from the official notice. With no verified spec, no check is done.
class PhotoCheckScreen extends ConsumerStatefulWidget {
  const PhotoCheckScreen({super.key, this.examId});
  final int? examId;
  @override
  ConsumerState<PhotoCheckScreen> createState() => _PhotoCheckState();
}

class _PhotoCheckState extends ConsumerState<PhotoCheckScreen> {
  int? _exam;
  PhotoSpecOut? _spec;
  PhotoCheckResult? _r;

  @override
  void initState() {
    super.initState();
    _exam = widget.examId;
  }

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final saved = ref.watch(savedProvider).value ?? const {};
    final specs = _exam == null ? null : ref.watch(checklistProvider(_exam!));
    final available = specs?.value?.data.photoSpecs ?? const <PhotoSpecOut>[];
    Widget line(String label, String value, bool ok, String bad) => ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(ok ? Icons.check_circle : Icons.cancel, color: ok ? p.green : p.red),
      title: Text(label),
      subtitle: Text(ok ? value : '$value · $bad'),
    );
    return Scaffold(
      appBar: AppBar(title: Text(context.t('photoCheck'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(context.t('photoIntro')),
          const SizedBox(height: 12),
          DropdownButtonFormField<int>(
            value: saved.containsKey(_exam) ? _exam : null,
            isExpanded: true,
            decoration: InputDecoration(labelText: context.t('chooseExam')),
            items: [
              for (final s in saved.values)
                DropdownMenuItem(value: s.examId, child: Text(s.snapshot?.title ?? '#${s.examId}', overflow: TextOverflow.ellipsis)),
            ],
            onChanged:
                (v) => setState(() {
                  _exam = v;
                  _spec = null;
                  _r = null;
                }),
          ),
          const SizedBox(height: 12),
          if (_exam != null && specs != null && specs.isLoading) const Loading(),
          if (_exam != null && !(specs?.isLoading ?? true) && available.isEmpty)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: p.amberSoft, borderRadius: BorderRadius.circular(8)),
              child: Text(context.t('noSpec'), style: TextStyle(color: p.amber)),
            ),
          if (available.isNotEmpty)
            Wrap(
              spacing: 8,
              children: [
                for (final s in available)
                  ChoiceChip(label: Text(s.item), selected: _spec?.id == s.id, onSelected: (_) => setState(() => _spec = s)),
              ],
            ),
          if (_spec != null) ...[
            const SizedBox(height: 12),
            Text(
              '${context.t('specFrom')}: ${_spec!.minKb ?? '?'}–${_spec!.maxKb ?? '?'} KB'
              '${_spec!.width != null ? ', ${_spec!.width} × ${_spec!.height} px' : ''}, ${_spec!.formats.join('/')}',
            ),
            if (_spec!.evidence != null)
              Text('“${_spec!.evidence!.quote}”', style: TextStyle(color: p.muted, fontSize: 12, fontStyle: FontStyle.italic)),
            const SizedBox(height: 12),
            FilledButton.icon(
              icon: const Icon(Icons.image_outlined),
              label: Text(context.t('chooseImage')),
              onPressed: () async {
                final res = await FilePicker.pickFiles(type: FileType.image, withData: true);
                final f = res?.files.single;
                if (f?.bytes == null) return;
                setState(() => _r = inspectImage(f!.bytes!, f.name));
              },
            ),
          ],
          if (_r != null && _spec != null) ...[
            const SizedBox(height: 12),
            line(context.t('format'), _r!.format, _spec!.formats.isEmpty || _spec!.formats.contains(_r!.format), context.t('wrong')),
            line(
              context.t('fileSize'),
              '${_r!.kb.toStringAsFixed(1)} KB',
              (_spec!.minKb == null || _r!.kb >= _spec!.minKb!) && (_spec!.maxKb == null || _r!.kb <= _spec!.maxKb!),
              _r!.kb > (_spec!.maxKb ?? 1e9) ? context.t('tooBig') : context.t('tooSmall'),
            ),
            if (_spec!.width != null)
              line(
                context.t('dimensions'),
                '${_r!.width} × ${_r!.height}',
                _r!.width == _spec!.width && _r!.height == _spec!.height,
                context.t('wrong'),
              ),
          ],
        ],
      ),
    );
  }
}
