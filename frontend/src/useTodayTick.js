import { useEffect, useState } from 'react';

export function useTodayTick(checkIntervalMs = 60000) {
  const [today, setToday] = useState(() => new Date());

  useEffect(() => {
    const refresh = () => setToday(new Date());
    refresh();
    const intervalId = window.setInterval(refresh, checkIntervalMs);
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [checkIntervalMs]);

  return today;
}
