import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/models.g.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Paste a link or message, or upload a PDF. The result always lists its evidence and never says "safe".
class ScamScreen extends ConsumerStatefulWidget {
  const ScamScreen({super.key});
  @override
  ConsumerState<ScamScreen> createState() => _ScamScreenState();
}

class _ScamScreenState extends ConsumerState<ScamScreen> {
  String _kind = 'url';
  final _text = TextEditingController();
  ScamOut? _result;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _run(Future<ScamOut> Function() f) async {
    setState(() {
      _busy = true;
      _error = null;
      _result = null;
    });
    try {
      final r = await f();
      setState(() => _result = r);
    } catch (e) {
      setState(() => _error = e.toString() == 'network' ? context.t('couldNotLoad') : e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickPdf() async {
    final res = await FilePicker.pickFiles(type: FileType.custom, allowedExtensions: const ['pdf'], withData: true);
    final f = res?.files.single;
    if (f?.bytes == null) return;
    if (f!.size > 5000000) {
      setState(() => _error = context.t('pdfTooLarge'));
      return;
    }
    await _run(() => ref.read(apiProvider).scamPdf(f.bytes!, f.name));
  }

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    return Scaffold(
      appBar: AppBar(title: Text(context.t('scam'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(context.t('scamIntro')),
          const SizedBox(height: 14),
          SegmentedButton<String>(
            segments: [
              ButtonSegment(value: 'url', label: Text(context.t('scamLink')), icon: const Icon(Icons.link)),
              ButtonSegment(value: 'text', label: Text(context.t('scamMessage')), icon: const Icon(Icons.sms_outlined)),
              ButtonSegment(value: 'pdf', label: Text(context.t('scamPdf')), icon: const Icon(Icons.picture_as_pdf_outlined)),
            ],
            selected: {_kind},
            onSelectionChanged:
                (s) => setState(() {
                  _kind = s.first;
                  _result = null;
                }),
          ),
          const SizedBox(height: 14),
          if (_kind != 'pdf') ...[
            TextField(
              controller: _text,
              minLines: _kind == 'url' ? 1 : 5,
              maxLines: _kind == 'url' ? 2 : 12,
              keyboardType: _kind == 'url' ? TextInputType.url : TextInputType.multiline,
              decoration: InputDecoration(hintText: context.t(_kind == 'url' ? 'scamPasteLink' : 'scamPasteMessage')),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed:
                  _busy || _text.text.trim().length < 3
                      ? null
                      : () => _run(() => ref.read(apiProvider).scamCheck(_kind, _text.text.trim())),
              child: Text(context.t('check')),
            ),
          ] else
            FilledButton.icon(onPressed: _busy ? null : _pickPdf, icon: const Icon(Icons.upload_file), label: Text(context.t('choosePdf'))),
          if (_busy) const Loading(),
          if (_error != null) Padding(padding: const EdgeInsets.only(top: 16), child: Text(_error!, style: TextStyle(color: p.red))),
          if (_result != null) _Result(_result!),
        ],
      ),
    );
  }
}

class _Result extends StatelessWidget {
  const _Result(this.r);
  final ScamOut r;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final (key, fg, bg, icon) = switch (r.verdict) {
      'Verified on official source' => ('v_verified', p.green, p.greenSoft, Icons.verified_outlined),
      'Suspicious' => ('v_suspicious', p.red, p.redSoft, Icons.warning_amber_rounded),
      'Known fake' => ('v_fake', p.red, p.redSoft, Icons.dangerous_outlined),
      _ => ('v_not_found', p.amber, p.amberSoft, Icons.help_outline),
    };
    final levelIcon = {
      'ok': Icons.check,
      'info': Icons.info_outline,
      'warn': Icons.error_outline,
      'bad': Icons.close,
      'fake': Icons.dangerous_outlined,
    };
    final levelColor = {'ok': p.green, 'info': p.muted, 'warn': p.amber, 'bad': p.red, 'fake': p.red};
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(10)),
            child: Row(
              children: [
                Icon(icon, color: fg, size: 30),
                const SizedBox(width: 12),
                Expanded(child: Text(context.t(key), style: TextStyle(color: fg, fontSize: 18, fontWeight: FontWeight.w700))),
              ],
            ),
          ),
          SectionHeader(context.t('whatWeFound')),
          for (final e in r.evidence)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(levelIcon[e.level] ?? Icons.info_outline, color: levelColor[e.level] ?? p.muted),
              title: Text(e.text),
              onTap: e.url == null ? null : () => openUrl(context, e.url!),
            ),
          const SizedBox(height: 8),
          Text(r.disclaimer, style: TextStyle(color: p.muted, fontSize: 12.5)),
          const SizedBox(height: 4),
          Text(context.t('neverPay'), style: TextStyle(color: p.red, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
