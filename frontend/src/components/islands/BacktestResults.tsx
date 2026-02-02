import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
  ColorType,
} from "lightweight-charts";
import type { AlgorithmBacktestResult } from "../../data/types";

interface Props {
  result: AlgorithmBacktestResult;
}

// Theme colors matching PriceChart
const LIGHT_THEME = {
  background: "#ffffff",
  text: "#64748b",
  grid: "#f1f5f9",
  border: "#e2e8f0",
  crosshair: "#94a3b8",
  lineColor: "#3b82f6",
};

const DARK_THEME = {
  background: "#1e293b",
  text: "#94a3b8",
  grid: "#334155",
  border: "#475569",
  crosshair: "#64748b",
  lineColor: "#3b82f6",
};

function _getTheme(): typeof LIGHT_THEME {
  if (typeof document === "undefined") return LIGHT_THEME;
  const theme = document.documentElement.dataset.theme;
  return theme === "dark" ? DARK_THEME : LIGHT_THEME;
}

function _formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function _formatCurrency(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

export default function BacktestResults({ result }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [mounted, setMounted] = useState(false);

  const { performance, signalBreakdown, trades } = result;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !chartContainerRef.current || result.equityCurve.length === 0) return;

    const container = chartContainerRef.current;
    const theme = _getTheme();
    const height = 300;

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

    // Add line series for equity curve
    const lineSeries = chart.addSeries(LineSeries, {
      color: theme.lineColor,
      lineWidth: 2,
      priceFormat: {
        type: "price",
        precision: 2,
        minMove: 0.01,
      },
    });
    lineSeriesRef.current = lineSeries;

    // Prepare equity curve data
    const equityData: LineData<Time>[] = result.equityCurve.map((point) => ({
      time: point.date as Time,
      value: point.value,
    }));

    lineSeries.setData(equityData);
    chart.timeScale().fitContent();

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
      lineSeries.applyOptions({
        color: newTheme.lineColor,
      });
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
  }, [mounted, result.equityCurve]);

  // Loading placeholder
  if (!mounted) {
    return (
      <div className="bg-bg-surface rounded-lg animate-pulse p-8 flex items-center justify-center">
        <span className="text-text-secondary text-sm">Loading results...</span>
      </div>
    );
  }

  const totalSignals = Object.values(signalBreakdown).reduce((sum, count) => sum + count, 0);

  return (
    <div className="space-y-6">
      {/* Key Metrics Grid */}
      <section>
        <h3 className="text-lg font-semibold text-text-primary mb-3">Performance Metrics</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Total Return</p>
            <p className={`text-xl font-bold ${performance.totalReturn >= 0 ? "text-success" : "text-danger"}`}>
              {_formatPercent(performance.totalReturn)}
            </p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Sharpe Ratio</p>
            <p className="text-xl font-bold text-text-primary">{performance.sharpeRatio.toFixed(2)}</p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Sortino Ratio</p>
            <p className="text-xl font-bold text-text-primary">{performance.sortinoRatio.toFixed(2)}</p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Max Drawdown</p>
            <p className="text-xl font-bold text-danger">{_formatPercent(performance.maxDrawdown)}</p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Win Rate</p>
            <p className="text-xl font-bold text-text-primary">{_formatPercent(performance.winRate)}</p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Profit Factor</p>
            <p className="text-xl font-bold text-text-primary">{performance.profitFactor.toFixed(2)}</p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Total Trades</p>
            <p className="text-xl font-bold text-text-primary">{performance.totalTrades}</p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Avg Holding</p>
            <p className="text-xl font-bold text-text-primary">{Math.round(performance.avgHoldingDays)}d</p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Alpha</p>
            <p className={`text-xl font-bold ${performance.alpha >= 0 ? "text-success" : "text-danger"}`}>
              {_formatPercent(performance.alpha)}
            </p>
          </div>

          <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Benchmark</p>
            <p className={`text-xl font-bold ${performance.benchmarkReturn >= 0 ? "text-success" : "text-danger"}`}>
              {_formatPercent(performance.benchmarkReturn)}
            </p>
          </div>
        </div>
      </section>

      {/* Equity Curve Chart */}
      <section>
        <h3 className="text-lg font-semibold text-text-primary mb-3">Equity Curve</h3>
        <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <div
            ref={chartContainerRef}
            className="w-full rounded-lg overflow-hidden"
            role="img"
            aria-label="Equity curve showing portfolio value over time"
          />
        </div>
      </section>

      {/* Signal Breakdown */}
      <section>
        <h3 className="text-lg font-semibold text-text-primary mb-3">Signal Breakdown</h3>
        <div className="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Long Entry</span>
              <div className="flex items-center gap-2">
                <div className="w-32 h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-success"
                    style={{ width: `${(signalBreakdown.longEntry / totalSignals) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-text-primary w-12 text-right">
                  {signalBreakdown.longEntry}
                </span>
              </div>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Long Exit</span>
              <div className="flex items-center gap-2">
                <div className="w-32 h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-700"
                    style={{ width: `${(signalBreakdown.longExit / totalSignals) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-text-primary w-12 text-right">
                  {signalBreakdown.longExit}
                </span>
              </div>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Short Entry</span>
              <div className="flex items-center gap-2">
                <div className="w-32 h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-danger"
                    style={{ width: `${(signalBreakdown.shortEntry / totalSignals) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-text-primary w-12 text-right">
                  {signalBreakdown.shortEntry}
                </span>
              </div>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Short Exit</span>
              <div className="flex items-center gap-2">
                <div className="w-32 h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-red-700"
                    style={{ width: `${(signalBreakdown.shortExit / totalSignals) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-text-primary w-12 text-right">
                  {signalBreakdown.shortExit}
                </span>
              </div>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Stop Loss</span>
              <div className="flex items-center gap-2">
                <div className="w-32 h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-orange-500"
                    style={{ width: `${(signalBreakdown.stopLoss / totalSignals) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-text-primary w-12 text-right">
                  {signalBreakdown.stopLoss}
                </span>
              </div>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Take Profit</span>
              <div className="flex items-center gap-2">
                <div className="w-32 h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500"
                    style={{ width: `${(signalBreakdown.takeProfit / totalSignals) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-text-primary w-12 text-right">
                  {signalBreakdown.takeProfit}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Recent Trades Table */}
      <section>
        <h3 className="text-lg font-semibold text-text-primary mb-3">
          Recent Trades (Last {Math.min(10, trades.length)})
        </h3>
        <div className="bg-bg-surface rounded-lg border border-border-subtle overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg-elevated border-b border-border-subtle">
                <tr>
                  <th className="text-left px-4 py-3 text-text-secondary font-medium">Ticker</th>
                  <th className="text-left px-4 py-3 text-text-secondary font-medium">Entry</th>
                  <th className="text-left px-4 py-3 text-text-secondary font-medium">Exit</th>
                  <th className="text-right px-4 py-3 text-text-secondary font-medium">Return</th>
                  <th className="text-right px-4 py-3 text-text-secondary font-medium">Days</th>
                  <th className="text-left px-4 py-3 text-text-secondary font-medium">Signal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {trades.slice(-10).reverse().map((trade, idx) => (
                  <tr key={idx} className="hover:bg-bg-elevated transition-colors">
                    <td className="px-4 py-3 font-medium text-text-primary">{trade.ticker}</td>
                    <td className="px-4 py-3 text-text-secondary">
                      {_formatCurrency(trade.entryPrice)}
                      <br />
                      <span className="text-xs text-text-muted">
                        {new Date(trade.entryDate).toLocaleDateString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {trade.exitPrice ? _formatCurrency(trade.exitPrice) : "—"}
                      {trade.exitDate && (
                        <>
                          <br />
                          <span className="text-xs text-text-muted">
                            {new Date(trade.exitDate).toLocaleDateString()}
                          </span>
                        </>
                      )}
                    </td>
                    <td className={`px-4 py-3 text-right font-medium ${
                      (trade.returnPct ?? 0) >= 0 ? "text-success" : "text-danger"
                    }`}>
                      {trade.returnPct ? _formatPercent(trade.returnPct) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right text-text-secondary">
                      {trade.holdingDays ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-text-secondary text-xs">
                      <span className="uppercase">{trade.entrySignal.replace("_", " ")}</span>
                      {trade.exitSignal && (
                        <>
                          <br />
                          <span className="text-text-muted uppercase">
                            → {trade.exitSignal.replace("_", " ")}
                          </span>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
