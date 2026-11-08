import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../api/models.g.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';

class AlertsScreen extends ConsumerWidget {
  const AlertsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = context.pal;
    final inbox = ref.watch(inboxProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(context.t('alerts')),
        actions: [
          IconButton(tooltip: context.t('alertSettings'), onPressed: () => context.push('/alerts/settings'), icon: const Icon(Icons.tune)),
        ],
      ),
      body: inbox.when(
        loading: () => const Loading(),
        error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(inboxProvider)),
        data: (items) {
          if (items.isEmpty) return EmptyNote(context.t('inboxEmpty'), icon: Icons.notifications_none);
          return RefreshIndicator(
            onRefresh: () => ref.refresh(inboxProvider.future),
            child: ListView(
              children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () async {
                      await ref.read(apiProvider).markRead(items.map((n) => n.id).toList());
                      ref.invalidate(inboxProvider);
                    },
                    child: Text(context.t('markAllRead')),
                  ),
                ),
                for (final n in items) ...[
                  ListTile(
                    leading: Icon(
                      n.urgent ? Icons.priority_high : Icons.notifications_none,
                      color: n.urgent ? p.red : (n.read ? p.muted : p.green),
                    ),
                    title: Text(n.title, style: TextStyle(fontWeight: n.read ? FontWeight.w400 : FontWeight.w700)),
                    subtitle: Text('${n.body}\n${ago(context, n.createdAt)}'),
                    isThreeLine: true,
                    onTap: () {
                      ref.read(apiProvider).markRead([n.id]).ignore();
                      final u = Uri.parse(n.deepLink);
                      context.push('/${u.host}${u.path}${u.hasQuery ? '?${u.query}' : ''}');
                    },
                  ),
                  const Divider(),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

const _types = [
  'new_notice',
  'new_matching_exam',
  'application_opening',
  'deadline_7',
  'deadline_3',
  'deadline_1',
  'confirmation_deadline',
  'date_change',
  'link_change',
  'correction_window',
  'admit_card',
  'answer_key',
  'objection_deadline',
  'result',
];
const _typeNames = {
  'new_notice': 'New official notices',
  'new_matching_exam': 'New exams that match me',
  'application_opening': 'Applications opening',
  'deadline_7': 'Deadline in 7 days',
  'deadline_3': 'Deadline in 3 days',
  'deadline_1': 'Deadline tomorrow',
  'confirmation_deadline': 'Kerala PSC confirmation deadline',
  'date_change': 'Date changes',
  'link_change': 'Link changes',
  'correction_window': 'Correction window',
  'admit_card': 'Admit cards',
  'answer_key': 'Answer keys',
  'objection_deadline': 'Objection deadlines',
  'result': 'Results and rank lists',
};

class AlertSettingsScreen extends ConsumerStatefulWidget {
  const AlertSettingsScreen({super.key});
  @override
  ConsumerState<AlertSettingsScreen> createState() => _AlertSettingsState();
}

class _AlertSettingsState extends ConsumerState<AlertSettingsScreen> {
  PrefsOut? _p;

  Future<void> _save(PrefsOut p) async {
    setState(() => _p = p);
    try {
      await ref.read(apiProvider).putPrefs(p);
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.t('couldNotLoad'))));
    }
  }

  PrefsOut _copy(PrefsOut p, {List<String>? types, Map<String, List<String>>? interests, String? qs, String? qe, int? max, bool? digest}) =>
      PrefsOut(
        enabledTypes: types ?? p.enabledTypes,
        interests: interests ?? p.interests,
        quietStart: qs ?? p.quietStart,
        quietEnd: qe ?? p.quietEnd,
        maxPerDay: max ?? p.maxPerDay,
        digest: digest ?? p.digest,
      );

  @override
  Widget build(BuildContext context) {
    final server = ref.watch(serverPrefsProvider);
    final meta = ref.watch(metaProvider).value?.data;
    return Scaffold(
      appBar: AppBar(title: Text(context.t('alertSettings'))),
      body: server.when(
        loading: () => const Loading(),
        error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(serverPrefsProvider)),
        data: (sp) {
          final p = _p ?? sp;
          if (p == null) return EmptyNote(context.t('couldNotLoad'));
          final orgs = p.interests['organisations'] ?? const <String>[];
          Future<void> pickTime(bool start) async {
            final cur = (start ? p.quietStart : p.quietEnd).split(':');
            final t = await showTimePicker(context: context, initialTime: TimeOfDay(hour: int.parse(cur[0]), minute: int.parse(cur[1])));
            if (t == null) return;
            final s = '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
            await _save(start ? _copy(p, qs: s) : _copy(p, qe: s));
          }

          return ListView(
            children: [
              SectionHeader(context.t('interests')),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  const SizedBox(width: 8),
                  for (final o in meta?.organisations ?? const <OrgOut>[])
                    FilterChip(
                      label: Text(o.name),
                      selected: orgs.contains(o.key),
                      onSelected:
                          (on) => _save(
                            _copy(
                              p,
                              interests: {
                                ...p.interests,
                                'organisations': on ? [...orgs, o.key] : orgs.where((x) => x != o.key).toList(),
                              },
                            ),
                          ),
                    ),
                ],
              ),
              SectionHeader(context.t('alertTypes')),
              for (final t in _types)
                SwitchListTile(
                  title: Text(_typeNames[t] ?? t),
                  value: p.enabledTypes.contains(t),
                  onChanged: (on) => _save(_copy(p, types: on ? [...p.enabledTypes, t] : p.enabledTypes.where((x) => x != t).toList())),
                ),
              SectionHeader(context.t('quietHours')),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(context.t('quietHelp'), style: TextStyle(color: context.pal.muted)),
              ),
              ListTile(title: Text(context.t('from')), trailing: Text(p.quietStart), onTap: () => pickTime(true)),
              ListTile(title: Text(context.t('to')), trailing: Text(p.quietEnd), onTap: () => pickTime(false)),
              ListTile(
                title: Text(context.t('maxPerDay')),
                trailing: DropdownButton<int>(
                  value: p.maxPerDay,
                  items: [
                    for (final n in const [2, 4, 6, 10, 20]) DropdownMenuItem(value: n, child: Text('$n')),
                  ],
                  onChanged: (v) => v == null ? null : _save(_copy(p, max: v)),
                ),
              ),
              SwitchListTile(title: Text(context.t('bundle')), value: p.digest, onChanged: (v) => _save(_copy(p, digest: v))),
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }
}
