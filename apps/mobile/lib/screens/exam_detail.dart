import 'package:add_2_calendar/add_2_calendar.dart' as cal;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';

import '../api/models.g.dart';
import '../config.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../services/notifications.dart';
import '../theme.dart';
import '../widgets/common.dart';

const trackingSteps = ['interested', 'applied', 'confirmed', 'admit_card', 'exam_taken', 'result_checked'];

class ExamDetailScreen extends ConsumerStatefulWidget {
  const ExamDetailScreen({super.key, required this.id, this.tab});
  final int id;
  final String? tab;
  @override
  ConsumerState<ExamDetailScreen> createState() => _ExamDetailScreenState();
}

class _ExamDetailScreenState extends ConsumerState<ExamDetailScreen> {
  final _changesKey = GlobalKey();
  bool _scrolled = false;

  @override
  Widget build(BuildContext context) {
    final res = ref.watch(examDetailProvider(widget.id));
    return Scaffold(
      appBar: AppBar(),
      body: res.when(
        loading: () => const Loading(),
        error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(examDetailProvider(widget.id))),
        data: (f) {
          if (widget.tab == 'changes' && !_scrolled) {
            _scrolled = true;
            WidgetsBinding.instance.addPostFrameCallback((_) {
              final c = _changesKey.currentContext;
              if (c != null) Scrollable.ensureVisible(c, duration: const Duration(milliseconds: 300));
            });
          }
          return RefreshIndicator(
            onRefresh: () => ref.refresh(examDetailProvider(widget.id).future),
            child: ListView(children: [StaleBanner(f), ..._body(context, f.data)]),
          );
        },
      ),
    );
  }

  List<Widget> _body(BuildContext context, ExamDetail d) {
    final p = context.pal;
    final saved = ref.watch(savedProvider).value ?? const {};
    final isSaved = saved.containsKey(d.id);
    final status = saved[d.id]?.status;
    final events = [...d.events]..sort((a, b) => (a.dateStart ?? DateTime(2100)).compareTo(b.dateStart ?? DateTime(2100)));
    return [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(d.organisation.name, style: TextStyle(color: p.muted, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(d.title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                StatusTag(d.status),
                Text(context.t('checked', {'time': ago(context, d.lastCheckedAt)}), style: TextStyle(color: p.muted, fontSize: 13)),
              ],
            ),
          ],
        ),
      ),
      if (d.isFastAlert) _Banner(context.t('fastAlert'), p.blue, p.paper),
      if (d.sourceStatus == 'stale') _Banner(context.t('sourceStale'), p.amber, p.amberSoft),
      if (d.sourceStatus == 'blocked') _Banner(context.t('sourceBlocked'), p.amber, p.amberSoft),
      if (d.sourceStatus == 'manual') _Banner(context.t('sourceManual'), p.muted, p.paper),
      if (d.apply != null) _ApplyCard(d.apply!),
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
        child: Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => ref.read(savedProvider.notifier).toggle(d.id, detail: d),
                icon: Icon(isSaved ? Icons.bookmark : Icons.bookmark_border, color: isSaved ? p.green : null),
                label: Text(context.t(isSaved ? 'saved' : 'save')),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                onPressed:
                    () => SharePlus.instance.share(
                      ShareParams(text: context.t('shareText', {'title': d.title, 'url': d.officialUrl, 'app': AppConfig.appName})),
                    ),
                icon: const Icon(Icons.share_outlined),
                label: Text(context.t('share')),
              ),
            ),
          ],
        ),
      ),
      if (isSaved) ...[
        SectionHeader(context.t('myProgress')),
        SizedBox(
          height: 44,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            children: [
              for (final s in trackingSteps)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: ChoiceChip(
                    label: Text(context.t('stt_$s')),
                    selected: status == s,
                    onSelected: (_) => ref.read(savedProvider.notifier).setStatus(d.id, s),
                  ),
                ),
            ],
          ),
        ),
      ],
      SectionHeader(context.t('keyDates')),
      Card(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(
          children: [
            if (events.isEmpty) EmptyNote(context.t('fastAlert'), icon: Icons.hourglass_empty),
            for (final (i, e) in events.indexed) ...[if (i > 0) const Divider(), _EventRow(e, d)],
          ],
        ),
      ),
      if (d.combinedWith.isNotEmpty)
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
          child: Text(context.t('combinedWith', {'list': d.combinedWith.join(', ')}), style: TextStyle(color: p.muted)),
        ),
      for (final n in d.confirmationNotes)
        Padding(padding: const EdgeInsets.fromLTRB(16, 8, 16, 0), child: Text(context.t('confirmationNote', {'text': n}))),
      _Eligibility(d),
      if (d.posts.isNotEmpty || d.vacanciesTotal != null || d.fees.isNotEmpty || d.qualificationText != null) ...[
        SectionHeader(context.t('posts')),
        Card(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (d.vacanciesTotal != null) _kv(context, context.t('vacancies'), '${d.vacanciesTotal}'),
                for (final post in d.posts) ...[
                  Text(post.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                  if (post.department != null) Text(post.department!, style: TextStyle(color: p.muted)),
                  if (post.vacanciesText != null) _kv(context, context.t('vacancies'), post.vacanciesText!),
                  if (post.payScale != null) _kv(context, context.t('pay'), post.payScale!),
                  const SizedBox(height: 8),
                ],
                if (d.fees.isNotEmpty) ...[
                  Text(context.t('fee'), style: const TextStyle(fontWeight: FontWeight.w700)),
                  for (final fee in d.fees)
                    _kv(
                      context,
                      fee.appliesTo == 'others' ? context.t('feeOthers', {'cats': fee.exempted.join(', ')}) : fee.categories.join(', '),
                      '₹${fee.amount}',
                    ),
                  const SizedBox(height: 8),
                ],
                if (d.qualificationText != null) ...[
                  Text(context.t('qualification'), style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(d.qualificationText!),
                ],
              ],
            ),
          ),
        ),
      ],
      _Checklist(d),
      SectionHeader(context.t('documents')),
      Card(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(
          children: [
            if (d.notificationPdf != null)
              ListTile(
                leading: const Icon(Icons.picture_as_pdf_outlined),
                title: Text(context.t('notificationPdf')),
                subtitle: Text(Uri.parse(d.notificationPdf!).host),
                onTap: () => openUrl(context, d.notificationPdf!),
              ),
            if (d.officialUrl.isNotEmpty)
              ListTile(
                leading: const Icon(Icons.public),
                title: Text(context.t('officialPage')),
                subtitle: Text(Uri.parse(d.officialUrl).host),
                onTap: () => openUrl(context, d.officialUrl),
              ),
            for (final l in d.links.where((l) => l.url != d.notificationPdf && l.url != d.officialUrl && l.kind != 'apply').take(6))
              ListTile(
                leading: const Icon(Icons.link),
                title: Text(l.label ?? l.kind, maxLines: 2, overflow: TextOverflow.ellipsis),
                subtitle: Text(l.host),
                onTap: () => openUrl(context, l.url),
              ),
          ],
        ),
      ),
      SectionHeader(context.t('changeHistory'), key: _changesKey),
      Card(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        child:
            d.changes.isEmpty
                ? EmptyNote(context.t('noChanges'), icon: Icons.history_toggle_off)
                : Column(
                  children: [
                    for (final c in d.changes)
                      ListTile(
                        leading: Icon(c.kind == 'retract' ? Icons.block : Icons.edit_calendar_outlined, color: p.amber),
                        title: Text(c.eventTitle),
                        subtitle: Text(
                          [
                            if (c.kind == 'retract') context.t('withdrawn'),
                            if (c.newValue?['date_start'] != null) '${c.newValue!['date_start']}',
                            if (c.oldValue?['date_start'] != null) context.t('was', {'old': c.oldValue!['date_start']}),
                            if (c.reason != null) c.reason!,
                            ago(context, c.createdAt),
                          ].join(' · '),
                        ),
                        onTap: c.sourceUrl == null ? null : () => openUrl(context, c.sourceUrl!),
                      ),
                  ],
                ),
      ),
      if (d.news.isNotEmpty && !ref.watch(settingsProvider).lowData) ...[
        SectionHeader(context.t('inTheNews')),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(context.t('newsUnverified'), style: TextStyle(color: p.muted)),
        ),
        for (final n in d.news)
          ListTile(
            title: Text(n.title, maxLines: 2, overflow: TextOverflow.ellipsis),
            subtitle: Text(n.publisher ?? Uri.parse(n.url).host),
            trailing: const Icon(Icons.open_in_new, size: 18),
            onTap: () => openUrl(context, n.url),
          ),
      ],
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 32),
        child: Text(d.disclaimer, style: TextStyle(color: p.muted, fontSize: 12.5)),
      ),
    ];
  }

  Widget _kv(BuildContext context, String k, String v) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Text(k, style: TextStyle(color: context.pal.muted))),
        const SizedBox(width: 12),
        Flexible(child: Text(v, textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600, fontFeatures: tabular))),
      ],
    ),
  );
}

