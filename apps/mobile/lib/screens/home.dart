import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../api/models.g.dart';
import '../config.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Action-first: what the user must do next for saved exams, then what is closing soon, changes, and new notices.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = context.pal;
    final settings = ref.watch(settingsProvider);
    final saved = ref.watch(savedProvider);
    final group = settings.groups.length == 1 ? settings.groups.first : null;
    final open = ref.watch(examsProvider((q: null, group: group, status: 'open', sort: 'deadline')));
    final notices = settings.lowData ? null : ref.watch(noticesProvider);

    final actions = <_Action>[];
    for (final s in (saved.value ?? const <int, SavedEntry>{}).values) {
      final d = s.snapshot;
      if (d == null) continue;
      for (final e in d.events) {
        if (e.status != 'active' || e.dateStart == null) continue;
        final n = daysUntil(e.dateStart!);
        final relevant =
            (e.isDeadline && n >= 0 && n <= 45) ||
            (e.eventType == 'admit_card' && n >= -10 && n <= 7) ||
            (e.eventType == 'exam' && n >= 0 && n <= 30);
        if (e.eventType == 'application_end' &&
            const ['applied', 'confirmed', 'admit_card', 'exam_taken', 'result_checked'].contains(s.status)) {
          continue;
        }
        if (relevant) actions.add(_Action(d, e));
      }
    }
    actions.sort((a, b) => a.e.dateStart!.compareTo(b.e.dateStart!));
    final changed = (saved.value ?? const <int, SavedEntry>{}).values.where((s) => s.snapshot?.hasChanges ?? false).toList();

    return Scaffold(
      appBar: AppBar(
        title: Text(AppConfig.appName),
        actions: [
          IconButton(tooltip: context.t('scam'), onPressed: () => context.push('/scam'), icon: const Icon(Icons.verified_user_outlined)),
          IconButton(tooltip: context.t('alerts'), onPressed: () => context.push('/alerts'), icon: const Icon(Icons.notifications_none)),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(examsProvider);
          ref.invalidate(noticesProvider);
          for (final id in (saved.value ?? const <int, SavedEntry>{}).keys) {
            ref.invalidate(examDetailProvider(id));
          }
          try {
            await ref.read(examsProvider((q: null, group: group, status: 'open', sort: 'deadline')).future);
          } catch (_) {}
        },
        child: ListView(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Text(
                '${context.t('today')}, ${DateFormat('EEEE d MMMM', context.lang == 'ml' ? 'ml' : 'en_IN').format(DateTime.now())}',
                style: TextStyle(color: p.muted),
              ),
            ),
            SectionHeader(context.t('whatToDo')),
            if (saved.isLoading) const Loading(),
            if (!saved.isLoading && (saved.value?.isEmpty ?? true))
              Card(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                child: EmptyNote(
                  context.t('trackHint'),
                  icon: Icons.bookmark_border,
                  action: context.t('browseExams'),
                  onAction: () => context.go('/exams'),
                ),
              ),
            if (!saved.isLoading && (saved.value?.isNotEmpty ?? false) && actions.isEmpty)
              Card(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                child: EmptyNote(context.t('nothingToDo'), icon: Icons.check_circle_outline),
              ),
            if (actions.isNotEmpty)
              Card(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(
                  children: [
                    for (final (i, a) in actions.take(8).indexed) ...[if (i > 0) const Divider(), _ActionRow(a)],
                  ],
                ),
              ),
            if (changed.isNotEmpty) ...[
              SectionHeader(context.t('changesTitle')),
              Card(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(
                  children: [
                    for (final s in changed)
                      ListTile(
                        leading: Icon(Icons.history, color: p.amber),
                        title: Text(s.snapshot!.title, maxLines: 2, overflow: TextOverflow.ellipsis),
                        subtitle: Text(s.snapshot!.changes.isEmpty ? '' : s.snapshot!.changes.first.eventTitle),
                        onTap: () => context.push('/exam/${s.examId}?tab=changes'),
                      ),
                  ],
                ),
              ),
            ],
            SectionHeader(context.t('closingSoon'), action: context.t('seeAll'), onAction: () => context.go('/exams')),
            open.when(
              loading: () => const Loading(),
              error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(examsProvider)),
              data: (f) {
                final items =
                    f.data.items
                        .where((e) => e.applicationEnd?.dateStart != null && daysUntil(e.applicationEnd!.dateStart!) <= 21)
                        .take(6)
                        .toList();
                return Column(
                  children: [
                    StaleBanner(f),
                    if (items.isEmpty) EmptyNote(context.t('nothingUpcoming')),
                    for (final e in items) ...[ExamTile(e, onTap: () => context.push('/exam/${e.id}')), const Divider()],
                  ],
                );
              },
            ),
            if (notices != null) ...[
              SectionHeader(context.t('newNotices'), action: context.t('seeAll'), onAction: () => context.push('/notices')),
              notices.when(
                loading: () => const Loading(),
                error: (e, _) => const SizedBox.shrink(),
                data:
                    (f) => Column(
                      children: [
                        for (final n in f.data.items.take(5))
                          ListTile(
                            leading: Icon(Icons.campaign_outlined, color: p.green),
                            title: Text(n.title, maxLines: 2, overflow: TextOverflow.ellipsis),
                            subtitle: Text('${n.organisation.name} · ${ago(context, n.firstSeenAt)}'),
                            onTap:
                                () =>
                                    n.examId != null
                                        ? context.push('/exam/${n.examId}')
                                        : (n.url != null ? openUrl(context, n.url!) : null),
                          ),
                      ],
                    ),
              ),
            ],
            const Disclaimer(),
          ],
        ),
      ),
    );
  }
}

class _Action {
  _Action(this.exam, this.e);
  final ExamDetail exam;
  final EventOut e;
}

class _ActionRow extends StatelessWidget {
  const _ActionRow(this.a);
  final _Action a;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final e = a.e;
    return InkWell(
      onTap: () => context.push('/exam/${a.exam.id}'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            DateBlock(date: e.dateStart, precision: e.precision, tone: e.isDeadline ? p.amber : p.green),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(e.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 2),
                  Text(a.exam.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(color: p.muted, fontSize: 13)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      CertaintyTag(e.certainty),
                      const SizedBox(width: 8),
                      if (daysUntil(e.dateStart!) >= 0) DaysLeft(e.dateStart!),
                    ],
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: p.muted),
          ],
        ),
      ),
    );
  }
}
