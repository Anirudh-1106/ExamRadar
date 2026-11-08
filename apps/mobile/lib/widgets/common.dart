import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/models.g.dart';
import '../data/api.dart';
import '../l10n/strings.dart';
import '../theme.dart';

DateTime today() {
  final n = DateTime.now();
  return DateTime(n.year, n.month, n.day);
}

int daysUntil(DateTime d) => DateTime(d.year, d.month, d.day).difference(today()).inDays;

String fmtDate(BuildContext c, DateTime? d, {String precision = 'day', DateTime? end}) {
  if (d == null) return '—';
  final loc = c.lang == 'ml' ? 'ml' : 'en_IN';
  if (precision == 'month') return DateFormat('MMMM yyyy', loc).format(d);
  final s = DateFormat('d MMM yyyy', loc).format(d);
  return end != null && end != d ? '$s – ${DateFormat('d MMM yyyy', loc).format(end)}' : s;
}

String ago(BuildContext c, DateTime t) {
  final diff = DateTime.now().difference(t.isUtc ? t.toLocal() : t.add(DateTime.now().timeZoneOffset));
  if (diff.inMinutes < 60) return '${diff.inMinutes.clamp(1, 59)} min ago';
  if (diff.inHours < 24) return '${diff.inHours} h ago';
  return c.t('daysAgo', {'n': diff.inDays});
}

Future<void> openUrl(BuildContext context, String url) async {
  final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  if (!ok && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.t('openLinkFailed'))));
  }
}

/// A tear-off calendar block. Month precision shows the month only, so it never looks like a real day.
class DateBlock extends StatelessWidget {
  const DateBlock({super.key, required this.date, this.precision = 'day', this.tone});
  final DateTime? date;
  final String precision;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final color = tone ?? p.green;
    final loc = context.lang == 'ml' ? 'ml' : 'en_IN';
    return Container(
      width: 54,
      decoration: BoxDecoration(color: p.surface, borderRadius: BorderRadius.circular(8), border: Border.all(color: p.line)),
      clipBehavior: Clip.antiAlias,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: double.infinity,
            color: color,
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Text(
              date == null ? '' : DateFormat('MMM', loc).format(date!).toUpperCase(),
              textAlign: TextAlign.center,
              style: TextStyle(color: p.surface, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.8),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text(
              date == null ? '?' : (precision == 'month' ? '${date!.year}' : '${date!.day}'),
              style: TextStyle(fontSize: precision == 'month' ? 14 : 22, fontWeight: FontWeight.w700, color: p.ink, fontFeatures: tabular),
            ),
          ),
        ],
      ),
    );
  }
}

class Tag extends StatelessWidget {
  const Tag(this.text, {super.key, required this.fg, required this.bg, this.outlined = false, this.onTap});
  final String text;
  final Color fg, bg;
  final bool outlined;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final w = Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: outlined ? Colors.transparent : bg,
        borderRadius: BorderRadius.circular(5),
        border: Border.all(color: outlined ? fg : bg),
      ),
      child: Text(text, style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600)),
    );
    return onTap == null ? w : InkWell(onTap: onTap, borderRadius: BorderRadius.circular(5), child: w);
  }
}

class CertaintyTag extends StatelessWidget {
  const CertaintyTag(this.certainty, {super.key});
  final String certainty;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final (fg, bg, outlined) = switch (certainty) {
      'official' => (p.green, p.greenSoft, false),
      'tentative' => (p.amber, p.amberSoft, true),
      _ => (p.muted, p.paper, true),
    };
    return Tag(
      context.t('cert_$certainty'),
      fg: fg,
      bg: bg,
      outlined: outlined,
      onTap: () {
        showDialog<void>(
          context: context,
          builder:
              (c) => AlertDialog(
                title: Text(context.t('cert_$certainty')),
                content: Text(context.t('cert_${certainty}_help')),
                actions: [TextButton(onPressed: () => Navigator.pop(c), child: Text(context.t('ok')))],
              ),
        );
      },
    );
  }
}

class StatusTag extends StatelessWidget {
  const StatusTag(this.status, {super.key});
  final String status;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final (fg, bg) = switch (status) {
      'open' => (p.green, p.greenSoft),
      'upcoming' => (p.blue, p.paper),
      'exam_scheduled' => (p.amber, p.amberSoft),
      'cancelled' => (p.red, p.redSoft),
      _ => (p.muted, p.paper),
    };
    return Tag(context.t('st_$status'), fg: fg, bg: bg);
  }
}