class _Banner extends StatelessWidget {
  const _Banner(this.text, this.fg, this.bg);
  final String text;
  final Color fg, bg;
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(8), border: Border.all(color: fg.withValues(alpha: 0.4))),
    child: Text(text, style: TextStyle(color: fg, fontWeight: FontWeight.w600)),
  );
}

class _ApplyCard extends StatelessWidget {
  const _ApplyCard(this.a);
  final ApplyOut a;
  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          FilledButton.icon(
            onPressed: () => openUrl(context, a.url),
            icon: const Icon(Icons.open_in_new),
            label: Text(context.t('applyOfficial')),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Icon(Icons.lock_outline, size: 15, color: p.green),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  a.host,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(color: p.green, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          if (a.note != null)
            Padding(padding: const EdgeInsets.only(top: 4), child: Text(a.note!, style: TextStyle(color: p.muted, fontSize: 13))),
          if (a.copyText != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: OutlinedButton.icon(
                onPressed: () => copyText(context, a.copyText!),
                icon: const Icon(Icons.copy, size: 18),
                label: Text(context.t('copy', {'label': '${a.copyLabel ?? ''} ${a.copyText}'.trim()})),
              ),
            ),
        ],
      ),
    );
  }
}

class _EventRow extends StatefulWidget {
  const _EventRow(this.e, this.exam);
  final EventOut e;
  final ExamDetail exam;
  @override
  State<_EventRow> createState() => _EventRowState();
}

