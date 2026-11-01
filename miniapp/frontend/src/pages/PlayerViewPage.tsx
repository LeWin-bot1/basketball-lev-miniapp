import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { api } from '../api/client';
import type { PublicProfile } from '../types/app';
import { useLoad } from '../hooks/useLoad';
import { ErrorBox, Loader } from '../components/ui';

/** Профиль другого игрока: только ник и число матчей. */
export default function PlayerViewPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const id = Number(userId);
  const mock: PublicProfile = { user_id: id, nick: `Игрок ${id}`, matches: 42 };
  const { data: p, error, loading, reload } = useLoad(() => api.publicProfile(id), mock);

  return (
    <div className="page-transition p-4">
      <button onClick={() => navigate(-1)} className="mb-4 flex items-center gap-1 text-sm text-ink-400">
        <ArrowLeft size={16} /> Назад
      </button>
      {loading && <Loader />}
      {!loading && (error || !p) && <ErrorBox message={error || ''} onRetry={reload} />}
      {!loading && p && (
        <div className="card-gold flex flex-col items-center px-6 py-8 text-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-b from-gold-300 to-gold-600 text-2xl font-extrabold text-ink-950 shadow-[0_0_30px_rgba(212,169,55,0.35)]">
            {p.nick.replace('@', '').slice(0, 2).toUpperCase()}
          </div>
          <div className="mt-4 text-xl font-bold">{p.nick}</div>
          <div className="mt-5 rounded-xl border border-white/[0.06] bg-ink-950/60 px-6 py-3">
            <div className="gold-text tabular text-3xl font-extrabold">{p.matches}</div>
            <div className="text-xs text-ink-400">матчей сыграно</div>
          </div>
        </div>
      )}
    </div>
  );
}
