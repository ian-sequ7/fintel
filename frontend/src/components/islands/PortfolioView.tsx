import { useEffect, useState, useMemo, useCallback } from "react";
import type {
  PaperTrade,
  TradePerformance,
  PortfolioSummary,
  StockDetail,
  Sector,
} from "../../data/types";
import {
  getPaperTrades,
  closeTrade,
  deleteTrade,
  calculateTradePerformance,
  calculatePortfolioSummary,
} from "../../data/portfolio";
import { getStockDetails } from "../../data/lazy";

interface PortfolioViewProps {
  stockDetails?: Record<string, StockDetail>;
}

// =============================================================================
// Portfolio Analytics Types
// =============================================================================

interface PortfolioAnalytics {
  beta: number | null;
  sectorAllocation: Record<string, { value: number; percent: number }>;
  concentrationWarnings: { ticker: string; percent: number }[];
  taxLossHarvesting: { ticker: string; loss: number; holdingDays: number; isLongTerm: boolean }[];
  holdingPeriods: { shortTerm: number; longTerm: number };
  sharpeRatio: number | null;
  meanReversionAlerts: { ticker: string; deviation: number; direction: "oversold" | "overbought" }[];
}

// =============================================================================
// Analytics Calculations
// =============================================================================

function calculatePortfolioAnalytics(
  trades: PaperTrade[],
  stockDetails: Record<string, StockDetail>,
  getCurrentPrice: (ticker: string) => number | null
): PortfolioAnalytics {
  const openTrades = trades.filter((t) => t.status === "open");
  const now = new Date();
  const ONE_YEAR_MS = 365 * 24 * 60 * 60 * 1000;

  // Calculate position values
  const positions = openTrades.map((trade) => {
    const currentPrice = getCurrentPrice(trade.ticker) ?? trade.entryPrice;
    const value = trade.shares * currentPrice;
    const pnl = (currentPrice - trade.entryPrice) * trade.shares;
    const detail = stockDetails[trade.ticker];
    const holdingDays = Math.floor((now.getTime() - new Date(trade.entryDate).getTime()) / (24 * 60 * 60 * 1000));
    const isLongTerm = holdingDays >= 365;

    return {
      ticker: trade.ticker,
      value,
      pnl,
      pnlPercent: ((currentPrice - trade.entryPrice) / trade.entryPrice) * 100,
      beta: detail?.fundamentals?.beta ?? null,
      sector: detail?.sector ?? "unknown",
      holdingDays,
      isLongTerm,
      entryPrice: trade.entryPrice,
      currentPrice,
      priceHistory: detail?.priceHistory ?? [],
    };
  });

  const totalValue = positions.reduce((sum, p) => sum + p.value, 0);

  // 1. Portfolio Beta (value-weighted)
  let beta: number | null = null;
  if (totalValue > 0) {
    const betaSum = positions.reduce((sum, p) => {
      if (p.beta !== null) {
        return sum + p.beta * (p.value / totalValue);
      }
      return sum;
    }, 0);
    const betaWeight = positions.reduce((sum, p) => {
      if (p.beta !== null) {
        return sum + p.value / totalValue;
      }
      return sum;
    }, 0);
    if (betaWeight > 0.5) {
      beta = betaSum / betaWeight;
    }
  }

  // 2. Sector Allocation
  const sectorAllocation: Record<string, { value: number; percent: number }> = {};
  positions.forEach((p) => {
    const sector = p.sector || "unknown";
    if (!sectorAllocation[sector]) {
      sectorAllocation[sector] = { value: 0, percent: 0 };
    }
    sectorAllocation[sector].value += p.value;
  });
  Object.keys(sectorAllocation).forEach((sector) => {
    sectorAllocation[sector].percent = totalValue > 0
      ? (sectorAllocation[sector].value / totalValue) * 100
      : 0;
  });

  // 3. Concentration Warnings (>20% in single position)
  const concentrationWarnings = positions
    .map((p) => ({
      ticker: p.ticker,
      percent: totalValue > 0 ? (p.value / totalValue) * 100 : 0,
    }))
    .filter((p) => p.percent > 20)
    .sort((a, b) => b.percent - a.percent);

  // 4. Tax-Loss Harvesting Opportunities (negative P&L)
  const taxLossHarvesting = positions
    .filter((p) => p.pnl < 0)
    .map((p) => ({
      ticker: p.ticker,
      loss: Math.abs(p.pnl),
      holdingDays: p.holdingDays,
      isLongTerm: p.isLongTerm,
    }))
    .sort((a, b) => b.loss - a.loss);

  // 5. Holding Period Summary
  const holdingPeriods = {
    shortTerm: positions.filter((p) => !p.isLongTerm).length,
    longTerm: positions.filter((p) => p.isLongTerm).length,
  };

  // 6. Sharpe Ratio (simplified: using portfolio return / volatility estimate)
  let sharpeRatio: number | null = null;
  if (totalValue > 0 && positions.length > 0) {
    const avgReturn = positions.reduce((sum, p) => sum + p.pnlPercent, 0) / positions.length;
    const variance = positions.reduce((sum, p) => sum + Math.pow(p.pnlPercent - avgReturn, 2), 0) / positions.length;
    const volatility = Math.sqrt(variance);
    if (volatility > 0) {
      // Assuming risk-free rate of ~5%
      sharpeRatio = (avgReturn - 5) / volatility;
    }
  }

  // 7. Mean Reversion Alerts (stocks far from their 50-day moving average)
  const meanReversionAlerts: { ticker: string; deviation: number; direction: "oversold" | "overbought" }[] = [];
  positions.forEach((p) => {
    if (p.priceHistory.length >= 50) {
      const recent50 = p.priceHistory.slice(-50);
      const ma50 = recent50.reduce((sum, d) => sum + d.close, 0) / 50;
      const deviation = ((p.currentPrice - ma50) / ma50) * 100;

      // Alert if >10% deviation from MA50
      if (Math.abs(deviation) > 10) {
        meanReversionAlerts.push({
          ticker: p.ticker,
          deviation,
          direction: deviation < 0 ? "oversold" : "overbought",
        });
      }
    }
  });
  meanReversionAlerts.sort((a, b) => Math.abs(b.deviation) - Math.abs(a.deviation));

  return {
    beta,
    sectorAllocation,
    concentrationWarnings,
    taxLossHarvesting,
    holdingPeriods,
    sharpeRatio,
    meanReversionAlerts,
  };
}

