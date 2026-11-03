import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Wallet as WalletIcon, ArrowDownLeft, ArrowUpRight, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import type { Deposit, Wallet, Withdrawal } from '../types/app';
import { useLoad } from '../hooks/useLoad';
import { Chip, Empty, ErrorBox, Loader, PageTitle, fmtDate, fmtLev, haptic } from '../components/ui';

type Tab = 'deposits' | 'withdrawals';

const now = Date.now() / 1000;
const mockWallet: Wallet = {
  balance: 955,
  pending_withdraw_lev: 200,
  requisites: {
    deposit: { ton: null, trc20: null },
    withdraw: { ton: null, trc20: 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', cryptobot: null },
  },
  deposits: [
    { id: 'p2', method: 'usdt', amount: '5 USDT', lev: 500, status: 'paid', details: 'CryptoBot · счёт #777', created_at: now - 3600 },
    { id: 'i3', method: 'ton', amount: '0.5 TON', lev: 150, status: 'active', details: 'CryptoBot · счёт #778', created_at: now - 600 },
    { id: 'p1', method: 'stars', amount: '5 ⭐', lev: 50, status: 'paid', details: 'Telegram Stars', created_at: now - 86400 },
  ],
  withdrawals: [
    { id: 3, lev: 200, method: 'trc20', asset: 'USDT', amount: '2.00 USDT', destination: 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', status: 'pending', queue_position: 2, reject_reason: null, created_at: now - 300, processed_at: null },
    { id: 2, lev: 300, method: 'cryptobot', asset: 'USDT', amount: '3.00 USDT', destination: '@CryptoBot', status: 'paid', queue_position: null, reject_reason: null, created_at: now - 7200, processed_at: now - 7000 },
    { id: 1, lev: 300, method: 'ton', asset: 'TON', amount: '1.000 TON', destination: 'UQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', status: 'rejected', queue_position: null, reject_reason: 'Отклонено админом', created_at: now - 90000, processed_at: now - 80000 },
  ],
};

const METHOD_ICON: Record<string, string> = { stars: '⭐', usdt: '💵', ton: '💎', rub: '💳', cryptobot: '🤖', trc20: '💵' };
const WD_METHOD: Record<string, string> = { cryptobot: 'CryptoBot', trc20: 'USDT · TRC20', ton: 'Кошелёк TON' };

function depositStatus(d: Deposit) {
  if (d.status === 'paid') return <Chip tone="ok">Зачислено</Chip>;
  if (d.status === 'active') return <Chip tone="wait">Ожидает оплаты</Chip>;
  if (d.status === 'expired') return <Chip tone="muted">Счёт истёк</Chip>;
  return <Chip tone="muted">{d.status}</Chip>;
}

function withdrawalStatus(w: Withdrawal) {
  if (w.status === 'paid') return <Chip tone="ok">Выполнено</Chip>;
  if (w.status === 'processing') return <Chip tone="info">Отправляется</Chip>;
  if (w.status === 'pending') return <Chip tone="wait">Ожидает{w.queue_position ? ` · №${w.queue_position} в очереди` : ''}</Chip>;
  if (w.status === 'rejected') return <Chip tone="bad">Отклонено</Chip>;
  return <Chip tone="muted">{w.status}</Chip>;
}

function shortAddr(a?: string | null) {
  if (!a) return '—';
  return a.length > 20 ? `${a.slice(0, 8)}…${a.slice(-6)}` : a;
}

function DepositRow({ d }: { d: Deposit }) {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-400/10 text-base">
        {METHOD_ICON[d.method] || '➕'}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <div className="truncate text-sm font-semibold">{d.amount}</div>
          <div className="tabular shrink-0 text-sm font-bold text-emerald-300">+{fmtLev(d.lev)} Lev</div>
        </div>
        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="truncate text-[11px] text-ink-400">
            {d.details} · {fmtDate(d.created_at)}
          </div>
          {depositStatus(d)}
        </div>
      </div>
    </div>
  );
}

function WithdrawalRow({ w }: { w: Withdrawal }) {
  const [open, setOpen] = useState(false);
  return (
    <button className="block w-full px-4 py-3 text-left" onClick={() => { setOpen(!open); haptic(); }}>
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gold-500/10 text-base">
          {METHOD_ICON[w.method] || '↗️'}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="truncate text-sm font-semibold">{w.amount || `${w.lev} Lev`}</div>
            <div className="tabular shrink-0 text-sm font-bold text-[#f4f1ea]">−{fmtLev(w.lev)} Lev</div>
          </div>
          <div className="mt-1 flex items-center justify-between gap-2">
            <div className="truncate text-[11px] text-ink-400">
              #{w.id} · {WD_METHOD[w.method] || 'Вывод'} · {fmtDate(w.created_at)}
            </div>
            {withdrawalStatus(w)}
          </div>
        </div>
      </div>
      {open && (
        <div className="mt-3 space-y-1.5 rounded-xl bg-ink-950/60 p-3 text-xs">
          <Row k="Куда" v={w.destination || '—'} mono />
          <Row k="Создана" v={fmtDate(w.created_at)} />
          {w.processed_at && <Row k="Обработана" v={fmtDate(w.processed_at)} />}
          {w.status === 'rejected' && <Row k="Причина" v={w.reject_reason || '—'} />}
          {w.status === 'rejected' && <Row k="Lev" v="возвращены на баланс" />}
        </div>
      )}
      {!open && w.destination && w.method !== 'cryptobot' && (
        <div className="ml-12 mt-1 font-mono text-[11px] text-ink-400">{shortAddr(w.destination)}</div>
      )}
    </button>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex gap-3">
      <span className="w-20 shrink-0 text-ink-400">{k}</span>
      <span className={`min-w-0 break-all text-[#f4f1ea] ${mono ? 'font-mono' : ''}`}>{v}</span>
    </div>
  );
}

export default function WalletPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get('tab') === 'withdrawals' ? 'withdrawals' : 'deposits';
  const { data: w, error, loading, reload } = useLoad(api.wallet, mockWallet);

  const setTab = (t: Tab) => {
    haptic();
    setParams({ tab: t }, { replace: true });
  };

  if (loading) return <Loader />;
  if (error || !w) return <div className="p-4"><ErrorBox message={error || ''} onRetry={reload} /></div>;

  const pendingCount = w.withdrawals.filter((x) => x.status === 'pending' || x.status === 'processing').length;

  return (
    <div className="page-transition p-4">
      <PageTitle
        icon={<WalletIcon size={22} />}
        title="Кошелёк"
        right={
          <button onClick={reload} className="rounded-lg p-2 text-ink-400 active:bg-white/5" aria-label="Обновить">
            <RefreshCw size={18} />
          </button>
        }
      />

      {/* Баланс */}
      <div className="card-gold mb-5 p-4">
        <div className="label">Баланс</div>
        <div className="tabular mt-1 text-4xl font-extrabold">
          <span className="gold-text">{fmtLev(w.balance)}</span>
          <span className="ml-2 text-lg font-semibold text-gold-400">Lev</span>
        </div>
        {w.pending_withdraw_lev > 0 && (
          <div className="mt-2 text-xs text-ink-300">
            ⏳ На выводе: <b className="text-gold-300">{fmtLev(w.pending_withdraw_lev)} Lev</b> ({pendingCount} заявк{pendingCount === 1 ? 'а' : 'и'})
          </div>
        )}
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button onClick={() => navigate('/crypto?tab=deposit')} className="btn-gold">
            <ArrowDownLeft size={16} /> Пополнить
          </button>
          <button onClick={() => navigate('/crypto?tab=withdraw')} className="btn-ghost">
            <ArrowUpRight size={16} /> Вывести
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-ink-400">Криптой — во вкладке «Пополнение / вывод». Звёздами — в чате с ботом.</p>
      </div>

      {/* Вкладки */}
      <div className="mb-3 flex rounded-xl border border-white/[0.06] bg-ink-900 p-1">
        {(['deposits', 'withdrawals'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold transition ${
              tab === t ? 'bg-gold-500/15 text-gold-300' : 'text-ink-400'
            }`}
          >
            {t === 'deposits' ? `Пополнения (${w.deposits.length})` : `Выводы (${w.withdrawals.length})`}
          </button>
        ))}
      </div>

      {tab === 'deposits' &&
        (w.deposits.length ? (
          <div className="card divide-y divide-white/[0.05]">
            {w.deposits.map((d) => <DepositRow key={d.id} d={d} />)}
          </div>
        ) : (
          <Empty emoji="💸" text="Пополнений пока нет. Пополнить Lev можно звёздами или криптой в боте." />
        ))}

      {tab === 'withdrawals' &&
        (w.withdrawals.length ? (
          <div className="card divide-y divide-white/[0.05]">
            {w.withdrawals.map((x) => <WithdrawalRow key={x.id} w={x} />)}
          </div>
        ) : (
          <Empty emoji="🏦" text="Выводов пока нет. Вывести Lev в крипту можно в боте." />
        ))}

      <button
        onClick={() => navigate(`/requisites?tab=${tab === 'withdrawals' ? 'withdraw' : 'deposit'}`)}
        className="card mt-5 flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm">🔐 Реквизиты для {tab === 'withdrawals' ? 'вывода' : 'пополнения'}</span>
        <span className="text-xs font-semibold text-gold-400">Открыть →</span>
      </button>
    </div>
  );
}
