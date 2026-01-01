import { useEffect, useState } from "react";
import { _getCompareStocks, removeFromCompare, clearCompare, type CompareStock } from "./CompareManager";

interface StockDetail {
  ticker: string;
  companyName: string;
  currentPrice: number;
  priceChange: number;
  priceChangePercent: number;
  convictionScore: number;
  timeframe: string;
  thesis: string;
  sector: string;
  entryPrice?: number;
  targetPrice?: number;
  stopLoss?: number;
  marketCap?: number;
  fundamentals?: {
    peTrailing?: number;
    peForward?: number;
    fiftyTwoWeekHigh?: number;
    fiftyTwoWeekLow?: number;
    revenueGrowth?: number;
    profitMargin?: number;
    dividendYield?: number;
    beta?: number;
  };
}

interface Props {
  stockDetails: Record<string, StockDetail>;
}

function _formatPrice(price?: number): string {
  if (price === undefined) return "-";
  return `$${price.toFixed(2)}`;
}

function _formatPercent(value?: number): string {
  if (value === undefined) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function _formatLargeNumber(num?: number): string {
  if (num === undefined) return "-";
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  return `$${num.toFixed(0)}`;
}

function _getConvictionColor(score: number): string {
  if (score >= 0.7) return "text-success";
  if (score >= 0.4) return "text-warning";
  return "text-danger";
}

function _getChangeColor(change: number): string {
  return change >= 0 ? "text-success" : "text-danger";
}

export default function CompareView({ stockDetails }: Props) {
  const [stocks, setStocks] = useState<CompareStock[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setStocks(_getCompareStocks());

    const handleUpdate = () => setStocks(_getCompareStocks());
    window.addEventListener("compare-updated", handleUpdate);
    window.addEventListener("storage", handleUpdate);

    return () => {
      window.removeEventListener("compare-updated", handleUpdate);
      window.removeEventListener("storage", handleUpdate);
    };
  }, []);

  if (!mounted) {
    return (
      <div className="text-center py-12 text-text-secondary">
        Loading comparison...
      </div>
    );
  }

  if (stocks.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-6xl mb-4">📊</div>
        <h2 className="text-xl font-semibold text-text-primary mb-2">
          No stocks to compare
        </h2>
        <p className="text-text-secondary mb-4">
          Add stocks to compare by clicking the "Compare" button on any pick.
        </p>
        <a
          href="/picks"
          className="inline-block bg-accent text-white px-4 py-2 rounded font-medium hover:bg-accent/90 transition-colors"
        >
          Browse Picks
        </a>
      </div>
    );
  }

  const details = stocks
    .map((s) => stockDetails[s.ticker])
    .filter((d): d is StockDetail => d !== undefined);

  if (details.length === 0) {
    return (
      <div className="text-center py-12 text-text-secondary">
        Stock details not available. Please regenerate data.
      </div>
    );
  }

  // Metric rows for comparison
  const metrics = [
    {
      label: "Current Price",
      getValue: (d: StockDetail) => _formatPrice(d.currentPrice),
      getClass: () => "font-semibold",
    },
    {
      label: "Daily Change",
      getValue: (d: StockDetail) =>
        `${d.priceChange >= 0 ? "+" : ""}${d.priceChange.toFixed(2)} (${d.priceChangePercent >= 0 ? "+" : ""}${d.priceChangePercent.toFixed(2)}%)`,
      getClass: (d: StockDetail) => _getChangeColor(d.priceChange),
    },
    {
      label: "Conviction",
      getValue: (d: StockDetail) => `${Math.round(d.convictionScore * 100)}%`,
      getClass: (d: StockDetail) => _getConvictionColor(d.convictionScore),
    },
    {
      label: "Timeframe",
      getValue: (d: StockDetail) =>
        d.timeframe.charAt(0).toUpperCase() + d.timeframe.slice(1),
      getClass: () => "",
    },
    {
      label: "Sector",
      getValue: (d: StockDetail) =>
        d.sector.charAt(0).toUpperCase() + d.sector.slice(1).replace("_", " "),
      getClass: () => "",
    },
    { label: "divider", getValue: () => "", getClass: () => "" },
    {
      label: "Entry Price",
      getValue: (d: StockDetail) => _formatPrice(d.entryPrice),
      getClass: () => "",
    },
    {
      label: "Target Price",
      getValue: (d: StockDetail) => _formatPrice(d.targetPrice),
      getClass: () => "text-success",
    },
    {
      label: "Stop Loss",
      getValue: (d: StockDetail) => _formatPrice(d.stopLoss),
      getClass: () => "text-danger",
    },
    {
      label: "Upside to Target",
      getValue: (d: StockDetail) => {
        if (!d.targetPrice) return "-";
        const upside = ((d.targetPrice - d.currentPrice) / d.currentPrice) * 100;
        return `${upside >= 0 ? "+" : ""}${upside.toFixed(1)}%`;
      },
      getClass: (d: StockDetail) => {
        if (!d.targetPrice) return "";
        return d.targetPrice > d.currentPrice ? "text-success" : "text-danger";
      },
    },
    { label: "divider", getValue: () => "", getClass: () => "" },
    {
      label: "Market Cap",
      getValue: (d: StockDetail) => _formatLargeNumber(d.marketCap),
      getClass: () => "",
    },
    {
      label: "P/E (Trailing)",
      getValue: (d: StockDetail) => d.fundamentals?.peTrailing?.toFixed(1) ?? "-",
      getClass: () => "",
    },
    {
      label: "P/E (Forward)",
      getValue: (d: StockDetail) => d.fundamentals?.peForward?.toFixed(1) ?? "-",
      getClass: () => "",
    },
    {
      label: "52W High",
      getValue: (d: StockDetail) => _formatPrice(d.fundamentals?.fiftyTwoWeekHigh),
      getClass: () => "",
    },
    {
      label: "52W Low",
      getValue: (d: StockDetail) => _formatPrice(d.fundamentals?.fiftyTwoWeekLow),
      getClass: () => "",
    },
    {
      label: "Revenue Growth",
      getValue: (d: StockDetail) => _formatPercent(d.fundamentals?.revenueGrowth),
      getClass: (d: StockDetail) =>
        (d.fundamentals?.revenueGrowth ?? 0) > 0 ? "text-success" : "",
    },
    {
      label: "Profit Margin",
      getValue: (d: StockDetail) => _formatPercent(d.fundamentals?.profitMargin),
      getClass: (d: StockDetail) =>
        (d.fundamentals?.profitMargin ?? 0) > 0.1 ? "text-success" : "",
    },
    {
      label: "Dividend Yield",
      getValue: (d: StockDetail) => _formatPercent(d.fundamentals?.dividendYield),
      getClass: () => "",
    },
    {
      label: "Beta",
      getValue: (d: StockDetail) => d.fundamentals?.beta?.toFixed(2) ?? "-",
      getClass: () => "",
    },
  ];

  return (
    <div>
      {/* Header row with stock names */}
      <div className="flex items-center justify-end gap-2 mb-4">
        <button
          onClick={() => clearCompare()}
          className="text-sm text-text-muted hover:text-danger transition-colors"
        >
          Clear All
        </button>
      </div>

      <div className="bg-bg-surface border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left p-4 text-text-secondary font-medium text-sm w-40">
                  Metric
                </th>
                {details.map((d) => (
                  <th key={d.ticker} className="text-center p-4 min-w-[180px]">
                    <div className="flex flex-col items-center gap-1">
                      <a
                        href={`/stock/${d.ticker}`}
                        className="font-mono text-xl font-bold text-accent hover:underline"
                      >
                        {d.ticker}
                      </a>
                      <span className="text-sm text-text-secondary">
                        {d.companyName}
                      </span>
                      <button
                        onClick={() => removeFromCompare(d.ticker)}
                        className="text-xs text-text-muted hover:text-danger mt-1"
                      >
                        Remove
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((metric, idx) =>
                metric.label === "divider" ? (
                  <tr key={idx} className="bg-bg-elevated">
                    <td colSpan={details.length + 1} className="h-2" />
                  </tr>
                ) : (
                  <tr
                    key={metric.label}
                    className="border-b border-border last:border-0 hover:bg-bg-elevated/50"
                  >
                    <td className="p-3 text-sm text-text-secondary">
                      {metric.label}
                    </td>
                    {details.map((d) => (
                      <td
                        key={d.ticker}
                        className={`p-3 text-center text-sm ${metric.getClass(d)}`}
                      >
                        {metric.getValue(d)}
                      </td>
                    ))}
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Thesis comparison */}
      <div className="mt-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">
          Investment Thesis
        </h3>
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${details.length}, 1fr)` }}>
          {details.map((d) => (
            <div
              key={d.ticker}
              className="bg-bg-surface border border-border rounded-lg p-4"
            >
              <p className="font-mono font-bold text-accent mb-2">{d.ticker}</p>
              <p className="text-sm text-text-primary leading-relaxed">
                {d.thesis}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
