import { useCallback, useEffect, useState } from 'react';
import WebApp from '@twa-dev/sdk';
import type { TelegramUser } from '../types';

interface UseTelegramReturn {
  tg: typeof WebApp;
  user: TelegramUser | null;
  initData: string;
  initDataUnsafe: typeof WebApp.initDataUnsafe;
  isReady: boolean;
  colorScheme: 'light' | 'dark';
  close: () => void;
  showAlert: (message: string) => void;
  showConfirm: (message: string) => Promise<boolean>;
  hapticFeedback: (type: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
  setMainButton: (text: string, onClick: () => void) => void;
  hideMainButton: () => void;
  setBackButton: (onClick: () => void) => void;
  hideBackButton: () => void;
}

export function useTelegram(): UseTelegramReturn {
  const [isReady, setIsReady] = useState(false);
  const [user, setUser] = useState<TelegramUser | null>(null);

  useEffect(() => {
    // Проверяем, что мы в контексте Telegram
    if (WebApp.initDataUnsafe?.user) {
      setUser(WebApp.initDataUnsafe.user as TelegramUser);
    }
    setIsReady(true);
  }, []);

  const close = useCallback(() => {
    WebApp.close();
  }, []);

  const showAlert = useCallback((message: string) => {
    WebApp.showAlert(message);
  }, []);

  const showConfirm = useCallback((message: string): Promise<boolean> => {
    return new Promise((resolve) => {
      WebApp.showConfirm(message, resolve);
    });
  }, []);

  const hapticFeedback = useCallback((type: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => {
    WebApp.HapticFeedback.impactOccurred(type);
  }, []);

  const setMainButton = useCallback((text: string, onClick: () => void) => {
    WebApp.MainButton.setText(text);
    WebApp.MainButton.onClick(onClick);
    WebApp.MainButton.show();
  }, []);

  const hideMainButton = useCallback(() => {
    WebApp.MainButton.hide();
  }, []);

  const setBackButton = useCallback((onClick: () => void) => {
    WebApp.BackButton.onClick(onClick);
    WebApp.BackButton.show();
  }, []);

  const hideBackButton = useCallback(() => {
    WebApp.BackButton.hide();
  }, []);

  return {
    tg: WebApp,
    user,
    initData: WebApp.initData,
    initDataUnsafe: WebApp.initDataUnsafe,
    isReady,
    colorScheme: WebApp.colorScheme,
    close,
    showAlert,
    showConfirm,
    hapticFeedback,
    setMainButton,
    hideMainButton,
    setBackButton,
    hideBackButton,
  };
}

export default useTelegram;