class _EventRowState extends State<_EventRow> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final e = widget.e;
    final retracted = e.status != 'active';
    final ev = e.evidence;
    return InkWell(
      onTap: ev == null ? null : () => setState(() => _open = !_open),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DateBlock(date: e.dateStart, precision: e.precision, tone: e.isDeadline ? p.amber : p.green),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        e.title + (e.categoryNumber != null ? ' · ${e.categoryNumber}' : ''),
                        style: TextStyle(fontWeight: FontWeight.w700, decoration: retracted ? TextDecoration.lineThrough : null),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        fmtDate(context, e.dateStart, precision: e.precision, end: e.dateEnd),
                        style: const TextStyle(fontFeatures: tabular),
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          if (retracted) Tag(context.t('withdrawn'), fg: p.red, bg: p.redSoft) else CertaintyTag(e.certainty),
                          if (!retracted && e.dateStart != null && daysUntil(e.dateStart!) >= 0 && e.isDeadline) DaysLeft(e.dateStart!),
                          if (e.revisionCount > 1) Tag(context.t('changeHistory'), fg: p.amber, bg: p.amberSoft, outlined: true),
                        ],
                      ),
                    ],
                  ),
                ),
                PopupMenuButton<String>(
                  icon: Icon(Icons.more_vert, color: p.muted),
                  onSelected: (v) {
                    if (v == 'cal' && e.dateStart != null) {
                      cal.Add2Calendar.addEvent2Cal(
                        cal.Event(
                          title: '${e.title}: ${widget.exam.title}',
                          description: '${widget.exam.officialUrl}\n${context.t('disclaimerShort')}',
                          startDate: e.dateStart!,
                          endDate: (e.dateEnd ?? e.dateStart!).add(const Duration(hours: 23)),
                          allDay: true,
                        ),
                      );
                    }
                  },
                  itemBuilder: (c) => [PopupMenuItem(value: 'cal', child: Text(context.t('addToCalendar')))],
                ),
              ],
            ),
            if (ev != null)
              Padding(
                padding: const EdgeInsets.only(left: 66, top: 4),
                child: Row(
                  children: [
                    Icon(_open ? Icons.expand_less : Icons.expand_more, size: 18, color: p.muted),
                    Text(context.t('source'), style: TextStyle(color: p.muted, fontSize: 13)),
                  ],
                ),
              ),
            if (_open && ev != null)
              Container(
                margin: const EdgeInsets.only(left: 66, top: 6),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: p.paper,
                  borderRadius: BorderRadius.circular(6),
                  border: Border(left: BorderSide(color: p.green, width: 3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${context.t('fromDocument')}${ev.page != null ? ', ${context.t('page', {'n': ev.page})}' : ''}',
                      style: TextStyle(color: p.muted, fontSize: 12),
                    ),
                    const SizedBox(height: 4),
                    Text('“${ev.quote.replaceAll(' | ', ' … ')}”', style: const TextStyle(fontStyle: FontStyle.italic)),
                    TextButton(onPressed: () => openUrl(context, ev.sourceUrl), child: Text(context.t('openSource'))),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _Eligibility extends ConsumerWidget {
  const _Eligibility(this.d);
  final ExamDetail d;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = context.pal;
    final profile = ref.watch(profileProvider).value;
    final res = profile == null ? null : ref.watch(eligibilityProvider(d.id));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(context.t('eligibility')),
        Card(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          child:
              profile == null
                  ? EmptyNote(
                    context.t('addDetailsToCheck'),
                    icon: Icons.person_outline,
                    action: context.t('addDetails'),
                    onAction: () => context.push('/profile'),
                  )
                  : res!.when(
                    loading: () => const Loading(),
                    error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(eligibilityProvider(d.id))),
                    data: (el) {
                      if (el == null) return EmptyNote(context.t('notChecked'));
                      return Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            for (final post in el.posts) ...[
                              Row(
                                children: [
                                  Icon(
                                    post.status == 'eligible'
                                        ? Icons.check_circle
                                        : (post.status == 'not_eligible' ? Icons.cancel : Icons.help),
                                    color: post.status == 'eligible' ? p.green : (post.status == 'not_eligible' ? p.red : p.amber),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      context.t('el_${post.status}'),
                                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
                                    ),
                                  ),
                                ],
                              ),
                              if (el.posts.length > 1) Text(post.postName, style: TextStyle(color: p.muted)),
                              const SizedBox(height: 8),
                              for (final r in post.results)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 10),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(r.requirement, style: const TextStyle(fontWeight: FontWeight.w600)),
                                      if (r.userValue != null) Text(r.userValue!, style: TextStyle(color: p.muted)),
                                      Text(
                                        r.explanation,
                                        style: TextStyle(color: r.outcome == 'pass' ? p.green : (r.outcome == 'fail' ? p.red : p.amber)),
                                      ),
                                      if (r.clause != null)
                                        Text(
                                          '“${r.clause!.length > 160 ? '${r.clause!.substring(0, 160)}…' : r.clause}”',
                                          style: TextStyle(color: p.muted, fontSize: 12, fontStyle: FontStyle.italic),
                                        ),
                                    ],
                                  ),
                                ),
                            ],
                            for (final c in el.countdown)
                              Container(
                                margin: const EdgeInsets.only(top: 4),
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(color: p.paper, borderRadius: BorderRadius.circular(6)),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(context.t('countdown'), style: const TextStyle(fontWeight: FontWeight.w700)),
                                    Text('${c['text']}'),
                                    Text('${c['basis']}', style: TextStyle(color: p.muted, fontSize: 12)),
                                  ],
                                ),
                              ),
                            const SizedBox(height: 6),
                            Text(context.t('eligibilityBasis'), style: TextStyle(color: p.muted, fontSize: 12)),
                          ],
                        ),
                      );
                    },
                  ),
        ),
      ],
    );
  }
}

