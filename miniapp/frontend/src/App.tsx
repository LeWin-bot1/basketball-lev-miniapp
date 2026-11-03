import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useTelegram } from './hooks/useTelegram';
import Layout from './components/Layout';
import ProfilePage from './pages/ProfilePage';
import TournamentsPage from './pages/TournamentsPage';
import WalletPage from './pages/WalletPage';
import PlayerViewPage from './pages/PlayerViewPage';
import RequisitesPage from './pages/RequisitesPage';
import CryptoPage from './pages/CryptoPage';

/** Старые ссылки бота (/history?tab=...) ведут в кошелёк с той же вкладкой. */
function HistoryRedirect() {
  const { search } = useLocation();
  const tab = new URLSearchParams(search).get('tab');
  const target = tab === 'withdrawals' ? 'withdrawals' : 'deposits';
  return <Navigate to={`/wallet?tab=${target}`} replace />;
}

function App() {
  const { isReady } = useTelegram();

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-gold-500/20 border-t-gold-400" />
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/profile" replace />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="tournaments" element={<TournamentsPage />} />
          <Route path="crypto" element={<CryptoPage />} />
          <Route path="wallet" element={<WalletPage />} />
          <Route path="requisites" element={<RequisitesPage />} />
          <Route path="player/:userId" element={<PlayerViewPage />} />
          {/* старые адреса */}
          <Route path="history" element={<HistoryRedirect />} />
          <Route path="leaderboard" element={<Navigate to="/tournaments" replace />} />
          <Route path="team" element={<Navigate to="/profile" replace />} />
          <Route path="*" element={<Navigate to="/profile" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
