import type { MatchResult } from '../types';

function formatDate(timestamp?: number): string {
  if (!timestamp) return '';
  return new Date(timestamp * 1000).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const resultLabel: Record<MatchResult['result'], string> = {
  win: 'Победа',
  loss: 'Поражение',
  draw: 'Ничья',
};

export default function MatchCard({ match }: { match: MatchResult }) {
  const tone =
    match.result === 'win'
      ? 'text-green-600 bg-green-50'
      : match.result === 'loss'
        ? 'text-red-600 bg-red-50'
        : 'text-gray-600 bg-gray-50';

  const delta = match.delta_lev ?? 0;
  const currency = match.currency === 'stars' ? '⭐' : 'Lev';

  return (
    <div className="bg-white rounded-xl p-4 border border-gray-100 flex items-center gap-3">
      <div className={`px-2 py-1 rounded-lg text-xs font-semibold ${tone}`}>
        {resultLabel[match.result]}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-gray-900 truncate">
          vs {match.opponent_name || 'Соперник'}
        </div>
        <div className="text-xs text-gray-400">
          {match.mode || 'Матч'}
          {match.played_at ? ` · ${formatDate(match.played_at)}` : ''}
        </div>
      </div>
      <div className="text-right">
        <div className="font-semibold text-gray-900">
          {match.player_score}:{match.opponent_score}
        </div>
        <div
          className={`text-xs ${
            delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-gray-400'
          }`}
        >
          {delta > 0 ? '+' : ''}
          {delta} {currency}
        </div>
      </div>
    </div>
  );
}