class DaysLeft extends StatelessWidget {
  const DaysLeft(this.date, {super.key, this.big = false});
  final DateTime date;
  final bool big;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final n = daysUntil(date);
    final color = n <= 1 ? p.red : (n <= 7 ? p.amber : p.muted);
    final text = n <= 0 ? context.t('dueToday') : (n == 1 ? context.t('dayLeft') : context.t('daysLeft', {'n': n}));
    return Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: big ? 15 : 13, fontFeatures: tabular));
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.action, this.onAction});
  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(16, 22, 8, 8),
    child: Row(
      children: [
        Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
        if (action != null) TextButton(onPressed: onAction, child: Text(action!)),
      ],
    ),
  );
}

class EmptyNote extends StatelessWidget {
  const EmptyNote(this.text, {super.key, this.action, this.onAction, this.icon = Icons.inbox_outlined});
  final String text;
  final String? action;
  final VoidCallback? onAction;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(20),
    child: Column(
      children: [
        Icon(icon, color: context.pal.muted, size: 32),
        const SizedBox(height: 8),
        Text(text, textAlign: TextAlign.center, style: TextStyle(color: context.pal.muted)),
        if (action != null) ...[const SizedBox(height: 12), OutlinedButton(onPressed: onAction, child: Text(action!))],
      ],
    ),
  );
}

class ErrorNote extends StatelessWidget {
  const ErrorNote({super.key, required this.onRetry, this.error});
  final VoidCallback onRetry;
  final Object? error;

  @override
  Widget build(BuildContext context) => EmptyNote(
    error is ApiError && (error as ApiError).message != 'network' ? (error as ApiError).message : context.t('couldNotLoad'),
    icon: Icons.cloud_off_outlined,
    action: context.t('retry'),
    onAction: onRetry,
  );
}

class StaleBanner extends StatelessWidget {
  const StaleBanner(this.f, {super.key});
  final Fetched<Object?> f;

  @override
  Widget build(BuildContext context) {
    if (!f.stale) return const SizedBox.shrink();
    final p = context.pal;
    return Container(
      width: double.infinity,
      color: p.amberSoft,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        context.t('offline', {'time': f.savedAt == null ? '' : ago(context, f.savedAt!.toUtc())}),
        style: TextStyle(color: p.amber, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class Loading extends StatelessWidget {
  const Loading({super.key});
  @override
  Widget build(BuildContext context) => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator()));
}

/// One exam in a list. The most urgent date is shown with its certainty.
class ExamTile extends StatelessWidget {
  const ExamTile(this.e, {super.key, required this.onTap, this.trailing});
  final ExamSummary e;
  final VoidCallback onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final ev = e.applicationEnd != null && daysUntil(e.applicationEnd!.dateStart ?? DateTime(1900)) >= 0 ? e.applicationEnd : e.nextEvent;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            DateBlock(date: ev?.dateStart, precision: ev?.precision ?? 'day', tone: ev != null && ev.isDeadline ? p.amber : p.green),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(e.title, maxLines: 3, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 3),
                  Text(e.organisation.name, style: TextStyle(color: p.muted, fontSize: 13)),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      StatusTag(e.status),
                      if (ev != null) Text(ev.title, style: TextStyle(color: p.ink, fontSize: 13)),
                      if (ev != null) CertaintyTag(ev.certainty),
                      if (ev?.dateStart != null && daysUntil(ev!.dateStart!) >= 0 && ev.isDeadline) DaysLeft(ev.dateStart!),
                    ],
                  ),
                ],
              ),
            ),
            if (trailing != null) trailing!,
          ],
        ),
      ),
    );
  }
}

class Disclaimer extends StatelessWidget {
  const Disclaimer({super.key});
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(16, 24, 16, 32),
    child: Text(context.t('disclaimerShort'), style: TextStyle(color: context.pal.muted, fontSize: 12.5)),
  );
}

Future<void> copyText(BuildContext context, String text) async {
  await Clipboard.setData(ClipboardData(text: text));
  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.t('copied'))));
}