class _Checklist extends ConsumerStatefulWidget {
  const _Checklist(this.d);
  final ExamDetail d;
  @override
  ConsumerState<_Checklist> createState() => _ChecklistState();
}

class _ChecklistState extends ConsumerState<_Checklist> {
  Set<String> _done = {};

  @override
  void initState() {
    super.initState();
    ref.read(dbProvider).checked(widget.d.id).then((v) => mounted ? setState(() => _done = v) : null);
  }

  @override
  Widget build(BuildContext context) {
    final res = ref.watch(checklistProvider(widget.d.id));
    return res.maybeWhen(
      orElse: () => const SizedBox.shrink(),
      data:
          (f) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionHeader(context.t('checklist')),
              Card(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(
                  children: [
                    for (final it in f.data.items)
                      CheckboxListTile(
                        value: _done.contains(it.key),
                        onChanged: (v) async {
                          await ref.read(dbProvider).setChecked(widget.d.id, it.key, v ?? false);
                          setState(() => v == true ? _done.add(it.key) : _done.remove(it.key));
                        },
                        title: Text(it.text),
                        subtitle: it.due == null ? null : Text(fmtDate(context, it.due)),
                        controlAffinity: ListTileControlAffinity.leading,
                      ),
                    for (final rule in f.data.certificateRules) _CertificateRuleTile(rule, widget.d),
                    if (f.data.photoSpecs.isNotEmpty)
                      ListTile(
                        leading: const Icon(Icons.photo_size_select_actual_outlined),
                        title: Text(context.t('photoCheck')),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => context.push('/tools/photo?exam=${widget.d.id}'),
                      ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                      child: Text(f.data.note, style: TextStyle(color: context.pal.muted, fontSize: 12.5)),
                    ),
                  ],
                ),
              ),
            ],
          ),
    );
  }
}

