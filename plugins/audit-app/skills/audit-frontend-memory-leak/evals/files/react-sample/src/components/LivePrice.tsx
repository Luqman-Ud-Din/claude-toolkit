import { useEffect, useRef, useState } from 'react';
import { Chart } from 'chart.js';

export function LivePrice({ symbol }: { symbol: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [price, setPrice] = useState(0);

  useEffect(() => {
    // no cleanup returned: interval and listener survive unmount, chart never destroyed
    const chart = new Chart(canvas.current!, { type: 'line', data: { datasets: [] } });
    setInterval(() => setPrice(p => p + 1), 1000);
    window.addEventListener('resize', () => chart.resize());
  }, [symbol]);

  return <canvas ref={canvas} title={String(price)} />;
}

// Negative control: everything acquired in the effect is released in the cleanup.
export function Clock() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    const onVis = () => setNow(Date.now());
    document.addEventListener('visibilitychange', onVis);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, []);
  return <time>{new Date(now).toLocaleTimeString()}</time>;
}
