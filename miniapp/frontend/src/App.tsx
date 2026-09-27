import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useTelegram } from './hooks/useTelegram';
import Layout from './components/Layout';
import ProfilePage from './pages/ProfilePage';
import LeaderboardPage from './pages/LeaderboardPage';
import TournamentsPage from './pages/TournamentsPage';
import TeamPage from './pages/TeamPage';
import HistoryPage from './pages/HistoryPage';
import PlayerViewPage from './pages/PlayerViewPage';

function App() {
  const { isReady, user } = useTelegram();

  // Показываем загрузку пока SDK не готов
  if (!isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-tg-bg">
        <div className="animate-pulse text-tg-hint">Загрузка...</div>
      </div>
    );
  }

  // В режиме разработки без Telegram создаём моковые данные
  const isDev = import.meta.env.DEV && !user;

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/profile" replace />} />
          <Route path="profile" element={<ProfilePage isDev={isDev} />} />
          <Route path="leaderboard" element={<LeaderboardPage />} />
          <Route path="tournaments" element={<TournamentsPage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="player/:userId" element={<PlayerViewPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
