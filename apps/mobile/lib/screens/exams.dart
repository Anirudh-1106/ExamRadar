import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/state.dart';
import '../l10n/strings.dart';
import '../widgets/common.dart';

/// Search and filters for Central or Kerala, status, and "only ones I can apply for".
class ExamsScreen extends ConsumerStatefulWidget {
  const ExamsScreen({super.key});
  @override
  ConsumerState<ExamsScreen> createState() => _ExamsScreenState();
}

class _ExamsScreenState extends ConsumerState<ExamsScreen> {
  final _search = TextEditingController();
  Timer? _debounce;
  String? _q, _group, _status;
  bool _onlyEligible = false;

  static const _statuses = ['open', 'upcoming', 'exam_scheduled', 'result'];

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final query = (q: _q, group: _group, status: _status, sort: 'deadline');
    final res = ref.watch(examsProvider(query));
    final hasProfile = ref.watch(profileProvider).value != null;
    return Scaffold(
      appBar: AppBar(title: Text(context.t('navExams'))),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              controller: _search,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(prefixIcon: const Icon(Icons.search), hintText: context.t('searchHint')),
              onChanged: (v) {
                _debounce?.cancel();
                _debounce = Timer(const Duration(milliseconds: 450), () => setState(() => _q = v));
              },
            ),
          ),
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                for (final g in [null, 'central', 'kerala'])
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: ChoiceChip(
                      label: Text(context.t(g ?? 'all')),
                      selected: _group == g,
                      onSelected: (_) => setState(() => _group = g),
                    ),
                  ),
                const VerticalDivider(width: 16, indent: 8, endIndent: 8),
                for (final s in _statuses)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: FilterChip(
                      label: Text(context.t('st_$s')),
                      selected: _status == s,
                      onSelected: (on) => setState(() => _status = on ? s : null),
                    ),
                  ),
              ],
            ),
          ),
          if (hasProfile)
            SwitchListTile(
              dense: true,
              title: Text(context.t('onlyEligible')),
              value: _onlyEligible,
              onChanged: (v) => setState(() => _onlyEligible = v),
            ),
          const Divider(),
          Expanded(
            child: res.when(
              loading: () => const Loading(),
              error: (e, _) => ErrorNote(error: e, onRetry: () => ref.invalidate(examsProvider(query))),
              data: (f) {
                var items = f.data.items;
                if (_onlyEligible && hasProfile) {
                  final ok = ref.watch(eligibleIdsProvider(items.map((e) => e.id).toList()));
                  items = ok.when(
                    data: (s) => items.where((e) => s.contains(e.id)).toList(),
                    loading: () => items,
                    error: (_, __) => items,
                  );
                }
                if (items.isEmpty) return ListView(children: [StaleBanner(f), EmptyNote(context.t('noResults'), icon: Icons.search_off)]);
                return RefreshIndicator(
                  onRefresh: () => ref.refresh(examsProvider(query).future),
                  child: ListView.separated(
                    itemCount: items.length + 1,
                    separatorBuilder: (_, __) => const Divider(),
                    itemBuilder:
                        (c, i) => i == 0 ? StaleBanner(f) : ExamTile(items[i - 1], onTap: () => context.push('/exam/${items[i - 1].id}')),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
