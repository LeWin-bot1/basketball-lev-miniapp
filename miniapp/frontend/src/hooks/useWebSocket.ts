import { useEffect, useRef, useState, useCallback } from 'react';

interface UseWebSocketOptions {
  /** Автоматически переподключаться при разрыве */
  reconnect?: boolean;
  /** Задержка перед переподключением (мс) */
  reconnectDelay?: number;
  /** Максимальное количество попыток переподключения */
  maxRetries?: number;
  /** Callback при получении сообщения */
  onMessage?: (data: unknown) => void;
  /** Callback при подключении */
  onOpen?: () => void;
  /** Callback при отключении */
  onClose?: () => void;
  /** Callback при ошибке */
  onError?: (error: Event) => void;
}

interface WebSocketState {
  isConnected: boolean;
  lastMessage: unknown;
  error: string | null;
}

/**
 * Hook для работы с WebSocket соединением.
 * 
 * @example
 * ```tsx
 * const { isConnected, lastMessage, sendMessage } = useWebSocket(
 *   'ws://localhost:8080/ws/tournaments/solo',
 *   {
 *     onMessage: (data) => console.log('Received:', data),
 *     reconnect: true,
 *   }
 * );
 * ```
 */
export function useWebSocket(
  url: string | null,
  options: UseWebSocketOptions = {}
) {
  const {
    reconnect = true,
    reconnectDelay = 3000,
    maxRetries = 5,
    onMessage,
    onOpen,
    onClose,
    onError,
  } = options;

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    lastMessage: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const connect = useCallback(() => {
    if (!url) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setState((prev) => ({ ...prev, isConnected: true, error: null }));
        retriesRef.current = 0;
        onOpen?.();

        // Запускаем ping каждые 30 секунд
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          // Игнорируем pong ответы
          if (event.data === 'pong' || event.data === 'ping') {
            return;
          }

          const data = JSON.parse(event.data);
          setState((prev) => ({ ...prev, lastMessage: data }));
          onMessage?.(data);
        } catch {
          // Не JSON - возможно текстовое сообщение
          setState((prev) => ({ ...prev, lastMessage: event.data }));
          onMessage?.(event.data);
        }
      };

      ws.onclose = () => {
        setState((prev) => ({ ...prev, isConnected: false }));
        onClose?.();

        // Очищаем ping интервал
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Переподключаемся если нужно
        if (reconnect && retriesRef.current < maxRetries) {
          retriesRef.current++;
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectDelay);
        }
      };

      ws.onerror = (error) => {
        setState((prev) => ({ ...prev, error: 'WebSocket error' }));
        onError?.(error);
      };

      wsRef.current = ws;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Connection failed',
      }));
    }
  }, [url, reconnect, reconnectDelay, maxRetries, onMessage, onOpen, onClose, onError]);

  const disconnect = useCallback(() => {
    // Отменяем переподключение
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Очищаем ping интервал
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    // Закрываем соединение
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setState((prev) => ({ ...prev, isConnected: false }));
  }, []);

  const sendMessage = useCallback((message: string | object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const data = typeof message === 'string' ? message : JSON.stringify(message);
      wsRef.current.send(data);
    }
  }, []);

  // Подключаемся при монтировании
  useEffect(() => {
    if (url) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [url]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    ...state,
    sendMessage,
    connect,
    disconnect,
  };
}

/**
 * Hook для подписки на обновления турнира.
 */
export function useTournamentWebSocket(
  tournamentType: 'solo' | 'team',
  onUpdate?: (data: unknown) => void
) {
  const apiUrl = import.meta.env.VITE_API_URL || '';
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  
  // Формируем WebSocket URL
  let wsUrl: string | null = null;
  if (apiUrl) {
    // Если API URL указан, преобразуем его в WebSocket URL
    const apiHost = apiUrl.replace(/^https?:\/\//, '').replace(/\/api$/, '');
    wsUrl = `${wsProtocol}//${apiHost}/ws/tournaments/${tournamentType}`;
  } else if (typeof window !== 'undefined') {
    // В режиме разработки используем текущий хост
    wsUrl = `${wsProtocol}//${window.location.host}/ws/tournaments/${tournamentType}`;
  }

  return useWebSocket(wsUrl, {
    onMessage: onUpdate,
    reconnect: true,
    reconnectDelay: 5000,
    maxRetries: 10,
  });
}

export default useWebSocket;
