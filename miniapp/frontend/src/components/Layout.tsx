import { Outlet, NavLink } from 'react-router-dom';
import { User, Trophy, Users, History, Medal } from 'lucide-react';

const navItems = [
  { path: '/profile', icon: User, label: 'Профиль' },
  { path: '/leaderboard', icon: Medal, label: 'Рейтинг' },
  { path: '/tournaments', icon: Trophy, label: 'Турниры' },
  { path: '/team', icon: Users, label: 'Команда' },
  { path: '/history', icon: History, label: 'История' },
];

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-tg-bg">
      {/* Основной контент */}
      <main className="flex-1 overflow-y-auto pb-20">
        <Outlet />
      </main>

      {/* Нижняя навигация */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 safe-area-bottom">
        <div className="flex justify-around items-center h-16">
          {navItems.map(({ path, icon: Icon, label }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center w-full h-full transition-colors ${
                  isActive
                    ? 'text-primary-500'
                    : 'text-gray-400 hover:text-gray-600'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    size={22}
                    strokeWidth={isActive ? 2.5 : 2}
                  />
                  <span className="text-[10px] mt-1 font-medium">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
