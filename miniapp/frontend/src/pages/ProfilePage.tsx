import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Copy, Check, Trophy, ChevronRight, Flame, Wallet as WalletIcon } from 'lucide-react';
import { api } from '../api/client';
import type { Me } from '../types/app';
import { useLoad } from '../hooks/useLoad';
import { Chip, Empty, ErrorBox, Loader, PageTitle, Section, fmtDate, fmtLev, haptic } from '../components/ui';

const mockMe: Me = {
  user_id: 1,
  nick: 'Nikita',
  username: 'Nikita_Kovalevsk',
  balance: 955,
  stats: {
    matches: 24, wins: 15, losses: 9, win_rate: 63,
    lev_won: 820, lev_lost: 410, lev_net: 410, best_win: 150,
    win_streak: 3, best_win_streak: 5,
  },
  tournament: { rank: 4, wins: 15, losses: 9, points: 45, total: 87 },
  requisites: {
    deposit: { ton: null, trc20: null },
    withdraw: { ton: null, trc20: 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', cryptobot: 'tg_id 1350766902 (@Nikita_Kovalevsk)' },
  },
  recent_matches: [
    { match_id: '1', opponent_name: 'Alex', opponent_id: 2, player_score: 3, opponent_score: 2, result: 'win', delta_lev: 50, played_at: Date.now() / 1000 - 3600 },
    { match_id: '2', opponent_name: 'Max', opponent_id: 3, player_score: 1, opponent_score: 2, result: 'loss', delta_lev: -25, played_at: Date.now() / 1000 - 86400 },
  ],
  total_matches: 24,
};

function initials(name: string) {
  return name.replace('@', '').slice(0, 2).toUpperCase();
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: 'gold' | 'ok' | 'bad' }) {
  const color =
    accent === 'gold' ? 'gold-text' : accent === 'ok' ? 'text-emerald-300' : accent === 'bad' ? 'text-rose-300' : 'text-[#f4f1ea]';
  return (
    <div className="card px-3 py-3">
      <div className={`tabular text-xl font-bold ${color}`}>{value}</div>
      <div className="mt-0.5 text-[11px] text-ink-400">{label}</div>
    </div>
  );
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const { data: me, error, loading, reload } = useLoad(api.me, mockMe);
  const [copied, setCopied] = useState<string | null>(null);

  if (loading) return <Loader />;
  if (error || !me) return <div className="p-4"><ErrorBox message={error || ''} onRetry={reload} /></div>;

  const s = me.stats;
  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      haptic();
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* буфер недоступен */
    }
  };

  return (
    <div className="page-transition p-4">
      <PageTitle icon={<User size={22} />} title="Профиль" />

      {/* Карточка игрока */}
      <div className="card-gold mb-5 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-b from-gold-300 to-gold-600 text-lg font-extrabold text-ink-950 shadow-[0_0_24px_rgba(212,169,55,0.35)]">
            {initials(me.nick)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-lg font-bold">{me.nick}</div>
            {me.username && <div className="truncate text-xs text-ink-400">@{me.username}</div>}
          </div>
          {me.tournament?.rank && (
            <button onClick={() => navigate('/tournaments')} className="shrink-0">
              <Chip tone="wait">
                <Trophy size={12} /> #{me.tournament.rank}
              </Chip>
            </button>
          )}
        </div>
        <div className="mt-4 flex items-end justify-between">
          <div>
            <div className="label">Баланс</div>
            <div className="tabular mt-1 text-3xl font-extrabold">
              <span className="gold-text">{fmtLev(me.balance)}</span>
              <span className="ml-1.5 text-base font-semibold text-gold-400">Lev</span>
            </div>
          </div>
          <button onClick={() => navigate('/wallet')} className="btn-ghost px-3 py-2 text-xs">
            <WalletIcon size={14} /> Кошелёк
          </button>
        </div>
      </div>

      {/* Матчи */}
      <Section title="Матчи">
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Сыграно" value={String(s.matches)} />
          <Stat label="Победы" value={String(s.wins)} accent="ok" />
          <Stat label="Поражения" value={String(s.losses)} accent="bad" />
        </div>
        <div className="card mt-2 px-4 py-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-ink-300">Процент побед</span>
            <span className="tabular font-bold text-gold-300">{s.win_rate}%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-gradient-to-r from-gold-600 to-gold-300"
              style={{ width: `${Math.min(100, s.win_rate)}%` }}
            />
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-ink-400">
            <span className="flex items-center gap-1"><Flame size={13} className="text-gold-400" /> Серия побед: <b className="text-[#f4f1ea]">{s.win_streak}</b></span>
            <span>Лучшая: <b className="text-[#f4f1ea]">{s.best_win_streak}</b></span>
          </div>
        </div>
      </Section>

      {/* Lev */}
      <Section title="Lev в матчах">
        <div className="grid grid-cols-2 gap-2">
          <Stat label="Выиграно" value={fmtLev(s.lev_won, true)} accent="ok" />
          <Stat label="Проиграно" value={fmtLev(-s.lev_lost, true)} accent="bad" />
          <Stat label="Итог" value={fmtLev(s.lev_net, true)} accent="gold" />
          <Stat label="Крупнейший выигрыш" value={fmtLev(s.best_win)} />
        </div>
      </Section>

      {/* Турнир */}
      <Section title="Турнир">
        <button onClick={() => navigate('/tournaments')} className="card flex w-full items-center gap-3 px-4 py-3 text-left">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gold-500/10 text-gold-400">
            <Trophy size={20} />
          </div>
          <div className="flex-1">
            {me.tournament ? (
              <>
                <div className="font-semibold">
                  Место #{me.tournament.rank ?? '—'} <span className="text-ink-400">из {me.tournament.total}</span>
                </div>
                <div className="text-xs text-ink-400">
                  {me.tournament.wins} побед · {me.tournament.points} очков
                </div>
              </>
            ) : (
              <>
                <div className="font-semibold">Ты ещё не в таблице</div>
                <div className="text-xs text-ink-400">Побеждай в матчах на Lev, чтобы попасть в турнир</div>
              </>
            )}
          </div>
          <ChevronRight size={18} className="text-ink-400" />
        </button>
      </Section>

      {/* Реквизиты */}
      <Section
        title="Реквизиты для вывода"
        right={<button onClick={() => navigate('/requisites?tab=withdraw')} className="text-xs font-semibold text-gold-400">Изменить →</button>}
      >
        <div className="card divide-y divide-white/[0.05]">
          {(
            [
              ['ton', '💎', 'TON'],
              ['trc20', '💵', 'USDT TRC20'],
              ['cryptobot', '🤖', 'CryptoBot'],
            ] as const
          ).map(([key, icon, name]) => {
            const v = me.requisites.withdraw[key];
            return (
              <div key={key} className="flex items-center gap-3 px-4 py-3">
                <span className="text-base">{icon}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-ink-400">{name}</div>
                  <div className={`truncate font-mono text-[12px] ${v ? 'text-[#f4f1ea]' : 'text-ink-600'}`}>{v || 'не указан'}</div>
                </div>
                {v && (
                  <button onClick={() => copy(v)} className="shrink-0 rounded-lg p-2 text-gold-400 active:bg-white/5" aria-label="Скопировать">
                    {copied === v ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </Section>

      {/* Последние матчи */}
      <Section title="Последние матчи" right={<span className="text-xs text-ink-400">{me.total_matches}</span>}>
        {me.recent_matches.length ? (
          <div className="card divide-y divide-white/[0.05]">
            {me.recent_matches.map((m, i) => {
              const win = m.result === 'win';
              const delta = m.delta_lev ?? 0;
              return (
                <div key={m.match_id || i} className="flex items-center gap-3 px-4 py-3">
                  <Chip tone={win ? 'ok' : m.result === 'loss' ? 'bad' : 'muted'}>
                    {win ? 'Победа' : m.result === 'loss' ? 'Поражение' : 'Ничья'}
                  </Chip>
                  <button
                    className="min-w-0 flex-1 text-left"
                    onClick={() => m.opponent_id && navigate(`/player/${m.opponent_id}`)}
                  >
                    <div className="truncate text-sm font-medium">{m.opponent_name || 'Соперник'}</div>
                    <div className="text-[11px] text-ink-400">
                      Попадания {m.player_score}:{m.opponent_score} · {fmtDate(m.played_at)}
                    </div>
                  </button>
                  <div className={`tabular text-sm font-bold ${delta > 0 ? 'text-emerald-300' : delta < 0 ? 'text-rose-300' : 'text-ink-400'}`}>
                    {fmtLev(delta, true)}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <Empty emoji="🏀" text="Матчей пока нет. Сыграй первый матч в боте!" />
        )}
      </Section>
    </div>
  );
}
