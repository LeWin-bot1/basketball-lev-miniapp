import type { ReactNode } from 'react';
import WebApp from '@twa-dev/sdk';

/** Дата и время по-русски: «1 ноя, 12:45» */
export function fmtDate(ts?: number | null): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function fmtLev(n: number, sign = false): string {
  const s = Math.abs(n).toLocaleString('ru-RU');
  if (!sign) return `${n < 0 ? '−' : ''}${s}`;
  return `${n > 0 ? '+' : n < 0 ? '−' : ''}${s}`;
}

export function PageTitle({ icon, title, right }: { icon: ReactNode; title: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <h1 className="flex items-center gap-2 text-[22px] font-bold leading-tight tracking-tight text-[#f4f1ea]">
        <span className="text-gold-400">{icon}</span>
        {title}
      </h1>
      {right}
    </div>
  );
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="mb-5">
      <div className="mb-2 flex items-center justify-between px-1">
        <div className="label">{title}</div>
        {right}
      </div>
      {children}
    </section>
  );
}

const TONES = {
  ok: 'bg-emerald-400/10 text-emerald-300',
  wait: 'bg-gold-400/10 text-gold-300',
  info: 'bg-sky-400/10 text-sky-300',
  bad: 'bg-rose-400/10 text-rose-300',
  muted: 'bg-white/5 text-ink-400',
} as const;

export function Chip({ tone, children }: { tone: keyof typeof TONES; children: ReactNode }) {
  return <span className={`chip ${TONES[tone]}`}>{children}</span>;
}

export function Loader() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-gold-500/20 border-t-gold-400" />
      <p className="mt-4 text-sm text-ink-400">Загрузка…</p>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card p-5 text-center">
      <div className="text-3xl">⚠️</div>
      <p className="mt-2 text-sm text-ink-300">Не удалось загрузить данные</p>
      <p className="mt-1 text-xs text-ink-400">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost mt-4">
          Повторить
        </button>
      )}
    </div>
  );
}

export function Empty({ emoji, text }: { emoji: string; text: string }) {
  return (
    <div className="card flex flex-col items-center px-6 py-10 text-center">
      <div className="text-3xl opacity-80">{emoji}</div>
      <p className="mt-3 text-sm text-ink-400">{text}</p>
    </div>
  );
}

/** Закрыть Mini App и вернуться в чат с ботом (там пополнение/вывод). */
export function backToBot() {
  try {
    WebApp.close();
  } catch {
    /* вне Telegram — ничего */
  }
}

export function haptic() {
  try {
    WebApp.HapticFeedback.impactOccurred('light');
  } catch {
    /* вне Telegram */
  }
}