/// A certificate validity rule from the notice. The check runs on the phone; the certificate never leaves it.
class _CertificateRuleTile extends StatelessWidget {
  const _CertificateRuleTile(this.rule, this.exam);
  final CertificateRuleOut rule;
  final ExamDetail exam;

  Future<void> _check(BuildContext context) async {
    final p = context.pal;
    if (rule.issuedFrom == null && rule.issuedUntil == null) {
      await showDialog<void>(
        context: context,
        builder:
            (c) => AlertDialog(
              content: Text('${rule.text}\n\n${context.t('certFyOnly')}'),
              actions: [TextButton(onPressed: () => Navigator.pop(c), child: Text(context.t('ok')))],
            ),
      );
      return;
    }
    final picked = await showDatePicker(
      context: context,
      helpText: context.t('certIssued'),
      initialDate: today(),
      firstDate: DateTime(2015),
      lastDate: today(),
    );
    if (picked == null || !context.mounted) return;
    final tooOld = rule.issuedFrom != null && picked.isBefore(rule.issuedFrom!);
    final tooNew = rule.issuedUntil != null && picked.isAfter(rule.issuedUntil!);
    var message = tooOld ? context.t('certTooOld') : (tooNew ? context.t('certTooNew') : context.t('certOk'));
    if (tooOld && rule.issuedUntil != null) {
      final remind = rule.issuedUntil!.subtract(const Duration(days: 7));
      final set = await AlertService.instance.remindOn(
        remind.isBefore(today()) ? today().add(const Duration(days: 1)) : remind,
        '${rule.certificate}: ${context.t('certRenew')}',
        exam.title,
        'examradar://exam/${exam.id}',
      );
      if (set && context.mounted) message += '\n\n${context.t('certReminderSet', {'date': fmtDate(context, remind)})}';
    }
    if (!context.mounted) return;
    await showDialog<void>(
      context: context,
      builder:
          (c) => AlertDialog(
            icon: Icon(tooOld || tooNew ? Icons.error_outline : Icons.check_circle_outline, color: tooOld || tooNew ? p.red : p.green),
            content: Text(message),
            actions: [TextButton(onPressed: () => Navigator.pop(c), child: Text(context.t('ok')))],
          ),
    );
  }

  @override
  Widget build(BuildContext context) => ListTile(
    leading: const Icon(Icons.verified_outlined),
    title: Text(rule.text),
    subtitle:
        rule.evidence == null
            ? null
            : Text(
              '“${rule.evidence!.quote}”',
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontStyle: FontStyle.italic),
            ),
    trailing: TextButton(onPressed: () => _check(context), child: Text(context.t('certCheck'))),
    isThreeLine: rule.evidence != null,
  );
}
