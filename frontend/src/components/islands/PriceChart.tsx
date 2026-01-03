import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
  ColorType,
} from "lightweight-charts";

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
  companyName?: string;
}

type TimeRange = "1D" | "1W" | "1M" | "3M" | "6M" | "1Y" | "ALL";

// Theme colors for light and dark modes
const LIGHT_THEME = {
  background: "#ffffff",
  text: "#64748b",
  grid: "#f1f5f9",
  border: "#e2e8f0",
  crosshair: "#94a3b8",
  upColor: "#22c55e",
  downColor: "#ef4444",
  volumeUp: "rgba(34, 197, 94, 0.5)",
  volumeDown: "rgba(239, 68, 68, 0.5)",
};

const DARK_THEME = {
  background: "#1e293b",
  text: "#94a3b8",
  grid: "#334155",
  border: "#475569",
  crosshair: "#64748b",
  upColor: "#22c55e",
  downColor: "#ef4444",
  volumeUp: "rgba(34, 197, 94, 0.5)",
  volumeDown: "rgba(239, 68, 68, 0.5)",
};

// Generate mock price data for demonstration
function _generateMockData(ticker: string): PricePoint[] {
  const data: PricePoint[] = [];
  const basePrices: Record<string, number> = {
    AAPL: 225, NVDA: 875, MSFT: 415, GOOGL: 175, META: 490,
    AMZN: 185, TSLA: 245, JPM: 195, V: 280, JNJ: 155,
  };
  const basePrice = basePrices[ticker] ?? 150;
  let price = basePrice * 0.85;

  const today = new Date();
  for (let i = 365; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);

    // Skip weekends
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const volatility = 0.025;
    const drift = 0.0008;
    const change = (Math.random() - 0.48 + drift) * volatility * price;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) * (1 + Math.random() * 0.015);
    const low = Math.min(open, close) * (1 - Math.random() * 0.015);

    data.push({
      time: date.toISOString().split("T")[0],
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume: Math.floor(Math.random() * 80000000) + 20000000,
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

// Filter data by time range
function _filterDataByRange(data: PricePoint[], range: TimeRange): PricePoint[] {
  if (range === "ALL" || data.length === 0) return data;

  const now = new Date();
  let cutoffDate: Date;

  switch (range) {
    case "1D":
      cutoffDate = new Date(now.setDate(now.getDate() - 1));
      break;
    case "1W":
      cutoffDate = new Date(now.setDate(now.getDate() - 7));
      break;
    case "1M":
      cutoffDate = new Date(now.setMonth(now.getMonth() - 1));
      break;
    case "3M":
      cutoffDate = new Date(now.setMonth(now.getMonth() - 3));
      break;
    case "6M":
      cutoffDate = new Date(now.setMonth(now.getMonth() - 6));
      break;
    case "1Y":
      cutoffDate = new Date(now.setFullYear(now.getFullYear() - 1));
      break;
    default:
      return data;
  }

  const cutoffStr = cutoffDate.toISOString().split("T")[0];
  return data.filter((d) => d.time >= cutoffStr);
}

// Format price for display
function _formatPrice(price: number): string {
  return price.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

// Format volume for display
function _formatVolume(volume: number): string {
  if (volume >= 1_000_000_000) return (volume / 1_000_000_000).toFixed(2) + "B";
  if (volume >= 1_000_000) return (volume / 1_000_000).toFixed(2) + "M";
  if (volume >= 1_000) return (volume / 1_000).toFixed(1) + "K";
  return volume.toString();
}

export default function PriceChart({ ticker, data, height = 400, companyName }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [mounted, setMounted] = useState(false);
  const [timeRange, setTimeRange] = useState<TimeRange>("6M");
  const [hoveredData, setHoveredData] = useState<{
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    change: number;
    changePercent: number;
  } | null>(null);

  const fullData = data ?? _generateMockData(ticker);

  useEffect(() => {
    setMounted(true);
  }, []);

  const updateChart = useCallback(() => {
    if (!chartRef.current || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    const filteredData = _filterDataByRange(fullData, timeRange);
    const theme = _getTheme();

    // Prepare candlestick data
    const candleData: CandlestickData<Time>[] = filteredData.map((d) => ({
      time: d.time as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    // Prepare volume data with colors based on price direction
    const volumeData = filteredData.map((d, i) => {
      const prevClose = i > 0 ? filteredData[i - 1].close : d.open;
      const isUp = d.close >= prevClose;
      return {
        time: d.time as Time,
        value: d.volume ?? 0,
        color: isUp ? theme.volumeUp : theme.volumeDown,
      };
    });

    candleSeriesRef.current.setData(candleData);
    volumeSeriesRef.current.setData(volumeData);
    chartRef.current.timeScale().fitContent();
  }, [fullData, timeRange]);

  useEffect(() => {
    if (!mounted || !chartContainerRef.current) return;

    const container = chartContainerRef.current;
    const theme = _getTheme();

    // Calculate heights (main chart 75%, volume 25%)
    const mainHeight = Math.floor(height * 0.75);
    const volumeHeight = height - mainHeight;

    // Create chart
    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: theme.background },
        textColor: theme.text,
      },
      grid: {
        vertLines: { color: theme.grid, style: 1 },
        horzLines: { color: theme.grid, style: 1 },
      },
      width: container.clientWidth,
      height,
      rightPriceScale: {
        borderColor: theme.border,
        scaleMargins: { top: 0.1, bottom: 0.25 },
      },
      timeScale: {
        borderColor: theme.border,
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: 1, // Normal
        vertLine: {
          color: theme.crosshair,
          width: 1,
          style: 2,
          labelBackgroundColor: "#475569",
        },
        horzLine: {
          color: theme.crosshair,
          width: 1,
          style: 2,
          labelBackgroundColor: "#475569",
        },
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: true,
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: theme.upColor,
      downColor: theme.downColor,
      borderUpColor: theme.upColor,
      borderDownColor: theme.downColor,
      wickUpColor: theme.upColor,
      wickDownColor: theme.downColor,
      priceScaleId: "right",
    });
    candleSeriesRef.current = candlestickSeries;

    // Add volume histogram series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volumeSeriesRef.current = volumeSeries;

    // Configure volume scale
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
      borderVisible: false,
    });

    // Set initial data immediately after chart creation
    const filteredData = _filterDataByRange(fullData, timeRange);
    const candleData: CandlestickData<Time>[] = filteredData.map((d) => ({
      time: d.time as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    const volumeData = filteredData.map((d, i) => {
      const prevClose = i > 0 ? filteredData[i - 1].close : d.open;
      const isUp = d.close >= prevClose;
      return {
        time: d.time as Time,
        value: d.volume ?? 0,
        color: isUp ? theme.volumeUp : theme.volumeDown,
      };
    });
    candlestickSeries.setData(candleData);
    volumeSeries.setData(volumeData);
    chart.timeScale().fitContent();

    // Subscribe to crosshair move for tooltip
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setHoveredData(null);
        return;
      }

      const candleData = param.seriesData.get(candlestickSeries) as CandlestickData<Time> | undefined;
      const volumeData = param.seriesData.get(volumeSeries) as { value: number } | undefined;

      if (candleData) {
        const timeStr = param.time as string;
        const dataPoint = fullData.find((d) => d.time === timeStr);
        const prevPoint = fullData.find((d, i) => fullData[i + 1]?.time === timeStr);
        const prevClose = prevPoint?.close ?? candleData.open;
        const change = candleData.close - prevClose;
        const changePercent = (change / prevClose) * 100;

        setHoveredData({
          time: timeStr,
          open: candleData.open,
          high: candleData.high,
          low: candleData.low,
          close: candleData.close,
          volume: volumeData?.value ?? dataPoint?.volume ?? 0,
          change,
          changePercent,
        });
      }
    });

    // Handle resize
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (width > 0) {
          chart.applyOptions({ width });
        }
      }
    });
    resizeObserver.observe(container);

    // Watch for theme changes
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
        rightPriceScale: { borderColor: newTheme.border },
        timeScale: { borderColor: newTheme.border },
      });
      candlestickSeries.applyOptions({
        upColor: newTheme.upColor,
        downColor: newTheme.downColor,
        borderUpColor: newTheme.upColor,
        borderDownColor: newTheme.downColor,
        wickUpColor: newTheme.upColor,
        wickDownColor: newTheme.downColor,
      });
      // Refresh volume colors
      updateChart();
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    // Cleanup
    return () => {
      resizeObserver.disconnect();
      themeObserver.disconnect();
      chart.remove();
    };
  }, [mounted, height, fullData, timeRange]);

  // Update chart when time range changes
  useEffect(() => {
    updateChart();
  }, [timeRange, updateChart]);

  // Calculate current stats from latest data
  const latestData = fullData[fullData.length - 1];
  const prevData = fullData[fullData.length - 2];
  const currentChange = latestData && prevData ? latestData.close - prevData.close : 0;
  const currentChangePercent = prevData ? (currentChange / prevData.close) * 100 : 0;

  // Loading placeholder
  if (!mounted) {
    return (
      <div
        className="bg-bg-surface rounded-lg animate-pulse flex items-center justify-center"
        style={{ height: height + 60 }}
      >
        <span className="text-text-secondary text-sm">Loading chart...</span>
      </div>
    );
  }

  const displayData = hoveredData ?? {
    time: latestData?.time ?? "",
    open: latestData?.open ?? 0,
    high: latestData?.high ?? 0,
    low: latestData?.low ?? 0,
    close: latestData?.close ?? 0,
    volume: latestData?.volume ?? 0,
    change: currentChange,
    changePercent: currentChangePercent,
  };

  const isPositive = displayData.change >= 0;

  return (
    <div className="space-y-3">
      {/* Header with OHLC data */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-text-primary">
              {_formatPrice(displayData.close)}
            </span>
            <span className={`text-sm font-medium ${isPositive ? "text-success" : "text-danger"}`}>
              {isPositive ? "+" : ""}{displayData.change.toFixed(2)} ({isPositive ? "+" : ""}{displayData.changePercent.toFixed(2)}%)
            </span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-secondary mt-1">
            <span>O: {_formatPrice(displayData.open)}</span>
            <span>H: {_formatPrice(displayData.high)}</span>
            <span>L: {_formatPrice(displayData.low)}</span>
            <span>Vol: {_formatVolume(displayData.volume)}</span>
            {displayData.time && (
              <span className="text-text-muted">
                {new Date(displayData.time).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </span>
            )}
          </div>
        </div>

        {/* Time range selector */}
        <div className="flex gap-1 bg-bg-surface rounded-lg p-1">
          {(["1W", "1M", "3M", "6M", "1Y", "ALL"] as TimeRange[]).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                timeRange === range
                  ? "bg-accent text-white"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-elevated"
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Chart container */}
      <div
        ref={chartContainerRef}
        className="w-full rounded-lg overflow-hidden"
        style={{ height }}
      />
    </div>
  );
}
