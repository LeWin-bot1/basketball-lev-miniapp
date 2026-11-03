import { Outlet, NavLink } from 'react-router-dom';
import { User, Trophy, Wallet, KeyRound, Coins } from 'lucide-react';
import { haptic } from './ui';

const navItems = [
  { path: '/tournaments', icon: Trophy, label: 'Турнир' },
  { path: '/profile', icon: User, label: 'Профиль' },
  { path: '/crypto', icon: Coins, label: 'Крипта' },
  { path: '/wallet', icon: Wallet, label: 'Кошелёк' },
  { path: '/requisites', icon: KeyRound, label: 'Реквизиты' },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <main className="mx-auto w-full max-w-lg flex-1 pb-24">
        <Outlet />
      </main>

      <nav className="safe-area-bottom fixed bottom-0 left-0 right-0 border-t border-white/[0.06] bg-ink-950/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-lg items-center justify-around">
          {navItems.map(({ path, icon: Icon, label }) => (
            <NavLink
              key={path}
              to={path}
              onClick={haptic}
              className={({ isActive }) =>
                `flex h-full w-full flex-col items-center justify-center transition-colors ${
                  isActive ? 'text-gold-400' : 'text-ink-400'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={22} strokeWidth={isActive ? 2.4 : 1.9} />
                  <span className="mt-1 text-[10px] font-semibold tracking-wide">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
