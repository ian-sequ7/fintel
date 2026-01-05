/**
 * Paper trading portfolio management.
 * Uses localStorage for persistence (single-user, client-side).
 */

import type {
  PaperTrade,
  TradePerformance,
  PortfolioSummary,
  TradeStatus,
} from "./types";

// =============================================================================
// Constants
// =============================================================================

const STORAGE_KEY = "fintel_paper_trades";

// =============================================================================
// Storage Helpers
// =============================================================================

function _generateId(): string {
  return `trade_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function _loadTrades(): PaperTrade[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    console.warn("Failed to load paper trades from localStorage");
    return [];
  }
}

function _saveTrades(trades: PaperTrade[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trades));
    // Dispatch custom event for React components to react
    window.dispatchEvent(new CustomEvent("portfolio-updated"));
  } catch (e) {
    console.error("Failed to save paper trades:", e);
  }
}

// =============================================================================
// CRUD Operations
// =============================================================================

/**
 * Get all paper trades.
 */
export function getPaperTrades(): PaperTrade[] {
  return _loadTrades();
}

/**
 * Get trades filtered by status.
 */
export function getTradesByStatus(status: TradeStatus): PaperTrade[] {
  return _loadTrades().filter((t) => t.status === status);
}

/**
 * Get open positions only.
 */
export function getOpenPositions(): PaperTrade[] {
  return getTradesByStatus("open");
}

/**
 * Get closed trades only.
 */
export function getClosedTrades(): PaperTrade[] {
  return getTradesByStatus("closed");
}

/**
 * Get a specific trade by ID.
 */
export function getTrade(id: string): PaperTrade | null {
  const trades = _loadTrades();
  return trades.find((t) => t.id === id) ?? null;
}

/**
 * Add a new paper trade.
 */
export function addPaperTrade(
  trade: Omit<PaperTrade, "id" | "status">
): PaperTrade {
  const trades = _loadTrades();
  const newTrade: PaperTrade = {
    ...trade,
    id: _generateId(),
    status: "open",
  };
  trades.push(newTrade);
  _saveTrades(trades);
  return newTrade;
}

/**
 * Close an open trade.
 */
export function closeTrade(id: string, exitPrice: number): PaperTrade | null {
  const trades = _loadTrades();
  const index = trades.findIndex((t) => t.id === id);

  if (index === -1) return null;

  const trade = trades[index];
  if (trade.status === "closed") {
    console.warn(`Trade ${id} is already closed`);
    return trade;
  }

  const closedTrade: PaperTrade = {
    ...trade,
    status: "closed",
    exitPrice,
    exitDate: new Date().toISOString(),
  };

  trades[index] = closedTrade;
  _saveTrades(trades);
  return closedTrade;
}

/**
 * Delete a trade (open or closed).
 */
export function deleteTrade(id: string): boolean {
  const trades = _loadTrades();
  const filtered = trades.filter((t) => t.id !== id);

  if (filtered.length === trades.length) return false;

  _saveTrades(filtered);
  return true;
}

/**
 * Update trade notes.
 */
export function updateTradeNotes(id: string, notes: string): PaperTrade | null {
  const trades = _loadTrades();
  const index = trades.findIndex((t) => t.id === id);

  if (index === -1) return null;

  trades[index] = { ...trades[index], notes };
  _saveTrades(trades);
  return trades[index];
}

// =============================================================================
// Analytics
// =============================================================================

/**
 * Calculate performance for a single trade.
 */
export function calculateTradePerformance(
  trade: PaperTrade,
  currentPrice: number
): TradePerformance {
  const effectivePrice = trade.status === "closed" ? trade.exitPrice! : currentPrice;
  const costBasis = trade.shares * trade.entryPrice;
  const marketValue = trade.shares * effectivePrice;
  const pnl = marketValue - costBasis;
  const pnlPercent = costBasis > 0 ? (pnl / costBasis) * 100 : 0;

  return {
    trade,
    currentPrice: effectivePrice,
    marketValue,
    costBasis,
    pnl,
    pnlPercent,
  };
}

/**
 * Calculate portfolio summary.
 * @param getCurrentPrice - Function to get current price for a ticker
 */
export function calculatePortfolioSummary(
  getCurrentPrice: (ticker: string) => number | null
): PortfolioSummary {
  const trades = _loadTrades();
  const openTrades = trades.filter((t) => t.status === "open");
  const closedTrades = trades.filter((t) => t.status === "closed");

  // Calculate open positions value
  let totalValue = 0;
  let totalCost = 0;
  let bestTrade: TradePerformance | undefined;
  let worstTrade: TradePerformance | undefined;

  const performances: TradePerformance[] = [];

  for (const trade of openTrades) {
    const price = getCurrentPrice(trade.ticker);
    if (price === null) continue;

    const perf = calculateTradePerformance(trade, price);
    performances.push(perf);
    totalValue += perf.marketValue;
    totalCost += perf.costBasis;

    if (!bestTrade || perf.pnlPercent > bestTrade.pnlPercent) {
      bestTrade = perf;
    }
    if (!worstTrade || perf.pnlPercent < worstTrade.pnlPercent) {
      worstTrade = perf;
    }
  }

  // Calculate closed trades for win rate
  let wins = 0;
  for (const trade of closedTrades) {
    const perf = calculateTradePerformance(trade, trade.exitPrice!);
    if (perf.pnl > 0) wins++;

    // Include closed trades in best/worst if more extreme
    if (!bestTrade || perf.pnlPercent > bestTrade.pnlPercent) {
      bestTrade = perf;
    }
    if (!worstTrade || perf.pnlPercent < worstTrade.pnlPercent) {
      worstTrade = perf;
    }
  }

  const winRate = closedTrades.length > 0 ? (wins / closedTrades.length) * 100 : 0;
  const totalPnL = totalValue - totalCost;
  const totalPnLPercent = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;

  return {
    totalValue,
    totalCost,
    totalPnL,
    totalPnLPercent,
    openPositions: openTrades.length,
    closedPositions: closedTrades.length,
    winRate,
    bestTrade,
    worstTrade,
  };
}

/**
 * Get all trade performances with current prices.
 */
export function getAllTradePerformances(
  getCurrentPrice: (ticker: string) => number | null
): TradePerformance[] {
  const trades = _loadTrades();
  const performances: TradePerformance[] = [];

  for (const trade of trades) {
    const price =
      trade.status === "closed"
        ? trade.exitPrice!
        : getCurrentPrice(trade.ticker);

    if (price === null) continue;
    performances.push(calculateTradePerformance(trade, price));
  }

  return performances;
}

/**
 * Check if user has any position in a ticker.
 */
export function hasPositionIn(ticker: string): boolean {
  const trades = _loadTrades();
  return trades.some(
    (t) => t.ticker.toUpperCase() === ticker.toUpperCase() && t.status === "open"
  );
}

/**
 * Get positions for a specific ticker.
 */
export function getPositionsForTicker(ticker: string): PaperTrade[] {
  const trades = _loadTrades();
  return trades.filter(
    (t) => t.ticker.toUpperCase() === ticker.toUpperCase() && t.status === "open"
  );
}

// =============================================================================
// Export/Import (Future)
// =============================================================================

/**
 * Export all trades as JSON string.
 */
export function exportTrades(): string {
  return JSON.stringify(_loadTrades(), null, 2);
}

/**
 * Import trades from JSON string (merges with existing).
 */
export function importTrades(json: string): number {
  try {
    const imported = JSON.parse(json) as PaperTrade[];
    const existing = _loadTrades();
    const existingIds = new Set(existing.map((t) => t.id));

    let added = 0;
    for (const trade of imported) {
      if (!existingIds.has(trade.id)) {
        existing.push(trade);
        added++;
      }
    }

    _saveTrades(existing);
    return added;
  } catch {
    console.error("Failed to import trades");
    return 0;
  }
}

/**
 * Clear all trades (use with caution).
 */
export function clearAllTrades(): void {
  _saveTrades([]);
}
