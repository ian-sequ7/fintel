import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries, type IChartApi, ColorType } from "lightweight-charts";

interface Props {
  data: { time: string; close: number }[];
  width?: number;
  height?: number;
  showChange?: boolean;
}

export default function Sparkline({ data, width = 100, height = 40, showChange = true }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !containerRef.current || data.length < 2) return;

    const container = containerRef.current;

    // Determine if trend is up or down
    const firstPrice = data[0].close;
    const lastPrice = data[data.length - 1].close;
    const isPositive = lastPrice >= firstPrice;
    const lineColor = isPositive ? "#22c55e" : "#ef4444";

    // Create minimal chart
    const chart = createChart(container, {
      width,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "transparent",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: {
        vertLine: { visible: false },
        horzLine: { visible: false },
      },
      handleScroll: false,
      handleScale: false,
    });

    chartRef.current = chart;

    // Add line series
    const lineSeries = chart.addSeries(LineSeries, {
      color: lineColor,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Set data (use last 30 days for sparkline)
    const sparkData = data.slice(-30).map((d) => ({
      time: d.time,
      value: d.close,
    }));
    lineSeries.setData(sparkData);

    // Fit content
    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [mounted, data, width, height]);

  if (!mounted || data.length < 2) {
    return (
      <div
        className="bg-bg-surface/50 rounded animate-pulse"
        style={{ width, height }}
      />
    );
  }

  // Calculate change
  const firstPrice = data[0].close;
  const lastPrice = data[data.length - 1].close;
  const change = lastPrice - firstPrice;
  const changePercent = (change / firstPrice) * 100;
  const isPositive = change >= 0;

  return (
    <div className="flex items-center gap-2">
      <div ref={containerRef} style={{ width, height }} />
      {showChange && (
        <span className={`text-xs font-medium ${isPositive ? "text-success" : "text-danger"}`}>
          {isPositive ? "+" : ""}{changePercent.toFixed(1)}%
        </span>
      )}
    </div>
  );
}