export default function PortfolioView({ stockDetails: initialStockDetails }: PortfolioViewProps) {
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [activeTab, setActiveTab] = useState<"open" | "closed" | "insights">("open");
  const [mounted, setMounted] = useState(false);
  const [stockDetails, setStockDetails] = useState<Record<string, StockDetail>>(initialStockDetails ?? {});
  const [loading, setLoading] = useState(!initialStockDetails);

  // Get current price for a ticker (memoized to prevent analytics recalculation)
  const getCurrentPrice = useCallback((ticker: string): number | null => {
    const detail = stockDetails[ticker];
    return detail?.currentPrice ?? null;
  }, [stockDetails]);

  // Calculate analytics (memoized)
  const analytics = useMemo(() => {
    if (trades.length === 0 || loading) return null;
    return calculatePortfolioAnalytics(trades, stockDetails, getCurrentPrice);
  }, [trades, stockDetails, getCurrentPrice, loading]);

  // Refresh data from localStorage
  const refreshData = () => {
    const allTrades = getPaperTrades();
    setTrades(allTrades);
    setSummary(calculatePortfolioSummary(getCurrentPrice));
  };

  useEffect(() => {
    setMounted(true);

    // Lazy load stock details if not provided
    if (!initialStockDetails) {
      getStockDetails().then((data) => {
        setStockDetails(data);
        setLoading(false);
      });
    }

    refreshData();

    const handleUpdate = () => refreshData();
    window.addEventListener("portfolio-updated", handleUpdate);
    window.addEventListener("storage", handleUpdate);

    return () => {
      window.removeEventListener("portfolio-updated", handleUpdate);
      window.removeEventListener("storage", handleUpdate);
    };
  }, []);

  const handleCloseTrade = (id: string) => {
    const trade = trades.find((t) => t.id === id);
    if (!trade) return;

    const currentPrice = getCurrentPrice(trade.ticker);
    if (currentPrice === null) {
      alert(`Cannot get current price for ${trade.ticker}`);
      return;
    }

    if (confirm(`Close ${trade.ticker} position at $${currentPrice.toFixed(2)}?`)) {
      closeTrade(id, currentPrice);
      refreshData();
    }
  };

  const handleDeleteTrade = (id: string) => {
    if (confirm("Delete this trade? This cannot be undone.")) {
      deleteTrade(id);
      refreshData();
    }
  };

  if (!mounted) {
    return (
      <div className="animate-pulse">
        <div className="h-24 bg-bg-elevated rounded-lg mb-6"></div>
        <div className="h-64 bg-bg-elevated rounded-lg"></div>
      </div>
    );
  }

  const openTrades = trades.filter((t) => t.status === "open");
  const closedTrades = trades.filter((t) => t.status === "closed");
  const displayTrades = activeTab === "open" ? openTrades : closedTrades;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SummaryCard
            title="Portfolio Value"
            value={`$${summary.totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            subtitle={`Cost: $${summary.totalCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          />
          <SummaryCard
            title="Total P&L"
            value={`${summary.totalPnL >= 0 ? "+" : ""}$${summary.totalPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            subtitle={`${summary.totalPnLPercent >= 0 ? "+" : ""}${summary.totalPnLPercent.toFixed(2)}%`}
            valueColor={summary.totalPnL >= 0 ? "text-success" : "text-danger"}
          />
          <SummaryCard
            title="Open Positions"
            value={summary.openPositions.toString()}
            subtitle={`${summary.closedPositions} closed`}
          />
          <SummaryCard
            title="Win Rate"
            value={summary.closedPositions > 0 ? `${summary.winRate.toFixed(0)}%` : "—"}
            subtitle={summary.closedPositions > 0 ? `${summary.closedPositions} trades` : "No closed trades"}
          />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <TabButton
          active={activeTab === "open"}
          onClick={() => setActiveTab("open")}
          count={openTrades.length}
        >
          Open Positions
        </TabButton>
        <TabButton
          active={activeTab === "closed"}
          onClick={() => setActiveTab("closed")}
          count={closedTrades.length}
        >
          Closed Trades
        </TabButton>
        <TabButton
          active={activeTab === "insights"}
          onClick={() => setActiveTab("insights")}
          count={analytics ? Object.keys(analytics.sectorAllocation).length : 0}
        >
          Insights
        </TabButton>
      </div>

      {/* Tab Content */}
      {activeTab === "insights" ? (
        <PortfolioInsights analytics={analytics} />
      ) : displayTrades.length === 0 ? (
        <EmptyState tab={activeTab} />
      ) : (
        <div className="space-y-3">
          {displayTrades.map((trade) => {
            const price =
              trade.status === "closed"
                ? trade.exitPrice!
                : getCurrentPrice(trade.ticker);
            const perf = price
              ? calculateTradePerformance(trade, price)
              : null;

            return (
              <TradeCard
                key={trade.id}
                trade={trade}
                performance={perf}
                onClose={() => handleCloseTrade(trade.id)}
                onDelete={() => handleDeleteTrade(trade.id)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Sub-components
// =============================================================================

function SummaryCard({
  title,
  value,
  subtitle,
  valueColor = "text-text-primary",
}: {
  title: string;
  value: string;
  subtitle: string;
  valueColor?: string;
}) {
  return (
    <div className="bg-bg-surface border border-border rounded-lg p-4">
      <div className="text-sm text-text-secondary mb-1">{title}</div>
      <div className={`text-xl font-bold ${valueColor}`}>{value}</div>
      <div className="text-xs text-text-muted mt-1">{subtitle}</div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  count,
  children,
}: {
  active: boolean;
  onClick: () => void;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
        active
          ? "border-accent text-accent"
          : "border-transparent text-text-secondary hover:text-text-primary"
      }`}
    >
      {children}
      <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-bg-elevated">
        {count}
      </span>
    </button>
  );
}

function EmptyState({ tab }: { tab: "open" | "closed" | "insights" }) {
  return (
    <div className="text-center py-12 bg-bg-surface border border-border rounded-lg">
      <div className="text-4xl mb-4">{tab === "open" ? "📊" : tab === "closed" ? "📈" : "🔍"}</div>
      <p className="text-text-secondary">
        {tab === "open"
          ? "No open positions. Visit a stock page to start paper trading!"
          : tab === "closed"
          ? "No closed trades yet. Close an open position to see it here."
          : "Add some positions to see portfolio insights."}
      </p>
      {tab === "open" && (
        <a
          href="/picks"
          className="inline-block mt-4 px-4 py-2 bg-text-primary text-bg-base rounded hover:opacity-90 transition-opacity"
        >
          Browse Stock Picks
        </a>
      )}
    </div>
  );
}

// =============================================================================
// Portfolio Insights Component
// =============================================================================

function PortfolioInsights({ analytics }: { analytics: PortfolioAnalytics | null }) {
  if (!analytics) {
    return <EmptyState tab="insights" />;
  }

  const sectorEntries = Object.entries(analytics.sectorAllocation)
    .sort((a, b) => b[1].percent - a[1].percent);

  const sectorColors: Record<string, string> = {
    technology: "bg-blue-500",
    healthcare: "bg-green-500",
    finance: "bg-yellow-500",
    consumer: "bg-purple-500",
    energy: "bg-orange-500",
    industrials: "bg-gray-500",
    materials: "bg-teal-500",
    utilities: "bg-cyan-500",
    real_estate: "bg-pink-500",
    communications: "bg-indigo-500",
    unknown: "bg-slate-500",
  };

  return (
    <div className="space-y-6">
      {/* Risk Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <InsightCard
          title="Portfolio Beta"
          value={analytics.beta !== null ? analytics.beta.toFixed(2) : "—"}
          subtitle={analytics.beta !== null
            ? analytics.beta > 1 ? "Higher volatility than market" : "Lower volatility than market"
            : "Insufficient data"}
          icon="β"
          color={analytics.beta !== null && analytics.beta > 1.2 ? "text-warning" : "text-text-primary"}
        />
        <InsightCard
          title="Sharpe Ratio"
          value={analytics.sharpeRatio !== null ? analytics.sharpeRatio.toFixed(2) : "—"}
          subtitle={analytics.sharpeRatio !== null
            ? analytics.sharpeRatio > 1 ? "Good risk-adjusted return" : analytics.sharpeRatio > 0 ? "Positive return" : "Negative return"
            : "Insufficient data"}
          icon="📈"
          color={analytics.sharpeRatio !== null && analytics.sharpeRatio > 1 ? "text-success" : analytics.sharpeRatio !== null && analytics.sharpeRatio < 0 ? "text-danger" : "text-text-primary"}
        />
        <InsightCard
          title="Short-Term"
          value={analytics.holdingPeriods.shortTerm.toString()}
          subtitle="Positions < 1 year"
          icon="⏱️"
        />
        <InsightCard
          title="Long-Term"
          value={analytics.holdingPeriods.longTerm.toString()}
          subtitle="Positions > 1 year"
          icon="📅"
        />
      </div>

      {/* Concentration Warnings */}
      {analytics.concentrationWarnings.length > 0 && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-4">
          <h3 className="font-semibold text-warning mb-2 flex items-center gap-2">
            <span>⚠️</span> Concentration Warning
          </h3>
          <p className="text-sm text-text-secondary mb-2">
            The following positions exceed 20% of your portfolio:
          </p>
          <div className="flex flex-wrap gap-2">
            {analytics.concentrationWarnings.map((w) => (
              <span key={w.ticker} className="px-2 py-1 bg-warning/20 text-warning rounded text-sm font-mono">
                {w.ticker}: {w.percent.toFixed(1)}%
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Sector Allocation */}
      <div className="bg-bg-surface border border-border rounded-lg p-4">
        <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
          <span>🎯</span> Sector Allocation
        </h3>
        <div className="space-y-2">
          {sectorEntries.map(([sector, data]) => (
            <div key={sector} className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${sectorColors[sector] || sectorColors.unknown}`}></div>
              <span className="text-sm text-text-secondary capitalize w-28">{sector.replace("_", " ")}</span>
              <div className="flex-1 bg-bg-elevated rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${sectorColors[sector] || sectorColors.unknown}`}
                  style={{ width: `${Math.min(data.percent, 100)}%` }}
                ></div>
              </div>
              <span className="text-sm font-mono text-text-primary w-16 text-right">{data.percent.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tax-Loss Harvesting Opportunities */}
      {analytics.taxLossHarvesting.length > 0 && (
        <div className="bg-bg-surface border border-border rounded-lg p-4">
          <h3 className="font-semibold text-text-primary mb-2 flex items-center gap-2">
            <span>💰</span> Tax-Loss Harvesting Opportunities
          </h3>
          <p className="text-xs text-text-secondary mb-3">
            Positions with unrealized losses that could offset gains
          </p>
          <div className="space-y-2">
            {analytics.taxLossHarvesting.slice(0, 5).map((t) => (
              <div key={t.ticker} className="flex items-center justify-between p-2 bg-bg-elevated rounded">
                <div className="flex items-center gap-3">
                  <a href={`/stock/${t.ticker}`} className="font-mono font-bold text-accent hover:underline">
                    {t.ticker}
                  </a>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${t.isLongTerm ? "bg-success/20 text-success" : "bg-warning/20 text-warning"}`}>
                    {t.isLongTerm ? "Long-term" : "Short-term"}
                  </span>
                  <span className="text-xs text-text-secondary">{t.holdingDays} days</span>
                </div>
                <span className="font-mono text-danger">
                  -${t.loss.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mean Reversion Alerts */}
      {analytics.meanReversionAlerts.length > 0 && (
        <div className="bg-bg-surface border border-border rounded-lg p-4">
          <h3 className="font-semibold text-text-primary mb-2 flex items-center gap-2">
            <span>📊</span> Mean Reversion Alerts
          </h3>
          <p className="text-xs text-text-secondary mb-3">
            Positions trading &gt;10% from their 50-day moving average
          </p>
          <div className="flex flex-wrap gap-2">
            {analytics.meanReversionAlerts.map((a) => (
              <div
                key={a.ticker}
                className={`px-3 py-2 rounded-lg border ${
                  a.direction === "oversold"
                    ? "bg-success/10 border-success/30"
                    : "bg-danger/10 border-danger/30"
                }`}
              >
                <div className="flex items-center gap-2">
                  <a href={`/stock/${a.ticker}`} className="font-mono font-bold text-accent hover:underline">
                    {a.ticker}
                  </a>
                  <span className={`text-xs ${a.direction === "oversold" ? "text-success" : "text-danger"}`}>
                    {a.direction === "oversold" ? "↓" : "↑"} {Math.abs(a.deviation).toFixed(1)}%
                  </span>
                </div>
                <div className="text-xs text-text-secondary mt-1">
                  {a.direction === "oversold" ? "Below" : "Above"} 50-day MA
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Alerts State */}
      {analytics.concentrationWarnings.length === 0 &&
       analytics.taxLossHarvesting.length === 0 &&
       analytics.meanReversionAlerts.length === 0 && (
        <div className="text-center py-8 text-text-secondary">
          <div className="text-4xl mb-2">✓</div>
          <p>No warnings or opportunities detected. Portfolio looks balanced!</p>
        </div>
      )}
    </div>
  );
}

function InsightCard({
  title,
  value,
  subtitle,
  icon,
  color = "text-text-primary",
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: string;
  color?: string;
}) {
  return (
    <div className="bg-bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{icon}</span>
        <span className="text-sm text-text-secondary">{title}</span>
      </div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-text-muted mt-1">{subtitle}</div>
    </div>
  );
}

function TradeCard({
  trade,
  performance,
  onClose,
  onDelete,
}: {
  trade: PaperTrade;
  performance: TradePerformance | null;
  onClose: () => void;
  onDelete: () => void;
}) {
  const isOpen = trade.status === "open";
  const pnlColor = performance
    ? performance.pnl >= 0
      ? "text-success"
      : "text-danger"
    : "text-text-muted";

  return (
    <div className="bg-bg-surface border border-border rounded-lg p-4 hover:border-accent/50 transition-colors">
      <div className="flex items-start justify-between">
        {/* Left: Stock info */}
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <a
              href={`/stock/${trade.ticker}`}
              className="font-bold text-accent hover:underline"
            >
              {trade.ticker}
            </a>
            <span className="text-sm text-text-secondary">
              {trade.companyName}
            </span>
            {!isOpen && (
              <span className="text-xs px-2 py-0.5 rounded bg-bg-elevated text-text-muted">
                CLOSED
              </span>
            )}
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-text-secondary">
            <span>{trade.shares} shares</span>
            <span>Entry: ${trade.entryPrice.toFixed(2)}</span>
            {!isOpen && trade.exitPrice && (
              <span>Exit: ${trade.exitPrice.toFixed(2)}</span>
            )}
            <span>
              {new Date(trade.entryDate).toLocaleDateString()}
              {trade.exitDate && ` → ${new Date(trade.exitDate).toLocaleDateString()}`}
            </span>
          </div>

          {trade.notes && (
            <p className="text-xs text-text-muted mt-2 italic">"{trade.notes}"</p>
          )}
        </div>

        {/* Right: P&L and actions */}
        <div className="text-right ml-4">
          {performance ? (
            <>
              <div className={`font-bold ${pnlColor}`}>
                {performance.pnl >= 0 ? "+" : ""}$
                {performance.pnl.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </div>
              <div className={`text-sm ${pnlColor}`}>
                {performance.pnlPercent >= 0 ? "+" : ""}
                {performance.pnlPercent.toFixed(2)}%
              </div>
              {isOpen && (
                <div className="text-xs text-text-muted mt-1">
                  ${performance.currentPrice.toFixed(2)} current
                </div>
              )}
            </>
          ) : (
            <div className="text-text-muted">Price unavailable</div>
          )}

          {/* Actions */}
          <div className="flex gap-2 mt-3 justify-end">
            {isOpen && (
              <button
                onClick={onClose}
                className="px-3 py-1 text-xs font-medium bg-text-primary text-bg-base rounded hover:opacity-90 transition-opacity"
              >
                Close
              </button>
            )}
            <button
              onClick={onDelete}
              className="px-3 py-1 text-xs font-medium text-danger hover:bg-danger/10 rounded transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
