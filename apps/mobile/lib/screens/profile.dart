import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';

import '../api/models.g.dart';
import '../config.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Profile data is collected only for eligibility checks, with the purpose shown next to each field.
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});
  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  DateTime? _dob;
  String? _category, _community, _gender;
  bool? _pwd, _exsm;
  List<QualIn> _quals = [];
  final _langs = <String>{};
  bool _loaded = false;

  void _load(ProfileData? p) {
    if (_loaded) return;
    _loaded = true;
    if (p == null) return;
    _dob = p.dateOfBirth;
    _category = p.category;
    _community = p.keralaCommunity;
    _gender = p.gender;
    _pwd = p.pwd;
    _exsm = p.exServiceman;
    _quals = [...p.qualifications];
    _langs.addAll(p.languages);
  }

  ProfileData _build() => ProfileData(
    dateOfBirth: _dob,
    category: _category,
    keralaCommunity: _community,
    pwd: _pwd,
    exServiceman: _exsm,
    gender: _gender,
    nationality: 'indian',
    domicileState: null,
    qualifications: _quals,
    languages: _langs.toList(),
    attempts: const {},
  );

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final prof = ref.watch(profileProvider);
    final meta = ref.watch(metaProvider).value?.data;
    final settings = ref.watch(settingsProvider);
    if (prof.isLoading) return Scaffold(appBar: AppBar(), body: const Loading());
    _load(prof.value);
    final quals = {for (final q in meta?.qualifications ?? const <Map<String, dynamic>>[]) q['code'] as String: q['name'] as String};
    final communities = {
      for (final c in meta?.keralaCommunities ?? const <Map<String, dynamic>>[]) c['code'] as String: c['name'] as String,
    };

    Widget why(String key) => Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
      child: Text(context.t(key), style: TextStyle(color: p.muted, fontSize: 12.5)),
    );

    return Scaffold(
      appBar: AppBar(title: Text(context.t('profile'))),
      body: ListView(
        children: [
          Padding(padding: const EdgeInsets.all(16), child: Text(context.t('profileWhy'))),
          ListTile(
            title: Text(context.t('dob')),
            subtitle: Text(_dob == null ? context.t('notSet') : fmtDate(context, _dob)),
            trailing: const Icon(Icons.edit_calendar_outlined),
            onTap: () async {
              final d = await showDatePicker(
                context: context,
                initialDate: _dob ?? DateTime(2000),
                firstDate: DateTime(1950),
                lastDate: DateTime.now(),
              );
              if (d != null) setState(() => _dob = d);
            },
          ),
          why('dobWhy'),
          _dropdown(context.t('category'), _category, {
            for (final c in meta?.centralCategories ?? const ['GEN', 'EWS', 'OBC', 'SC', 'ST']) c: c,
          }, (v) => setState(() => _category = v)),
          why('categoryWhy'),
          _dropdown(context.t('keralaCommunity'), _community, communities, (v) => setState(() => _community = v)),
          _dropdown(context.t('gender'), _gender, {
            'female': context.t('female'),
            'male': context.t('male'),
            'other': context.t('other'),
          }, (v) => setState(() => _gender = v)),
          SwitchListTile(title: Text(context.t('pwd')), value: _pwd ?? false, onChanged: (v) => setState(() => _pwd = v)),
          SwitchListTile(title: Text(context.t('exServiceman')), value: _exsm ?? false, onChanged: (v) => setState(() => _exsm = v)),
          SectionHeader(context.t('qualifications'), action: context.t('addQualification'), onAction: () => _addQual(quals)),
          for (final (i, q) in _quals.indexed)
            ListTile(
              title: Text(quals[q.code] ?? q.code),
              subtitle: Text(context.t('q_${q.status}') + (q.percentage != null ? ' · ${q.percentage}%' : '')),
              trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => setState(() => _quals.removeAt(i))),
            ),
          SectionHeader(context.t('languages')),
          Wrap(
            spacing: 8,
            children: [
              const SizedBox(width: 8),
              for (final l in const ['english', 'malayalam', 'hindi', 'tamil', 'kannada'])
                FilterChip(
                  label: Text(l[0].toUpperCase() + l.substring(1)),
                  selected: _langs.contains(l),
                  onSelected: (on) => setState(() => on ? _langs.add(l) : _langs.remove(l)),
                ),
            ],
          ),
          const SizedBox(height: 8),
          SwitchListTile(
            title: Text(context.t('syncProfile')),
            subtitle: Text(context.t('syncHelp')),
            value: settings.syncProfile,
            onChanged: (on) async {
              await ref.read(settingsProvider.notifier).update(settings.copyWith(syncProfile: on));
              if (!on) ref.read(apiProvider).deleteProfile().ignore();
            },
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton(
              onPressed: () async {
                try {
                  await ref.read(profileProvider.notifier).save(_build());
                  ref.invalidate(eligibilityProvider);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.t('savedOk'))));
                    context.pop();
                  }
                } catch (e) {
                  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
                }
              },
              child: Text(context.t('saveDetails')),
            ),
          ),
        ],
      ),
    );
  }

  Widget _dropdown(String label, String? value, Map<String, String> options, ValueChanged<String?> onChanged) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
    child: DropdownButtonFormField<String?>(
      value: options.containsKey(value) ? value : null,
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      items: [
        DropdownMenuItem(value: null, child: Text(context.t('notSet'))),
        for (final e in options.entries) DropdownMenuItem(value: e.key, child: Text(e.value, overflow: TextOverflow.ellipsis)),
      ],
      onChanged: onChanged,
    ),
  );

  Future<void> _addQual(Map<String, String> quals) async {
    String? code;
    var status = 'completed';
    final pct = TextEditingController();
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder:
          (c) => StatefulBuilder(
            builder:
                (c, set) => Padding(
                  padding: EdgeInsets.fromLTRB(16, 16, 16, MediaQuery.of(c).viewInsets.bottom + 16),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      DropdownButtonFormField<String>(
                        isExpanded: true,
                        decoration: InputDecoration(labelText: context.t('qualifications')),
                        items: [for (final e in quals.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
                        onChanged: (v) => set(() => code = v),
                      ),
                      const SizedBox(height: 12),
                      SegmentedButton<String>(
                        segments: [
                          for (final s in const ['completed', 'final_year', 'appearing'])
                            ButtonSegment(value: s, label: Text(context.t('q_$s'))),
                        ],
                        selected: {status},
                        onSelectionChanged: (s) => set(() => status = s.first),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: pct,
                        keyboardType: TextInputType.number,
                        decoration: InputDecoration(labelText: context.t('percentage')),
                      ),
                      const SizedBox(height: 12),
                      FilledButton(onPressed: () => Navigator.pop(c, true), child: Text(context.t('save'))),
                    ],
                  ),
                ),
          ),
    );
    if (ok == true && code != null) {
      setState(() => _quals.add(QualIn(code: code!, status: status, percentage: double.tryParse(pct.text))));
    }
  }
}

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});
  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final _server = TextEditingController(text: ref.read(settingsProvider).apiBase);

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(settingsProvider);
    final n = ref.read(settingsProvider.notifier);
    final p = context.pal;
    return Scaffold(
      appBar: AppBar(title: Text(context.t('settings'))),
      body: ListView(
        children: [
          ListTile(
            title: Text(context.t('language')),
            trailing: SegmentedButton<String>(
              segments: const [ButtonSegment(value: 'en', label: Text('English')), ButtonSegment(value: 'ml', label: Text('മലയാളം'))],
              selected: {s.lang},
              showSelectedIcon: false,
              onSelectionChanged: (v) => n.update(s.copyWith(lang: v.first)),
            ),
          ),
          ListTile(
            title: Text(context.t('textSize')),
            trailing: SegmentedButton<bool>(
              segments: [
                ButtonSegment(value: false, label: Text(context.t('textNormal'))),
                ButtonSegment(value: true, label: Text(context.t('textLarge'))),
              ],
              selected: {s.largeText},
              showSelectedIcon: false,
              onSelectionChanged: (v) => n.update(s.copyWith(largeText: v.first)),
            ),
          ),
          SwitchListTile(
            title: Text(context.t('lowData')),
            subtitle: Text(context.t('lowDataHelp')),
            value: s.lowData,
            onChanged: (v) => n.update(s.copyWith(lowData: v)),
          ),
          SectionHeader(context.t('profile')),
          ListTile(
            leading: const Icon(Icons.download_outlined),
            title: Text(context.t('exportData')),
            onTap: () async {
              final local = {
                'profile_on_this_phone': (await ref.read(profileProvider.future))?.toJson(),
                'saved_on_this_phone': [
                  for (final r in await ref.read(dbProvider).savedRows()) {'exam_id': r.examId, 'status': r.status},
                ],
              };
              Map<String, dynamic>? server;
              try {
                if (s.token != null) server = await ref.read(apiProvider).export();
              } catch (_) {}
              final text = const JsonEncoder.withIndent('  ').convert({'app': AppConfig.appName, 'local': local, 'server': server});
              await SharePlus.instance.share(ShareParams(text: text, subject: '${AppConfig.appName} data export'));
            },
          ),
          ListTile(
            leading: Icon(Icons.delete_forever_outlined, color: p.red),
            title: Text(context.t('deleteData'), style: TextStyle(color: p.red)),
            onTap: () async {
              final yes = await showDialog<bool>(
                context: context,
                builder:
                    (c) => AlertDialog(
                      content: Text(context.t('deleteConfirm')),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(c, false), child: Text(context.t('cancel'))),
                        TextButton(
                          onPressed: () => Navigator.pop(c, true),
                          child: Text(context.t('delete'), style: TextStyle(color: p.red)),
                        ),
                      ],
                    ),
              );
              if (yes != true) return;
              try {
                if (s.token != null) await ref.read(apiProvider).deleteMe();
              } catch (_) {}
              await ref.read(dbProvider).wipe();
              await n.clearToken();
              ref.invalidate(savedProvider);
              ref.invalidate(profileProvider);
              if (context.mounted) context.go('/home');
            },
          ),
          SectionHeader(context.t('serverAddress')),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: TextField(
              controller: _server,
              keyboardType: TextInputType.url,
              onSubmitted: (v) async {
                await n.update(s.copyWith(apiBase: v.trim()));
                await n.clearToken();
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(context.t('version', {'v': AppConfig.version}), style: TextStyle(color: p.muted)),
          ),
        ],
      ),
    );
  }
}
