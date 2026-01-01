import { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries, type IChartApi, type ISeriesApi, ColorType } from "lightweight-charts";

interface PricePoint {
  time: string; // YYYY-MM-DD format
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface Props {
  ticker: string;
  data?: PricePoint[];
  height?: number;
}

// Theme colors for light and dark modes
const LIGHT_THEME = {
  background: "#ffffff",
  text: "#64748b",
  grid: "#e2e8f0",
  border: "#e2e8f0",
  crosshair: "#94a3b8",
  upColor: "#22c55e",
  downColor: "#ef4444",
};

const DARK_THEME = {
  background: "#1e293b",
  text: "#94a3b8",
  grid: "#334155",
  border: "#334155",
  crosshair: "#64748b",
  upColor: "#22c55e",
  downColor: "#ef4444",
};

// Generate mock price data for demonstration
function _generateMockData(ticker: string): PricePoint[] {
  const data: PricePoint[] = [];
  const basePrices: Record<string, number> = {
    AAPL: 225, NVDA: 875, MSFT: 415, GOOGL: 175, META: 490,
    AMZN: 185, TSLA: 245, JPM: 195, V: 280, JNJ: 155,
  };
  const basePrice = basePrices[ticker] ?? 150;
  let price = basePrice * 0.95;

  const today = new Date();
  for (let i = 90; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);

    // Skip weekends
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const volatility = 0.02;
    const drift = 0.001;
    const change = (Math.random() - 0.48 + drift) * volatility * price;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) * (1 + Math.random() * 0.01);
    const low = Math.min(open, close) * (1 - Math.random() * 0.01);

    data.push({
      time: date.toISOString().split("T")[0],
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume: Math.floor(Math.random() * 50000000) + 10000000,
    });

    price = close;
  }

  return data;
}

// Detect current theme from document
function _getTheme(): typeof LIGHT_THEME {
  if (typeof document === "undefined") return LIGHT_THEME;
  const theme = document.documentElement.dataset.theme;
  return theme === "dark" ? DARK_THEME : LIGHT_THEME;
}

export default function PriceChart({ ticker, data, height = 350 }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !chartContainerRef.current) return;

    const container = chartContainerRef.current;
    const theme = _getTheme();

    // Create chart
    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: theme.background },
        textColor: theme.text,
      },
      grid: {
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      width: container.clientWidth,
      height,
      rightPriceScale: {
        borderColor: theme.border,
      },
      timeScale: {
        borderColor: theme.border,
        timeVisible: false,
      },
      crosshair: {
        vertLine: {
          color: theme.crosshair,
          width: 1,
          style: 3,
          labelBackgroundColor: theme.background,
        },
        horzLine: {
          color: theme.crosshair,
          width: 1,
          style: 3,
          labelBackgroundColor: theme.background,
        },
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
      },
    });

    chartRef.current = chart;

    // Add candlestick series (v5 API)
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: theme.upColor,
      downColor: theme.downColor,
      borderUpColor: theme.upColor,
      borderDownColor: theme.downColor,
      wickUpColor: theme.upColor,
      wickDownColor: theme.downColor,
    });

    seriesRef.current = candlestickSeries;

    // Set data
    const chartData = data ?? _generateMockData(ticker);
    candlestickSeries.setData(chartData);

    // Fit content
    chart.timeScale().fitContent();

    // Handle resize with ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (width > 0) {
          chart.applyOptions({ width });
        }
      }
    });

    resizeObserver.observe(container);

    // Watch for theme changes with MutationObserver
    const themeObserver = new MutationObserver(() => {
      const newTheme = _getTheme();

      chart.applyOptions({
        layout: {
          background: { type: ColorType.Solid, color: newTheme.background },
          textColor: newTheme.text,
        },
        grid: {
          vertLines: { color: newTheme.grid },
          horzLines: { color: newTheme.grid },
        },
        rightPriceScale: {
          borderColor: newTheme.border,
        },
        timeScale: {
          borderColor: newTheme.border,
        },
        crosshair: {
          vertLine: {
            color: newTheme.crosshair,
            labelBackgroundColor: newTheme.background,
          },
          horzLine: {
            color: newTheme.crosshair,
            labelBackgroundColor: newTheme.background,
          },
        },
      });

      candlestickSeries.applyOptions({
        upColor: newTheme.upColor,
        downColor: newTheme.downColor,
        borderUpColor: newTheme.upColor,
        borderDownColor: newTheme.downColor,
        wickUpColor: newTheme.upColor,
        wickDownColor: newTheme.downColor,
      });
    });

    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    // Cleanup on unmount
    return () => {
      resizeObserver.disconnect();
      themeObserver.disconnect();
      chart.remove();
    };
  }, [mounted, ticker, data, height]);

  // Loading placeholder
  if (!mounted) {
    return (
      <div
        className="bg-bg-surface rounded-lg animate-pulse flex items-center justify-center"
        style={{ height }}
      >
        <span className="text-text-secondary text-sm">Loading chart...</span>
      </div>
    );
  }

  return (
    <div
      ref={chartContainerRef}
      className="w-full"
      style={{ height }}
    />
  );
}
