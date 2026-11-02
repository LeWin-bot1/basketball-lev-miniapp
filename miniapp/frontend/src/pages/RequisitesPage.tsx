import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { KeyRound, Check, Trash2 } from 'lucide-react';
import { api } from '../api/client';
import type { Requisites, RequisiteMethod, RequisitePurpose } from '../types/app';
import { useLoad } from '../hooks/useLoad';
import { Chip, ErrorBox, Loader, PageTitle, haptic } from '../components/ui';

const mockReq: Requisites = {
  deposit: { ton: null, trc20: 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t' },
  withdraw: { ton: null, trc20: null, cryptobot: 'tg_id 1350766902 (@Nikita_Kovalevsk)' },
};

const TRC20 = /^T[1-9A-HJ-NP-Za-km-z]{33}$/;
const TON = /^(EQ|UQ|kQ|0Q)[A-Za-z0-9_-]{46}$|^-?\d+:[0-9a-fA-F]{64}$/;

const META: Record<RequisiteMethod, { icon: string; title: string; placeholder: string; hint: string }> = {
  ton: {
    icon: '💎',
    title: 'TON-кошелёк',
    placeholder: 'UQ… или EQ…',
    hint: 'Tonkeeper, Telegram Wallet и др. Адрес начинается с UQ или EQ, 48 символов.',
  },
  trc20: {
    icon: '💵',
    title: 'USDT · TRC20 (Tron)',
    placeholder: 'T…',
    hint: 'Кошелёк или биржа в сети Tron. Адрес начинается с T, 34 символа.',
  },
  cryptobot: {
    icon: '🤖',
    title: 'Аккаунт @CryptoBot',
    placeholder: '',
    hint: 'Выплата приходит прямо на твой Telegram, без адреса и комиссии сети.',
  },
};

const ORDER: Record<RequisitePurpose, RequisiteMethod[]> = {
  withdraw: ['ton', 'trc20', 'cryptobot'],
  deposit: ['ton', 'trc20'],
};

function isValid(method: RequisiteMethod, v: string) {
  return method === 'trc20' ? TRC20.test(v) : TON.test(v);
}

function AddressCard({
  purpose,
  method,
  saved,
  onSaved,
}: {
  purpose: RequisitePurpose;
  method: 'ton' | 'trc20';
  saved: string | null;
  onSaved: (r: Requisites) => void;
}) {
  const meta = META[method];
  const [value, setValue] = useState(saved || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  useEffect(() => setValue(saved || ''), [saved]);

  const trimmed = value.trim();
  const changed = trimmed !== (saved || '');
  const invalid = trimmed.length > 0 && !isValid(method, trimmed);

  const save = async (v: string) => {
    setBusy(true);
    setError(null);
    try {
      const r = import.meta.env.DEV
        ? { ...mockReq, [purpose]: { ...mockReq[purpose], [method]: v || null } }
        : await api.saveRequisite(purpose, method, v);
      onSaved(r as Requisites);
      setOk(true);
      haptic();
      setTimeout(() => setOk(false), 1800);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 font-semibold">
          <span className="text-lg">{meta.icon}</span>
          {meta.title}
        </div>
        {saved ? <Chip tone="ok">Указан</Chip> : <Chip tone="muted">Не указан</Chip>}
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">{meta.hint}</p>

      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value.replace(/\s/g, ''))}
        placeholder={meta.placeholder}
        rows={2}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        className={`mt-3 w-full resize-none rounded-xl border bg-ink-950/70 px-3 py-2.5 font-mono text-[13px] text-[#f4f1ea] outline-none placeholder:text-ink-600 focus:border-gold-500/60 ${
          invalid ? 'border-rose-400/50' : 'border-white/10'
        }`}
      />
      {invalid && <p className="mt-1 text-[11px] text-rose-300">Проверь адрес: формат не подходит для этой сети.</p>}
      {error && <p className="mt-1 text-[11px] text-rose-300">{error}</p>}

      <div className="mt-3 flex gap-2">
        <button
          disabled={busy || !changed || invalid || !trimmed}
          onClick={() => save(trimmed)}
          className="btn-gold flex-1 py-2.5 disabled:opacity-40"
        >
          {ok ? <><Check size={16} /> Сохранено</> : busy ? 'Сохраняю…' : 'Сохранить'}
        </button>
        {saved && (
          <button
            disabled={busy}
            onClick={() => {
              setValue('');
              save('');
            }}
            className="btn-ghost px-3 py-2.5"
            aria-label="Удалить"
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>
    </div>
  );
}

function CryptoBotCard({ saved, onSaved }: { saved: string | null; onSaved: (r: Requisites) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const on = Boolean(saved);

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = import.meta.env.DEV
        ? { ...mockReq, withdraw: { ...mockReq.withdraw, cryptobot: on ? null : 'tg_id 1 (@you)' } }
        : await api.saveRequisite('withdraw', 'cryptobot', !on);
      onSaved(r as Requisites);
      haptic();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-semibold">
          <span className="text-lg">{META.cryptobot.icon}</span>
          {META.cryptobot.title}
        </div>
        <button
          onClick={toggle}
          disabled={busy}
          aria-pressed={on}
          className={`relative h-7 w-12 shrink-0 rounded-full transition ${on ? 'bg-gold-500' : 'bg-white/10'}`}
        >
          <span
            className={`absolute top-0.5 h-6 w-6 rounded-full bg-[#f4f1ea] shadow transition-all ${on ? 'left-[22px]' : 'left-0.5'}`}
          />
        </button>
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">{META.cryptobot.hint}</p>
      {on && (
        <div className="mt-3 rounded-xl bg-ink-950/70 px-3 py-2 font-mono text-[12px] text-ink-300">{saved}</div>
      )}
      {on && (
        <p className="mt-2 text-[11px] text-gold-300">⚠️ Открой @CryptoBot и нажми «Старт», иначе перевод не дойдёт.</p>
      )}
      {error && <p className="mt-1 text-[11px] text-rose-300">{error}</p>}
    </div>
  );
}

export default function RequisitesPage() {
  const [params, setParams] = useSearchParams();
  const tab: RequisitePurpose = params.get('tab') === 'deposit' ? 'deposit' : 'withdraw';
  const { data, error, loading, reload } = useLoad(api.requisites, mockReq);
  const [req, setReq] = useState<Requisites | null>(null);

  useEffect(() => {
    if (data) setReq(data);
  }, [data]);

  if (loading) return <Loader />;
  if (error || !req) return <div className="p-4"><ErrorBox message={error || ''} onRetry={reload} /></div>;

  const setTab = (t: RequisitePurpose) => {
    haptic();
    setParams({ tab: t }, { replace: true });
  };

  return (
    <div className="page-transition p-4">
      <PageTitle icon={<KeyRound size={22} />} title="Реквизиты" />

      <div className="mb-3 flex rounded-xl border border-white/[0.06] bg-ink-900 p-1">
        {(['withdraw', 'deposit'] as RequisitePurpose[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold transition ${
              tab === t ? 'bg-gold-500/15 text-gold-300' : 'text-ink-400'
            }`}
          >
            {t === 'withdraw' ? 'Для вывода' : 'Для пополнения'}
          </button>
        ))}
      </div>

      <p className="mb-4 px-1 text-xs leading-relaxed text-ink-400">
        {tab === 'withdraw'
          ? 'Куда отправлять выигрыш. При выводе в боте ты выбираешь способ — бот сразу возьмёт адрес отсюда.'
          : 'Кошельки, с которых ты пополняешь Lev. По ним мы видим, что перевод пришёл именно от тебя.'}
      </p>

      <div className="space-y-3">
        {ORDER[tab].map((m) =>
          m === 'cryptobot' ? (
            <CryptoBotCard key={m} saved={req.withdraw.cryptobot} onSaved={setReq} />
          ) : (
            <AddressCard key={`${tab}-${m}`} purpose={tab} method={m} saved={req[tab][m]} onSaved={setReq} />
          )
        )}
      </div>

      <p className="mt-5 px-1 text-center text-[11px] text-ink-400">
        Изменения сразу видны в боте. Проверяй сеть и адрес: перевод на неверный адрес вернуть нельзя.
      </p>
    </div>
  );
}
