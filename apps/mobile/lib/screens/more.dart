import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../l10n/strings.dart';
import '../theme.dart';
import '../widgets/common.dart';

class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    Widget tile(IconData i, String key, String path) =>
        ListTile(leading: Icon(i), title: Text(context.t(key)), trailing: const Icon(Icons.chevron_right), onTap: () => context.push(path));
    return Scaffold(
      appBar: AppBar(title: Text(context.t('more'))),
      body: ListView(
        children: [
          tile(Icons.verified_user_outlined, 'scam', '/scam'),
          tile(Icons.notifications_none, 'alerts', '/alerts'),
          tile(Icons.person_outline, 'profile', '/profile'),
          tile(Icons.campaign_outlined, 'newNotices', '/notices'),
          tile(Icons.newspaper_outlined, 'news', '/news'),
          SectionHeader(context.t('tools')),
          tile(Icons.cake_outlined, 'ageCalc', '/tools/age'),
          tile(Icons.badge_outlined, 'nameCheck', '/tools/names'),
          tile(Icons.photo_size_select_actual_outlined, 'photoCheck', '/tools/photo'),
          SectionHeader(context.t('help')),
          tile(Icons.settings_outlined, 'settings', '/settings'),
          tile(Icons.sensors_outlined, 'sources', '/sources'),
          tile(Icons.info_outline, 'about', '/about'),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(context.t('disclaimerShort'), style: TextStyle(color: context.pal.muted, fontSize: 12.5)),
          ),
        ],
      ),
    );
  }
}
