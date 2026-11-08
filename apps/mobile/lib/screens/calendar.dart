import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../api/models.g.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Month grid and agenda list. Warns when two saved exams fall on the same day.
class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});
  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  DateTime _day = today();
  bool _mine = true;
  bool _agenda = false;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final start = _agenda ? today() : DateTime(_month.year, _month.month, 1);
    final end = _agenda ? today().add(const Duration(days: 120)) : DateTime(_month.year, _month.month + 1, 0);
    final res = ref.watch(calendarProvider((start: start, end: end, mine: _mine)));
    final loc = context.lang == 'ml' ? 'ml' : 'en_IN';
    return Scaffold(
      appBar: AppBar(title: Text(context.t('calendar'))),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                SegmentedButton<bool>(
                  segments: [
                    ButtonSegment(value: true, label: Text(context.t('myOnly'))),
                    ButtonSegment(value: false, label: Text(context.t('allExams'))),
                  ],
                  selected: {_mine},
                  onSelectionChanged: (s) => setState(() => _mine = s.first),
                  showSelectedIcon: false,
                ),
                const Spacer(),
                IconButton(
                  tooltip: context.t(_agenda ? 'month' : 'list'),
                  onPressed: () => setState(() => _agenda = !_agenda),
                  icon: Icon(_agenda ? Icons.calendar_month : Icons.view_agenda_outlined),
                ),
              ],
            ),
          ),
          Expanded(
            child: res.when(
              loading: () => const Loading(),
              error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(calendarProvider)),
              data: (f) {
                final byDay = <DateTime, List<CalendarEntry>>{};
                for (final e in f.data) {
                  byDay.putIfAbsent(DateTime(e.date.year, e.date.month, e.date.day), () => []).add(e);
                }
                final clashes =
                    byDay.entries
                        .where(
                          (x) =>
                              x.value.where((e) => e.eventType == 'exam' && e.precision == 'day').map((e) => e.examId).toSet().length > 1,
                        )
                        .map((x) => x.key)
                        .toList();
                final banner =
                    _mine && clashes.isNotEmpty
                        ? Container(
                          width: double.infinity,
                          margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(color: p.redSoft, borderRadius: BorderRadius.circular(8)),
                          child: Text(
                            context.t('clash', {'date': fmtDate(context, clashes.first)}),
                            style: TextStyle(color: p.red, fontWeight: FontWeight.w600),
                          ),
                        )
                        : const SizedBox.shrink();
                if (_agenda) {
                  final days = byDay.keys.toList()..sort();
                  return ListView(
                    children: [
                      StaleBanner(f),
                      banner,
                      if (days.isEmpty) EmptyNote(context.t('nothingUpcoming')),
                      for (final d in days) ...[
                        Padding(
                          padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
                          child: Text(DateFormat('EEEE, d MMMM', loc).format(d), style: const TextStyle(fontWeight: FontWeight.w700)),
                        ),
                        for (final e in byDay[d]!) _EntryTile(e),
                      ],
                    ],
                  );
                }
                final first = DateTime(_month.year, _month.month, 1);
                final lead = (first.weekday + 6) % 7; // Monday first
                final daysIn = DateTime(_month.year, _month.month + 1, 0).day;
                final selected = byDay[_day] ?? const [];
                return ListView(
                  children: [
                    StaleBanner(f),
                    banner,
                    Padding(
                      padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
                      child: Row(
                        children: [
                          IconButton(
                            onPressed: () => setState(() => _month = DateTime(_month.year, _month.month - 1)),
                            icon: const Icon(Icons.chevron_left),
                          ),
                          Expanded(
                            child: Text(
                              DateFormat('MMMM yyyy', loc).format(_month),
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                          ),
                          IconButton(
                            onPressed: () => setState(() => _month = DateTime(_month.year, _month.month + 1)),
                            icon: const Icon(Icons.chevron_right),
                          ),
                        ],
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: GridView.count(
                        crossAxisCount: 7,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        childAspectRatio: 0.95,
                        children: [
                          for (final w in ['M', 'T', 'W', 'T', 'F', 'S', 'S'])
                            Center(child: Text(w, style: TextStyle(color: p.muted, fontWeight: FontWeight.w600))),
                          for (var i = 0; i < lead; i++) const SizedBox.shrink(),
                          for (var d = 1; d <= daysIn; d++)
                            _DayCell(DateTime(_month.year, _month.month, d), byDay, _day, clashes, (x) => setState(() => _day = x)),
                        ],
                      ),
                    ),
                    const Divider(),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                      child: Text(DateFormat('EEEE, d MMMM', loc).format(_day), style: const TextStyle(fontWeight: FontWeight.w700)),
                    ),
                    if (selected.isEmpty) EmptyNote(context.t('nothingThisDay'), icon: Icons.event_available_outlined),
                    for (final e in selected) _EntryTile(e),
                    const SizedBox(height: 24),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _DayCell extends StatelessWidget {
  const _DayCell(this.d, this.byDay, this.selected, this.clashes, this.onTap);
  final DateTime d;
  final Map<DateTime, List<CalendarEntry>> byDay;
  final DateTime selected;
  final List<DateTime> clashes;
  final ValueChanged<DateTime> onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final items = byDay[d] ?? const [];
    final isSel = d == selected;
    final isToday = d == today();
    final hasDeadline = items.any((e) => e.isDeadline);
    final hasExam = items.any((e) => e.eventType == 'exam');
    return InkWell(
      onTap: () => onTap(d),
      borderRadius: BorderRadius.circular(8),
      child: Container(
        margin: const EdgeInsets.all(2),
        decoration: BoxDecoration(
          color: isSel ? p.greenSoft : null,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: clashes.contains(d) ? p.red : (isToday ? p.green : Colors.transparent)),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('${d.day}', style: TextStyle(fontWeight: isToday ? FontWeight.w800 : FontWeight.w500, fontFeatures: tabular)),
            const SizedBox(height: 3),
            SizedBox(
              height: 6,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (hasDeadline) _dot(p.amber),
                  if (hasExam) _dot(p.green),
                  if (items.isNotEmpty && !hasDeadline && !hasExam) _dot(p.muted),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _dot(Color c) => Container(
    width: 6,
    height: 6,
    margin: const EdgeInsets.symmetric(horizontal: 1),
    decoration: BoxDecoration(color: c, shape: BoxShape.circle),
  );
}

class _EntryTile extends StatelessWidget {
  const _EntryTile(this.e);
  final CalendarEntry e;
  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    return ListTile(
      leading: Icon(
        e.isDeadline ? Icons.timer_outlined : (e.eventType == 'exam' ? Icons.edit_note : Icons.event_note),
        color: e.isDeadline ? p.amber : p.green,
      ),
      title: Text(e.title),
      subtitle: Text(e.examTitle, maxLines: 2, overflow: TextOverflow.ellipsis),
      trailing: CertaintyTag(e.certainty),
      onTap: () => context.push('/exam/${e.examId}'),
    );
  }
}
