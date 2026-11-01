import { useCallback, useEffect, useState } from 'react';

/** Загрузка данных с API: data / error / loading / reload. В dev — моки. */
export function useLoad<T>(load: () => Promise<T>, mock?: T) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (import.meta.env.DEV && mock !== undefined) {
        await new Promise((r) => setTimeout(r, 250));
        setData(mock);
      } else {
        setData(await load());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload };
}
