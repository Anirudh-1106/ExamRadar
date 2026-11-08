import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'config.dart';
import 'data/state.dart';
import 'l10n/strings.dart';
import 'screens/alerts.dart';
import 'screens/calendar.dart';
import 'screens/exam_detail.dart';
import 'screens/exams.dart';
import 'screens/home.dart';
import 'screens/info.dart';
import 'screens/more.dart';
import 'screens/my_exams.dart';
import 'screens/onboarding.dart';
import 'screens/profile.dart';
import 'screens/scam.dart';
import 'screens/tools.dart';
import 'theme.dart';

/// Maps examradar://exam/12?tab=changes (from notifications or shared links) to an in-app path.
String deepLinkToPath(String link) {
  final u = Uri.parse(link);
  if (u.scheme == AppConfig.deepLinkScheme) {
    final path = '/${u.host}${u.path}';
    final mapped = path.startsWith('/notice') ? '/notices' : path;
    return u.hasQuery ? '$mapped?${u.query}' : mapped;
  }
  return u.path.isEmpty ? '/home' : (u.hasQuery ? '${u.path}?${u.query}' : u.path);
}

GoRouter buildRouter(Ref ref, {String? initial}) {
  final shell = StatefulShellRoute.indexedStack(
    builder: (c, s, nav) => _Shell(nav: nav),
    branches: [
      StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (c, s) => const HomeScreen())]),
      StatefulShellBranch(routes: [GoRoute(path: '/exams', builder: (c, s) => const ExamsScreen())]),
      StatefulShellBranch(routes: [GoRoute(path: '/calendar', builder: (c, s) => const CalendarScreen())]),
      StatefulShellBranch(routes: [GoRoute(path: '/my', builder: (c, s) => const MyExamsScreen())]),
      StatefulShellBranch(routes: [GoRoute(path: '/more', builder: (c, s) => const MoreScreen())]),
    ],
  );
  return GoRouter(
    initialLocation: initial != null ? deepLinkToPath(initial) : '/home',
    redirect: (c, s) {
      if (s.uri.scheme == AppConfig.deepLinkScheme) return deepLinkToPath(s.uri.toString());
      if (!ref.read(settingsProvider).onboarded && s.matchedLocation != '/onboarding') return '/onboarding';
      return null;
    },
    routes: [
      shell,
      GoRoute(path: '/onboarding', builder: (c, s) => const OnboardingScreen()),
      GoRoute(
        path: '/exam/:id',
        builder: (c, s) => ExamDetailScreen(id: int.parse(s.pathParameters['id']!), tab: s.uri.queryParameters['tab']),
      ),
      GoRoute(path: '/alerts', builder: (c, s) => const AlertsScreen()),
      GoRoute(path: '/alerts/settings', builder: (c, s) => const AlertSettingsScreen()),
      GoRoute(path: '/scam', builder: (c, s) => const ScamScreen()),
      GoRoute(path: '/profile', builder: (c, s) => const ProfileScreen()),
      GoRoute(path: '/settings', builder: (c, s) => const SettingsScreen()),
      GoRoute(path: '/sources', builder: (c, s) => const SourcesScreen()),
      GoRoute(path: '/about', builder: (c, s) => const AboutScreen()),
      GoRoute(path: '/privacy', builder: (c, s) => const PrivacyScreen()),
      GoRoute(path: '/news', builder: (c, s) => const NewsScreen()),
      GoRoute(path: '/notices', builder: (c, s) => const NoticesScreen()),
      GoRoute(path: '/tools/age', builder: (c, s) => const AgeCalcScreen()),
      GoRoute(path: '/tools/names', builder: (c, s) => const NameCheckScreen()),
      GoRoute(path: '/tools/photo', builder: (c, s) => PhotoCheckScreen(examId: int.tryParse(s.uri.queryParameters['exam'] ?? ''))),
    ],
  );
}

class _Shell extends StatelessWidget {
  const _Shell({required this.nav});
  final StatefulNavigationShell nav;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: nav,
    bottomNavigationBar: NavigationBar(
      selectedIndex: nav.currentIndex,
      onDestinationSelected: (i) => nav.goBranch(i, initialLocation: i == nav.currentIndex),
      destinations: [
        NavigationDestination(icon: const Icon(Icons.home_outlined), selectedIcon: const Icon(Icons.home), label: context.t('navHome')),
        NavigationDestination(icon: const Icon(Icons.search), label: context.t('navExams')),
        NavigationDestination(
          icon: const Icon(Icons.calendar_month_outlined),
          selectedIcon: const Icon(Icons.calendar_month),
          label: context.t('navCalendar'),
        ),
        NavigationDestination(
          icon: const Icon(Icons.bookmark_border),
          selectedIcon: const Icon(Icons.bookmark),
          label: context.t('navMyExams'),
        ),
        NavigationDestination(icon: const Icon(Icons.menu), label: context.t('navMore')),
      ],
    ),
  );
}

final routerProvider = Provider<GoRouter>((ref) => throw UnimplementedError('overridden in main'));

class ExamRadarApp extends ConsumerWidget {
  const ExamRadarApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(settingsProvider);
    return LangScope(
      lang: s.lang,
      child: MaterialApp.router(
        title: AppConfig.appName,
        debugShowCheckedModeBanner: false,
        theme: buildTheme(Brightness.light),
        darkTheme: buildTheme(Brightness.dark),
        routerConfig: ref.watch(routerProvider),
        locale: Locale(s.lang == 'ml' ? 'ml' : 'en', 'IN'),
        supportedLocales: const [Locale('en', 'IN'), Locale('ml', 'IN')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        builder: (c, child) {
          final mq = MediaQuery.of(c);
          // Large text mode scales on top of the phone's own setting, capped to keep layouts usable.
          final scale = (mq.textScaler.scale(1) * (s.largeText ? 1.2 : 1.0)).clamp(0.9, 1.8);
          return LangScope(lang: s.lang, child: MediaQuery(data: mq.copyWith(textScaler: TextScaler.linear(scale)), child: child!));
        },
      ),
    );
  }
}
