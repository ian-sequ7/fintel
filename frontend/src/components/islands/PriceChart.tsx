import { useEffect, useRef, useState } from "react";
import { createChart, type IChartApi, type ISeriesApi, ColorType } from "lightweight-charts";

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

// Generate mock price data for demonstration
function _generateMockData(ticker: string): PricePoint[] {
  const data: PricePoint[] = [];
  const basePrice = ticker === "AAPL" ? 225 : ticker === "NVDA" ? 875 : ticker === "MSFT" ? 415 : 150;
  let price = basePrice;

  const today = new Date();
  for (let i = 90; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);

    // Skip weekends
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const volatility = 0.02;
    const change = (Math.random() - 0.48) * volatility * price;
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

export default function PriceChart({ ticker, data, height = 300 }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [mounted, setMounted] = useState(false);

  // Get theme colors from CSS variables
  const getThemeColors = () => {
    if (typeof window === "undefined") {
      return {
        bgBase: "#ffffff",
        bgSurface: "#f8fafc",
        textPrimary: "#0f172a",
        textSecondary: "#64748b",
        border: "#e2e8f0",
        chartUp: "#22c55e",
        chartDown: "#ef4444",
        chartGrid: "#e2e8f0",
      };
    }

    const style = getComputedStyle(document.documentElement);
    return {
      bgBase: style.getPropertyValue("--bg-base").trim() || "#ffffff",
      bgSurface: style.getPropertyValue("--bg-surface").trim() || "#f8fafc",
      textPrimary: style.getPropertyValue("--text-primary").trim() || "#0f172a",
      textSecondary: style.getPropertyValue("--text-secondary").trim() || "#64748b",
      border: style.getPropertyValue("--border").trim() || "#e2e8f0",
      chartUp: style.getPropertyValue("--chart-up").trim() || "#22c55e",
      chartDown: style.getPropertyValue("--chart-down").trim() || "#ef4444",
      chartGrid: style.getPropertyValue("--chart-grid").trim() || "#e2e8f0",
    };
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !chartContainerRef.current) return;

    const colors = getThemeColors();

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: colors.bgSurface },
        textColor: colors.textSecondary,
      },
      grid: {
        vertLines: { color: colors.chartGrid },
        horzLines: { color: colors.chartGrid },
      },
      width: chartContainerRef.current.clientWidth,
      height,
      rightPriceScale: {
        borderColor: colors.border,
      },
      timeScale: {
        borderColor: colors.border,
        timeVisible: true,
      },
      crosshair: {
        vertLine: {
          color: colors.textSecondary,
          labelBackgroundColor: colors.bgSurface,
        },
        horzLine: {
          color: colors.textSecondary,
          labelBackgroundColor: colors.bgSurface,
        },
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: colors.chartUp,
      downColor: colors.chartDown,
      borderUpColor: colors.chartUp,
      borderDownColor: colors.chartDown,
      wickUpColor: colors.chartUp,
      wickDownColor: colors.chartDown,
    });

    seriesRef.current = candlestickSeries;

    // Set data
    const chartData = data ?? _generateMockData(ticker);
    candlestickSeries.setData(chartData);

    // Fit content
    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener("resize", handleResize);

    // Listen for theme changes
    const observer = new MutationObserver(() => {
      const newColors = getThemeColors();
      chart.applyOptions({
        layout: {
          background: { type: ColorType.Solid, color: newColors.bgSurface },
          textColor: newColors.textSecondary,
        },
        grid: {
          vertLines: { color: newColors.chartGrid },
          horzLines: { color: newColors.chartGrid },
        },
        rightPriceScale: {
          borderColor: newColors.border,
        },
        timeScale: {
          borderColor: newColors.border,
        },
      });

      candlestickSeries.applyOptions({
        upColor: newColors.chartUp,
        downColor: newColors.chartDown,
        borderUpColor: newColors.chartUp,
        borderDownColor: newColors.chartDown,
        wickUpColor: newColors.chartUp,
        wickDownColor: newColors.chartDown,
      });
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    return () => {
      window.removeEventListener("resize", handleResize);
      observer.disconnect();
      chart.remove();
    };
  }, [mounted, ticker, data, height]);

  if (!mounted) {
    return (
      <div
        className="bg-bg-surface border border-border rounded-lg animate-pulse"
        style={{ height }}
      />
    );
  }

  return (
    <div
      ref={chartContainerRef}
      className="bg-bg-surface border border-border rounded-lg overflow-hidden"
    />
  );
}
