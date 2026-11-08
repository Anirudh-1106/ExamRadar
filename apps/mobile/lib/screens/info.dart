import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../config.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';

class SourcesScreen extends ConsumerWidget {
  const SourcesScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = context.pal;
    final res = ref.watch(sourcesProvider);
    return Scaffold(
      appBar: AppBar(title: Text(context.t('sources'))),
      body: res.when(
        loading: () => const Loading(),
        error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(sourcesProvider)),
        data: (f) {
          final official = f.data.where((s) => s.isOfficial).toList();
          final news = f.data.where((s) => !s.isOfficial && s.status != 'disabled').toList();
          Widget row(s) {
            final (fg, bg) = switch (s.status) {
              'ok' => (p.green, p.greenSoft),
              'blocked' || 'failing' || 'robots' => (p.red, p.redSoft),
              'stale' => (p.amber, p.amberSoft),
              _ => (p.muted, p.paper),
            };
            return ListTile(
              title: Text(s.organisation ?? Uri.parse(s.url).host),
              subtitle: Text(
                [
                  Uri.tryParse(s.url)?.host ?? s.url,
                  s.lastSuccessAt != null ? context.t('checked', {'time': ago(context, s.lastSuccessAt!)}) : context.t('notChecked'),
                  if (s.note != null) s.note!,
                ].join('\n'),
              ),
              isThreeLine: true,
              trailing: Tag(s.status, fg: fg, bg: bg),
            );
          }

          return ListView(
            children: [
              StaleBanner(f),
              Padding(padding: const EdgeInsets.all(16), child: Text(context.t('sourcesIntro'))),
              for (final s in official) row(s),
              if (news.isNotEmpty) SectionHeader(context.t('news')),
              for (final s in news) row(s),
            ],
          );
        },
      ),
    );
  }
}

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    return Scaffold(
      appBar: AppBar(title: Text(context.t('about'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(AppConfig.appName, style: Theme.of(context).textTheme.headlineSmall),
          Text(context.t('version', {'v': AppConfig.version}), style: TextStyle(color: p.muted)),
          const SizedBox(height: 12),
          Text(context.t('aboutText')),
          SectionHeader(context.t('disclaimerTitle')),
          Text(context.t('disclaimerFull')),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: () => context.push('/privacy'),
            icon: const Icon(Icons.privacy_tip_outlined),
            label: Text(context.t('privacy')),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () => context.push('/sources'),
            icon: const Icon(Icons.sensors_outlined),
            label: Text(context.t('sources')),
          ),
        ],
      ),
    );
  }
}

class PrivacyScreen extends ConsumerWidget {
  const PrivacyScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final base = ref.watch(settingsProvider).apiBase;
    return Scaffold(
      appBar: AppBar(title: Text(context.t('privacy'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const _P(
            'What we collect',
            'Nothing until you use a feature. The app works without an account. To save exams across reinstalls and send alerts, '
                'the phone gets an anonymous token. If you add your details, they stay on this phone. They go to our server only if you turn on '
                '"matching alerts", and only for eligibility checks and alerts.',
          ),
          const _P(
            'What we never collect',
            'Portal passwords, Aadhaar numbers, payment details, photos or identity documents. Photo and name checks run on '
                'the phone only.',
          ),
          const _P('Scam Check', 'Text you paste is deleted from our server within 24 hours. We keep only the result.'),
          const _P('Your rights', 'Settings lets you download everything we hold and delete it all, on the phone and on our server.'),
          const _P('Children', 'This app is for adults (18+).'),
          TextButton(onPressed: () => openUrl(context, '$base/privacy'), child: const Text('Full privacy policy')),
        ],
      ),
    );
  }
}

class _P extends StatelessWidget {
  const _P(this.h, this.b);
  final String h, b;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [Text(h, style: const TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 4), Text(b)],
    ),
  );
}

class NewsScreen extends ConsumerWidget {
  const NewsScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = context.pal;
    final res = ref.watch(newsProvider);
    return Scaffold(
      appBar: AppBar(title: Text(context.t('news'))),
      body: res.when(
        loading: () => const Loading(),
        error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(newsProvider)),
        data:
            (f) => ListView(
              children: [
                StaleBanner(f),
                Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: p.amberSoft, borderRadius: BorderRadius.circular(8)),
                  child: Text(context.t('newsUnverified'), style: TextStyle(color: p.amber, fontWeight: FontWeight.w600)),
                ),
                if (f.data.isEmpty) EmptyNote(context.t('inboxEmpty')),
                for (final n in f.data) ...[
                  ListTile(
                    title: Text(n.title),
                    subtitle: Text(
                      [n.publisher ?? Uri.parse(n.url).host, if (n.publishedAt != null) ago(context, n.publishedAt!)].join(' · '),
                    ),
                    trailing: const Icon(Icons.open_in_new, size: 18),
                    onTap: () => openUrl(context, n.url),
                  ),
                  const Divider(),
                ],
              ],
            ),
      ),
    );
  }
}

class NoticesScreen extends ConsumerWidget {
  const NoticesScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = context.pal;
    final res = ref.watch(noticesProvider);
    return Scaffold(
      appBar: AppBar(title: Text(context.t('newNotices'))),
      body: res.when(
        loading: () => const Loading(),
        error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(noticesProvider)),
        data:
            (f) => ListView(
              children: [
                StaleBanner(f),
                for (final n in f.data.items) ...[
                  ListTile(
                    leading: Icon(Icons.campaign_outlined, color: p.green),
                    title: Text(n.title),
                    subtitle: Text('${n.organisation.name} · ${ago(context, n.firstSeenAt)}'),
                    onTap: () => n.examId != null ? context.push('/exam/${n.examId}') : (n.url != null ? openUrl(context, n.url!) : null),
                  ),
                  const Divider(),
                ],
              ],
            ),
      ),
    );
  }
}
