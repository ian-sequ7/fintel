import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
  ColorType,
  LineStyle,
} from "lightweight-charts";
import { rsi, macd, bollingerBands, sma } from "../../data/indicators";
import type { AlgorithmSignal, PrecomputedIndicators } from "../../data/types";

interface PricePoint {
  time: string; // YYYY-MM-DD format
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface IndicatorChartProps {
  ticker: string;
  data?: PricePoint[];
  height?: number;
  companyName?: string;
  // Indicator toggles
  showRSI?: boolean;
  showMACD?: boolean;
  showBollingerBands?: boolean;
  showSMA50?: boolean;
  showSMA200?: boolean;
  // Signal markers
  signals?: AlgorithmSignal[];
  // Pre-computed indicators from server (preferred over calculation)
  indicators?: PrecomputedIndicators;
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
  // Indicator colors
  rsi: "#a855f7",
  macdLine: "#3b82f6",
  macdSignal: "#f59e0b",
  macdHistogramPos: "rgba(34, 197, 94, 0.5)",
  macdHistogramNeg: "rgba(239, 68, 68, 0.5)",
  bbUpper: "#9ca3af",
  bbMiddle: "#eab308",
  bbLower: "#9ca3af",
  sma50: "#3b82f6",
  sma200: "#ef4444",
  buySignal: "#22c55e",
  sellSignal: "#ef4444",
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
  // Indicator colors
  rsi: "#a855f7",
  macdLine: "#3b82f6",
  macdSignal: "#f59e0b",
  macdHistogramPos: "rgba(34, 197, 94, 0.5)",
  macdHistogramNeg: "rgba(239, 68, 68, 0.5)",
  bbUpper: "#6b7280",
  bbMiddle: "#eab308",
  bbLower: "#6b7280",
  sma50: "#3b82f6",
  sma200: "#ef4444",
  buySignal: "#22c55e",
  sellSignal: "#ef4444",
};

function _getTheme(): typeof LIGHT_THEME {
  if (typeof document === "undefined") return LIGHT_THEME;
  const theme = document.documentElement.dataset.theme;
  return theme === "dark" ? DARK_THEME : LIGHT_THEME;
}

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

function _formatPrice(price: number): string {
  return price.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function _formatVolume(volume: number): string {
  if (volume >= 1_000_000_000) return (volume / 1_000_000_000).toFixed(2) + "B";
  if (volume >= 1_000_000) return (volume / 1_000_000).toFixed(2) + "M";
  if (volume >= 1_000) return (volume / 1_000).toFixed(1) + "K";
  return volume.toString();
}

export default function IndicatorChart({
  ticker,
  data = [],
  height = 400,
  companyName,
  showRSI = false,
  showMACD = false,
  showBollingerBands = false,
  showSMA50 = false,
  showSMA200 = false,
  signals = [],
  indicators,
}: IndicatorChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Indicator series refs
  const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbMiddleRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null);
  const sma50Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma200Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdLineRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistogramRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const [mounted, setMounted] = useState(false);
  const [timeRange, setTimeRange] = useState<TimeRange>("6M");
  const [indicatorToggles, setIndicatorToggles] = useState({
    rsi: showRSI,
    macd: showMACD,
    bb: showBollingerBands,
    sma50: showSMA50,
    sma200: showSMA200,
  });
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

  const fullData = data;

  // Calculate dynamic height based on enabled panes
  const rsiHeight = 100;
  const macdHeight = 100;
  const mainChartHeight =
    height + (indicatorToggles.rsi ? rsiHeight : 0) + (indicatorToggles.macd ? macdHeight : 0);

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

    // Prepare volume data
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

    // Calculate and update indicators
    // Use pre-computed if available (from server), otherwise calculate
    const closes = filteredData.map((d) => d.close);

    // Helper to map indicator values to chart data with correct time alignment
    const mapIndicatorToChartData = (values: (number | null)[], sourceData: PricePoint[]) => {
      return values
        .map((val, i) => (val !== null ? { time: sourceData[i].time as Time, value: val } : null))
        .filter((d): d is { time: Time; value: number } => d !== null);
    };

    // Bollinger Bands
    if (indicatorToggles.bb && bbUpperRef.current && bbMiddleRef.current && bbLowerRef.current) {
      if (indicators) {
        // Use pre-computed from server
        bbUpperRef.current.setData(mapIndicatorToChartData(indicators.bbUpper, fullData));
        bbMiddleRef.current.setData(mapIndicatorToChartData(indicators.bbMiddle, fullData));
        bbLowerRef.current.setData(mapIndicatorToChartData(indicators.bbLower, fullData));
      } else {
        // Fallback to calculation
        const bb = bollingerBands(closes);
        bbUpperRef.current.setData(mapIndicatorToChartData(bb.upper, filteredData));
        bbMiddleRef.current.setData(mapIndicatorToChartData(bb.middle, filteredData));
        bbLowerRef.current.setData(mapIndicatorToChartData(bb.lower, filteredData));
      }
    }

    // SMA 50
    if (indicatorToggles.sma50 && sma50Ref.current) {
      const sma50Data = indicators?.sma50 ?? sma(closes, 50);
      const sourceData = indicators ? fullData : filteredData;
      sma50Ref.current.setData(mapIndicatorToChartData(sma50Data, sourceData));
    }

    // SMA 200
    if (indicatorToggles.sma200 && sma200Ref.current) {
      const sma200Data = indicators?.sma200 ?? sma(closes, 200);
      const sourceData = indicators ? fullData : filteredData;
      sma200Ref.current.setData(mapIndicatorToChartData(sma200Data, sourceData));
    }

    // RSI
    if (indicatorToggles.rsi && rsiSeriesRef.current) {
      const rsiData = indicators?.rsi ?? rsi(closes);
      const sourceData = indicators ? fullData : filteredData;
      rsiSeriesRef.current.setData(mapIndicatorToChartData(rsiData, sourceData));
    }

    // MACD
    if (indicatorToggles.macd && macdLineRef.current && macdSignalRef.current && macdHistogramRef.current) {
      if (indicators) {
        // Use pre-computed from server
        macdLineRef.current.setData(mapIndicatorToChartData(indicators.macdLine, fullData));
        macdSignalRef.current.setData(mapIndicatorToChartData(indicators.macdSignal, fullData));
        macdHistogramRef.current.setData(
          indicators.macdHistogram
            .map((val, i) =>
              val !== null
                ? {
                    time: fullData[i].time as Time,
                    value: val,
                    color: val >= 0 ? theme.macdHistogramPos : theme.macdHistogramNeg,
                  }
                : null
            )
            .filter((d): d is { time: Time; value: number; color: string } => d !== null)
        );
      } else {
        // Fallback to calculation
        const macdData = macd(closes);
        macdLineRef.current.setData(mapIndicatorToChartData(macdData.line, filteredData));
        macdSignalRef.current.setData(mapIndicatorToChartData(macdData.signal, filteredData));
        macdHistogramRef.current.setData(
          macdData.histogram
            .map((val, i) =>
              val !== null
                ? {
                    time: filteredData[i].time as Time,
                    value: val,
                    color: val >= 0 ? theme.macdHistogramPos : theme.macdHistogramNeg,
                  }
                : null
            )
            .filter((d): d is { time: Time; value: number } => d !== null)
        );
      }
    }

    chartRef.current.timeScale().fitContent();
  }, [fullData, timeRange, indicatorToggles]);

  useEffect(() => {
    if (!mounted || !chartContainerRef.current) return;

    const container = chartContainerRef.current;
    const theme = _getTheme();

    // Calculate main price pane margins based on enabled sub-panes
    let bottomMargin = 0.25; // Default for volume
    if (indicatorToggles.rsi && indicatorToggles.macd) {
      bottomMargin = 0.45;
    } else if (indicatorToggles.rsi || indicatorToggles.macd) {
      bottomMargin = 0.35;
    }

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
      height: mainChartHeight,
      rightPriceScale: {
        borderColor: theme.border,
        scaleMargins: { top: 0.1, bottom: bottomMargin },
      },
      timeScale: {
        borderColor: theme.border,
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: 1,
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

    // Add volume histogram
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volumeSeriesRef.current = volumeSeries;

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
      borderVisible: false,
    });

    // Add main chart overlays
    if (indicatorToggles.bb) {
      bbUpperRef.current = chart.addSeries(LineSeries, {
        color: theme.bbUpper,
        lineWidth: 1,
        priceScaleId: "right",
      });
      bbMiddleRef.current = chart.addSeries(LineSeries, {
        color: theme.bbMiddle,
        lineWidth: 2,
        priceScaleId: "right",
      });
      bbLowerRef.current = chart.addSeries(LineSeries, {
        color: theme.bbLower,
        lineWidth: 1,
        priceScaleId: "right",
      });
    }

    if (indicatorToggles.sma50) {
      sma50Ref.current = chart.addSeries(LineSeries, {
        color: theme.sma50,
        lineWidth: 2,
        priceScaleId: "right",
      });
    }

    if (indicatorToggles.sma200) {
      sma200Ref.current = chart.addSeries(LineSeries, {
        color: theme.sma200,
        lineWidth: 2,
        priceScaleId: "right",
      });
    }

    // Add RSI pane
    if (indicatorToggles.rsi) {
      rsiSeriesRef.current = chart.addSeries(LineSeries, {
        color: theme.rsi,
        lineWidth: 2,
        priceScaleId: "rsi",
      });

      chart.priceScale("rsi").applyOptions({
        scaleMargins: indicatorToggles.macd
          ? { top: 0.75, bottom: 0.25 }
          : { top: 0.75, bottom: 0.05 },
        borderVisible: false,
      });
    }

    // Add MACD pane
    if (indicatorToggles.macd) {
      macdLineRef.current = chart.addSeries(LineSeries, {
        color: theme.macdLine,
        lineWidth: 2,
        priceScaleId: "macd",
      });
      macdSignalRef.current = chart.addSeries(LineSeries, {
        color: theme.macdSignal,
        lineWidth: 2,
        priceScaleId: "macd",
      });
      macdHistogramRef.current = chart.addSeries(HistogramSeries, {
        priceScaleId: "macd",
      });

      chart.priceScale("macd").applyOptions({
        scaleMargins: { top: 0.9, bottom: 0 },
        borderVisible: false,
      });
    }

    // Set initial data
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

    // Subscribe to crosshair move
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
  }, [mounted, mainChartHeight, fullData, timeRange, indicatorToggles]);

  useEffect(() => {
    updateChart();
  }, [timeRange, updateChart]);

  const toggleIndicator = (indicator: keyof typeof indicatorToggles) => {
    setIndicatorToggles((prev) => ({
      ...prev,
      [indicator]: !prev[indicator],
    }));
  };

  // Calculate current stats
  const latestData = fullData[fullData.length - 1];
  const prevData = fullData[fullData.length - 2];
  const currentChange = latestData && prevData ? latestData.close - prevData.close : 0;
  const currentChangePercent = prevData ? (currentChange / prevData.close) * 100 : 0;

  if (!mounted) {
    return (
      <div
        className="bg-bg-surface rounded-lg animate-pulse flex items-center justify-center"
        style={{ height: mainChartHeight + 60 }}
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
      {/* Header with OHLC data and controls */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-text-primary">
              {_formatPrice(displayData.close)}
            </span>
            <span className={`text-sm font-medium ${isPositive ? "text-success" : "text-danger"}`}>
              {isPositive ? "+" : ""}
              {displayData.change.toFixed(2)} ({isPositive ? "+" : ""}
              {displayData.changePercent.toFixed(2)}%)
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
                  ? "bg-text-primary text-bg-base"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-elevated"
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Indicator toggles */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => toggleIndicator("bb")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            indicatorToggles.bb
              ? "bg-yellow-500/20 text-yellow-600 dark:text-yellow-400"
              : "bg-bg-surface text-text-secondary hover:bg-bg-elevated"
          }`}
        >
          Bollinger Bands
        </button>
        <button
          onClick={() => toggleIndicator("sma50")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            indicatorToggles.sma50
              ? "bg-blue-500/20 text-blue-600 dark:text-blue-400"
              : "bg-bg-surface text-text-secondary hover:bg-bg-elevated"
          }`}
        >
          SMA 50
        </button>
        <button
          onClick={() => toggleIndicator("sma200")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            indicatorToggles.sma200
              ? "bg-red-500/20 text-red-600 dark:text-red-400"
              : "bg-bg-surface text-text-secondary hover:bg-bg-elevated"
          }`}
        >
          SMA 200
        </button>
        <button
          onClick={() => toggleIndicator("rsi")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            indicatorToggles.rsi
              ? "bg-purple-500/20 text-purple-600 dark:text-purple-400"
              : "bg-bg-surface text-text-secondary hover:bg-bg-elevated"
          }`}
        >
          RSI
        </button>
        <button
          onClick={() => toggleIndicator("macd")}
          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
            indicatorToggles.macd
              ? "bg-blue-500/20 text-blue-600 dark:text-blue-400"
              : "bg-bg-surface text-text-secondary hover:bg-bg-elevated"
          }`}
        >
          MACD
        </button>
      </div>

      {/* Chart container */}
      <div
        ref={chartContainerRef}
        className="w-full rounded-lg overflow-hidden"
        style={{ height: mainChartHeight }}
        role="img"
        aria-label={`Interactive candlestick price chart for ${ticker}${
          companyName ? ` (${companyName})` : ""
        } with technical indicators`}
      />
    </div>
  );
}
