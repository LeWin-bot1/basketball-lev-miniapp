import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import WebApp from '@twa-dev/sdk';
import { Coins, ArrowDownLeft, ArrowUpRight, ExternalLink, CheckCircle2, Clock3, XCircle } from 'lucide-react';
import { api } from '../api/client';
import type { CryptoAsset, CryptoConfig, CryptoInvoice, WithdrawMethod, WithdrawResult } from '../types/app';
import { useLoad } from '../hooks/useLoad';
import { Chip, ErrorBox, Loader, PageTitle, fmtLev, haptic } from '../components/ui';

type Tab = 'deposit' | 'withdraw';

const mockConfig: CryptoConfig = {
  enabled: true,
  network: 'testnet',
  balance: 955,
  rates: { USDT: 100, TON: 300 },
  deposit: { assets: ['USDT', 'TON'], presets: { USDT: ['1', '5', '10', '25'], TON: ['0.5', '1', '5', '10'] }, min: { USDT: 0.1, TON: 0.05 }, max: 10000 },
  withdraw: { min_lev: 100, fee_pct: 0, decimals: { USDT: 2, TON: 3 }, saved: { ton: null, trc20: 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', cryptobot: null } },
};

const TRC20 = /^T[1-9A-HJ-NP-Za-km-z]{33}$/;
const TON = /^(EQ|UQ|kQ|0Q)[A-Za-z0-9_-]{46}$|^-?\d+:[0-9a-fA-F]{64}$/;

const ASSET_ICON: Record<CryptoAsset, string> = { USDT: '💵', TON: '💎' };

function num(v: string) {
  const n = parseFloat(v.replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

function openPay(url: string) {
  try {
    WebApp.openTelegramLink(url);
  } catch {
    window.open(url, '_blank');
  }
}

function Segmented<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-xl border border-white/[0.06] bg-ink-900 p-1">
      {options.map(([v, label]) => (
        <button
          key={v}
          onClick={() => { haptic(); onChange(v); }}
          className={`flex-1 rounded-lg py-2 text-sm font-semibold transition ${value === v ? 'bg-gold-500/15 text-gold-300' : 'text-ink-400'}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/* ---------------- Пополнение ---------------- */

function Deposit({ cfg, onBalance }: { cfg: CryptoConfig; onBalance: (b: number) => void }) {
  const [asset, setAsset] = useState<CryptoAsset>('USDT');
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invoice, setInvoice] = useState<CryptoInvoice | null>(null);
  const timer = useRef<number | null>(null);

  const value = num(amount);
  const lev = Math.floor(value * cfg.rates[asset] + 1e-9);
  const min = cfg.deposit.min[asset];
  const tooSmall = amount !== '' && value < min;

  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);

  // ждём оплату: опрашиваем статус счёта
  useEffect(() => {
    if (!invoice || invoice.status !== 'active' || import.meta.env.DEV) return;
    timer.current = window.setInterval(async () => {
      try {
        const st = await api.crypto.depositStatus(invoice.invoice_id);
        if (st.status !== 'active') {
          setInvoice(st);
          if (st.balance !== undefined) onBalance(st.balance);
          if (st.status === 'paid') {
            try { WebApp.HapticFeedback.notificationOccurred('success'); } catch { /* вне Telegram */ }
          }
        }
      } catch { /* сеть — попробуем ещё раз */ }
    }, 4000);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [invoice, onBalance]);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const inv = import.meta.env.DEV
        ? { invoice_id: 1, asset, amount, lev, status: 'active', pay_url: 'https://t.me/CryptoBot' }
        : await api.crypto.deposit(asset, amount.replace(',', '.'));
      setInvoice(inv);
      haptic();
      if (inv.pay_url) openPay(inv.pay_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (invoice) {
    const paid = invoice.status === 'paid';
    const expired = invoice.status === 'expired';
    return (
      <div className="card-gold p-5 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-ink-950/60">
          {paid ? <CheckCircle2 size={30} className="text-emerald-300" /> : expired ? <XCircle size={30} className="text-rose-300" /> : <Clock3 size={30} className="animate-pulse text-gold-300" />}
        </div>
        <div className="mt-3 text-lg font-bold">
          {paid ? 'Пополнение зачислено!' : expired ? 'Счёт истёк' : 'Ожидаем оплату'}
        </div>
        <div className="tabular mt-2 text-2xl font-extrabold">
          {invoice.amount} {invoice.asset} → <span className="gold-text">{fmtLev(invoice.lev)} Lev</span>
        </div>
        <div className="mt-1 text-xs text-ink-400">Счёт #{invoice.invoice_id}</div>
        {!paid && !expired && (
          <>
            <p className="mt-3 text-xs text-ink-400">
              Оплати счёт в CryptoBot. Lev зачислятся автоматически — эту страницу можно не закрывать.
            </p>
            {invoice.pay_url && (
              <button onClick={() => openPay(invoice.pay_url!)} className="btn-gold mt-4 w-full">
                <ExternalLink size={16} /> Оплатить в CryptoBot
              </button>
            )}
          </>
        )}
        <button onClick={() => { setInvoice(null); setAmount(''); }} className="btn-ghost mt-2 w-full">
          {paid || expired ? 'Новое пополнение' : 'Отменить и создать другой'}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card p-4">
        <div className="label mb-2">Монета</div>
        <div className="grid grid-cols-2 gap-2">
          {cfg.deposit.assets.map((a) => (
            <button
              key={a}
              onClick={() => { haptic(); setAsset(a); setAmount(''); }}
              className={`rounded-xl border px-3 py-3 text-left transition ${asset === a ? 'border-gold-500/60 bg-gold-500/10' : 'border-white/[0.06] bg-ink-950/40'}`}
            >
              <div className="text-lg">{ASSET_ICON[a]}</div>
              <div className="mt-1 text-sm font-semibold">{a}</div>
              <div className="text-[11px] text-ink-400">1 {a} = {cfg.rates[a]} Lev</div>
            </button>
          ))}
        </div>
      </div>

      <div className="card p-4">
        <div className="label mb-2">Сумма в {asset}</div>
        <input
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value.replace(/[^0-9.,]/g, ''))}
          placeholder={`от ${min}`}
          className={`tabular w-full rounded-xl border bg-ink-950/70 px-4 py-3 text-xl font-bold outline-none placeholder:text-ink-600 focus:border-gold-500/60 ${tooSmall ? 'border-rose-400/50' : 'border-white/10'}`}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {cfg.deposit.presets[asset].map((p) => (
            <button key={p} onClick={() => { haptic(); setAmount(p); }} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-semibold text-ink-300 active:bg-white/5">
              {p} {asset}
            </button>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between rounded-xl bg-ink-950/60 px-4 py-3">
          <span className="text-sm text-ink-300">Получишь</span>
          <span className="tabular text-lg font-extrabold"><span className="gold-text">{fmtLev(value > 0 ? lev : 0)}</span> <span className="text-sm text-gold-400">Lev</span></span>
        </div>
        {tooSmall && <p className="mt-2 text-[11px] text-rose-300">Минимум {min} {asset}</p>}
        {error && <p className="mt-2 text-[11px] text-rose-300">{error}</p>}
        <button disabled={busy || !value || tooSmall || lev <= 0} onClick={create} className="btn-gold mt-4 w-full disabled:opacity-40">
          <ArrowDownLeft size={16} /> {busy ? 'Создаю счёт…' : 'Пополнить через CryptoBot'}
        </button>
        <p className="mt-2 text-center text-[11px] text-ink-400">Откроется счёт в @CryptoBot. Оплатить можно с баланса CryptoBot или переводом.</p>
      </div>
    </div>
  );
}

/* ---------------- Вывод ---------------- */

const METHODS: { id: WithdrawMethod; icon: string; title: string; sub: string }[] = [
  { id: 'cryptobot', icon: '🤖', title: 'В CryptoBot', sub: 'USDT или TON на твой Telegram · без комиссии сети' },
  { id: 'trc20', icon: '💵', title: 'USDT · TRC20', sub: 'На кошелёк или биржу в сети Tron' },
  { id: 'ton', icon: '💎', title: 'TON-кошелёк', sub: 'Tonkeeper, Telegram Wallet и др.' },
];

function Withdraw({ cfg, onBalance }: { cfg: CryptoConfig; onBalance: (b: number) => void }) {
  const navigate = useNavigate();
  const [method, setMethod] = useState<WithdrawMethod>('cryptobot');
  const [cbAsset, setCbAsset] = useState<CryptoAsset>('USDT');
  const [address, setAddress] = useState('');
  const [lev, setLev] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<WithdrawResult | null>(null);

  const asset: CryptoAsset = method === 'cryptobot' ? cbAsset : method === 'trc20' ? 'USDT' : 'TON';
  const saved = cfg.withdraw.saved;
  useEffect(() => {
    if (method !== 'cryptobot') setAddress(saved[method] || '');
  }, [method, saved]);

  const levNum = parseInt(lev || '0', 10) || 0;
  const dec = cfg.withdraw.decimals[asset] ?? 2;
  const out = Math.floor(((levNum * (1 - cfg.withdraw.fee_pct / 100)) / cfg.rates[asset]) * 10 ** dec + 1e-9) / 10 ** dec;
  const addrOk = method === 'cryptobot' || (method === 'trc20' ? TRC20.test(address.trim()) : TON.test(address.trim()));
  const levErr =
    lev === '' ? null : levNum < cfg.withdraw.min_lev ? `Минимум ${cfg.withdraw.min_lev} Lev` : levNum > cfg.balance ? 'Больше, чем на балансе' : null;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = import.meta.env.DEV
        ? { id: 7, lev: levNum, asset, amount: out.toFixed(dec), method, destination: method === 'cryptobot' ? '@CryptoBot' : address, queue_position: 1, balance: cfg.balance - levNum }
        : await api.crypto.withdraw({ method, lev: levNum, asset: method === 'cryptobot' ? cbAsset : undefined, address: method === 'cryptobot' ? undefined : address.trim() });
      setDone(res);
      onBalance(res.balance);
      try { WebApp.HapticFeedback.notificationOccurred('success'); } catch { /* вне Telegram */ }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="card-gold p-5 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-ink-950/60">
          <CheckCircle2 size={30} className="text-emerald-300" />
        </div>
        <div className="mt-3 text-lg font-bold">Заявка #{done.id} создана</div>
        <div className="tabular mt-2 text-2xl font-extrabold">
          {fmtLev(done.lev)} Lev → <span className="gold-text">{done.amount} {done.asset}</span>
        </div>
        <div className="mt-2 break-all text-xs text-ink-400">Куда: {done.destination}</div>
        <div className="mt-3"><Chip tone="wait">⏳ Место в очереди: {done.queue_position}</Chip></div>
        <p className="mt-3 text-xs text-ink-400">Бот пришлёт уведомление, когда выплата будет отправлена.</p>
        <button onClick={() => navigate('/wallet?tab=withdrawals')} className="btn-gold mt-4 w-full">Смотреть статус</button>
        <button onClick={() => { setDone(null); setLev(''); }} className="btn-ghost mt-2 w-full">Новый вывод</button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card p-4">
        <div className="label mb-2">Куда вывести</div>
        <div className="space-y-2">
          {METHODS.map((m) => (
            <button
              key={m.id}
              onClick={() => { haptic(); setMethod(m.id); setError(null); }}
              className={`flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition ${method === m.id ? 'border-gold-500/60 bg-gold-500/10' : 'border-white/[0.06] bg-ink-950/40'}`}
            >
              <span className="text-xl">{m.icon}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">{m.title}</span>
                <span className="block text-[11px] text-ink-400">{m.sub}</span>
              </span>
              <span className={`h-4 w-4 shrink-0 rounded-full border-2 ${method === m.id ? 'border-gold-400 bg-gold-400' : 'border-ink-600'}`} />
            </button>
          ))}
        </div>

        {method === 'cryptobot' && (
          <div className="mt-3 grid grid-cols-2 gap-2">
            {(['USDT', 'TON'] as CryptoAsset[]).map((a) => (
              <button key={a} onClick={() => { haptic(); setCbAsset(a); }} className={`rounded-lg border py-2 text-sm font-semibold ${cbAsset === a ? 'border-gold-500/60 bg-gold-500/10 text-gold-300' : 'border-white/10 text-ink-400'}`}>
                {ASSET_ICON[a]} {a}
              </button>
            ))}
            <p className="col-span-2 text-[11px] text-gold-300">⚠️ Открой @CryptoBot и нажми «Старт», иначе перевод не дойдёт.</p>
          </div>
        )}

        {method !== 'cryptobot' && (
          <div className="mt-3">
            <div className="mb-1 text-[11px] text-ink-400">
              Адрес {method === 'trc20' ? 'USDT TRC20 (начинается с T)' : 'TON (начинается с UQ или EQ)'}
              {cfg.withdraw.saved[method] && address === cfg.withdraw.saved[method] ? ' · из реквизитов' : ''}
            </div>
            <textarea
              rows={2}
              value={address}
              onChange={(e) => setAddress(e.target.value.replace(/\s/g, ''))}
              spellCheck={false}
              autoCapitalize="off"
              placeholder={method === 'trc20' ? 'T…' : 'UQ…'}
              className={`w-full resize-none rounded-xl border bg-ink-950/70 px-3 py-2.5 font-mono text-[13px] outline-none placeholder:text-ink-600 focus:border-gold-500/60 ${address && !addrOk ? 'border-rose-400/50' : 'border-white/10'}`}
            />
            {address && !addrOk && <p className="mt-1 text-[11px] text-rose-300">Адрес не подходит для этой сети</p>}
          </div>
        )}
      </div>

      <div className="card p-4">
        <div className="flex items-center justify-between">
          <div className="label">Сумма в Lev</div>
          <button onClick={() => { haptic(); setLev(String(cfg.balance)); }} className="text-xs font-semibold text-gold-400">Всё: {fmtLev(cfg.balance)}</button>
        </div>
        <input
          inputMode="numeric"
          value={lev}
          onChange={(e) => setLev(e.target.value.replace(/\D/g, ''))}
          placeholder={`от ${cfg.withdraw.min_lev}`}
          className={`tabular mt-2 w-full rounded-xl border bg-ink-950/70 px-4 py-3 text-xl font-bold outline-none placeholder:text-ink-600 focus:border-gold-500/60 ${levErr ? 'border-rose-400/50' : 'border-white/10'}`}
        />
        <div className="mt-4 flex items-center justify-between rounded-xl bg-ink-950/60 px-4 py-3">
          <span className="text-sm text-ink-300">Получишь</span>
          <span className="tabular text-lg font-extrabold"><span className="gold-text">{levNum > 0 ? out.toFixed(dec) : '0'}</span> <span className="text-sm text-gold-400">{asset}</span></span>
        </div>
        <div className="mt-2 text-[11px] text-ink-400">
          Курс: {cfg.rates[asset]} Lev = 1 {asset}{cfg.withdraw.fee_pct ? ` · комиссия ${cfg.withdraw.fee_pct}%` : ''}
        </div>
        {levErr && <p className="mt-2 text-[11px] text-rose-300">{levErr}</p>}
        {error && <p className="mt-2 text-[11px] text-rose-300">{error}</p>}
        <button disabled={busy || !levNum || !!levErr || !addrOk || out <= 0} onClick={submit} className="btn-gold mt-4 w-full disabled:opacity-40">
          <ArrowUpRight size={16} /> {busy ? 'Создаю заявку…' : 'Вывести'}
        </button>
        <p className="mt-2 text-center text-[11px] text-ink-400">Lev спишутся сразу. Если заявку отклонят — вернутся на баланс.</p>
      </div>
    </div>
  );
}

/* ---------------- Страница ---------------- */

export default function CryptoPage() {
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get('tab') === 'withdraw' ? 'withdraw' : 'deposit';
  const { data, error, loading, reload } = useLoad(api.crypto.config, mockConfig);
  const [balance, setBalance] = useState<number | null>(null);

  if (loading) return <Loader />;
  if (error || !data) return <div className="p-4"><ErrorBox message={error || ''} onRetry={reload} /></div>;

  const cfg: CryptoConfig = { ...data, balance: balance ?? data.balance };

  return (
    <div className="page-transition p-4">
      <PageTitle
        icon={<Coins size={22} />}
        title="Крипта"
        right={data.network !== 'mainnet' ? <Chip tone="info">тестовая сеть</Chip> : undefined}
      />

      <div className="card-gold mb-4 flex items-end justify-between p-4">
        <div>
          <div className="label">Баланс</div>
          <div className="tabular mt-1 text-3xl font-extrabold">
            <span className="gold-text">{fmtLev(cfg.balance)}</span>
            <span className="ml-1.5 text-base font-semibold text-gold-400">Lev</span>
          </div>
        </div>
        <div className="text-right text-[11px] text-ink-400">
          1 USDT = {data.rates.USDT} Lev<br />1 TON = {data.rates.TON} Lev
        </div>
      </div>

      <div className="mb-4">
        <Segmented<Tab>
          value={tab}
          options={[['deposit', 'Пополнить'], ['withdraw', 'Вывести']]}
          onChange={(t) => setParams({ tab: t }, { replace: true })}
        />
      </div>

      {!data.enabled ? (
        <div className="card p-5 text-center text-sm text-ink-300">Крипто-платежи временно недоступны.</div>
      ) : tab === 'deposit' ? (
        <Deposit cfg={cfg} onBalance={setBalance} />
      ) : (
        <Withdraw cfg={cfg} onBalance={setBalance} />
      )}

      <p className="mt-5 px-1 text-center text-[11px] text-ink-400">
        ⭐ Пополнить звёздами можно прямо в чате с ботом.
      </p>
    </div>
  );
}
