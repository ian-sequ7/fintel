import { useEffect, useState } from "react";
import type {
  PaperTrade,
  TradePerformance,
  PortfolioSummary,
  StockDetail,
} from "../../data/types";
import {
  getPaperTrades,
  closeTrade,
  deleteTrade,
  calculateTradePerformance,
  calculatePortfolioSummary,
} from "../../data/portfolio";

interface PortfolioViewProps {
  stockDetails: Record<string, StockDetail>;
}

export default function PortfolioView({ stockDetails }: PortfolioViewProps) {
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [activeTab, setActiveTab] = useState<"open" | "closed">("open");
  const [mounted, setMounted] = useState(false);

  // Get current price for a ticker
  const getCurrentPrice = (ticker: string): number | null => {
    const detail = stockDetails[ticker];
    return detail?.currentPrice ?? null;
  };

  // Refresh data from localStorage
  const refreshData = () => {
    const allTrades = getPaperTrades();
    setTrades(allTrades);
    setSummary(calculatePortfolioSummary(getCurrentPrice));
  };

  useEffect(() => {
    setMounted(true);
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
      </div>

      {/* Trade List */}
      {displayTrades.length === 0 ? (
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

function EmptyState({ tab }: { tab: "open" | "closed" }) {
  return (
    <div className="text-center py-12 bg-bg-surface border border-border rounded-lg">
      <div className="text-4xl mb-4">{tab === "open" ? "📊" : "📈"}</div>
      <p className="text-text-secondary">
        {tab === "open"
          ? "No open positions. Visit a stock page to start paper trading!"
          : "No closed trades yet. Close an open position to see it here."}
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
