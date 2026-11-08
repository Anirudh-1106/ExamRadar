import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/state.dart';
import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';
import 'exam_detail.dart' show trackingSteps;

/// Saved exams with progress through interested, applied, confirmed, admit card, exam written, result checked.
class MyExamsScreen extends ConsumerWidget {
  const MyExamsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = context.pal;
    final saved = ref.watch(savedProvider);
    return Scaffold(
      appBar: AppBar(title: Text(context.t('navMyExams'))),
      body: saved.when(
        loading: () => const Loading(),
        error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(savedProvider)),
        data: (m) {
          if (m.isEmpty) {
            return EmptyNote(
              context.t('myExamsEmpty'),
              icon: Icons.bookmark_border,
              action: context.t('browseExams'),
              onAction: () => context.go('/exams'),
            );
          }
          final rows = m.values.toList()..sort((a, b) => b.savedAt.compareTo(a.savedAt));
          return RefreshIndicator(
            onRefresh: () async {
              for (final r in rows) {
                ref.invalidate(examDetailProvider(r.examId));
              }
              ref.invalidate(savedProvider);
            },
            child: ListView.separated(
              itemCount: rows.length,
              separatorBuilder: (_, __) => const Divider(),
              itemBuilder: (c, i) {
                final r = rows[i];
                final d = r.snapshot;
                final step = trackingSteps.indexOf(r.status ?? 'interested');
                final upcoming =
                    d?.events.where((e) => e.status == 'active' && e.dateStart != null && daysUntil(e.dateStart!) >= 0).toList()
                      ?..sort((a, b) => a.dateStart!.compareTo(b.dateStart!));
                final next = (upcoming == null || upcoming.isEmpty) ? null : upcoming.first;
                return InkWell(
                  onTap: () => context.push('/exam/${r.examId}'),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(d?.title ?? '#${r.examId}', style: Theme.of(context).textTheme.titleMedium),
                        if (d != null) Text(d.organisation.name, style: TextStyle(color: p.muted, fontSize: 13)),
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            for (var s = 0; s < trackingSteps.length; s++)
                              Expanded(
                                child: Container(
                                  height: 6,
                                  margin: const EdgeInsets.symmetric(horizontal: 1.5),
                                  decoration: BoxDecoration(color: s <= step ? p.green : p.line, borderRadius: BorderRadius.circular(3)),
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(context.t('stt_${r.status ?? 'interested'}'), style: TextStyle(color: p.green, fontWeight: FontWeight.w600)),
                        if (next != null) ...[
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 8,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              Text(
                                context.t('next', {
                                  'what': '${next.title}, ${fmtDate(context, next.dateStart, precision: next.precision)}',
                                }),
                              ),
                              CertaintyTag(next.certainty),
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
