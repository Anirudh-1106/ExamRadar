import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../config.dart';
import '../data/state.dart';
import '../l10n/strings.dart';
import '../services/notifications.dart';
import '../theme.dart';

/// One screen, no account. Asks only which exam groups interest the user and offers reminders.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});
  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingState();
}

class _OnboardingState extends ConsumerState<OnboardingScreen> {
  final _groups = {'central', 'kerala'};

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final s = ref.watch(settingsProvider);
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 32, 20, 20),
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: SegmentedButton<String>(
                segments: const [ButtonSegment(value: 'en', label: Text('English')), ButtonSegment(value: 'ml', label: Text('മലയാളം'))],
                selected: {s.lang},
                showSelectedIcon: false,
                onSelectionChanged: (v) => ref.read(settingsProvider.notifier).update(s.copyWith(lang: v.first)),
              ),
            ),
            const SizedBox(height: 28),
            Text(AppConfig.appName, style: TextStyle(color: p.green, fontWeight: FontWeight.w800, letterSpacing: 0.5)),
            const SizedBox(height: 8),
            Text(context.t('onTitle'), style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 14),
            Text(context.t('onBody1'), style: const TextStyle(fontSize: 16)),
            const SizedBox(height: 10),
            Text(context.t('onBody2'), style: TextStyle(fontSize: 16, color: p.muted)),
            const SizedBox(height: 28),
            Text(context.t('onGroups'), style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            for (final g in const ['central', 'kerala'])
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: _groups.contains(g),
                title: Text(context.t(g), style: const TextStyle(fontSize: 17)),
                onChanged: (v) => setState(() => v == true ? _groups.add(g) : (_groups.length > 1 ? _groups.remove(g) : null)),
              ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: p.paper, border: Border.all(color: p.line), borderRadius: BorderRadius.circular(8)),
              child: Text(context.t('disclaimerFull'), style: TextStyle(color: p.muted, fontSize: 13)),
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: () async {
                await AlertService.instance.requestPermission();
                await ref.read(settingsProvider.notifier).update(s.copyWith(onboarded: true, groups: _groups.toList()));
                if (context.mounted) context.go('/home');
              },
              child: Text(context.t('start')),
            ),
            const SizedBox(height: 8),
            Text(context.t('remindersHelp'), textAlign: TextAlign.center, style: TextStyle(color: p.muted, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
