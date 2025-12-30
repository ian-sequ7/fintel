/**
 * TypeScript types for financial dashboard data.
 * Comprehensive type definitions for the fintel frontend.
 */

// =============================================================================
// Core Types
// =============================================================================

export type Timeframe = "short" | "medium" | "long";
export type Severity = "low" | "medium" | "high";
export type Trend = "up" | "down" | "flat";
export type NewsCategory = "market" | "company" | "macro" | "earnings";
export type SortOption = "conviction" | "ticker" | "price" | "change";
export type Sector =
  | "technology"
  | "healthcare"
  | "finance"
  | "consumer"
  | "energy"
  | "industrials"
  | "materials"
  | "utilities"
  | "real_estate"
  | "communications";

// =============================================================================
// Price Data
// =============================================================================

export interface PricePoint {
  time: string; // YYYY-MM-DD format for lightweight-charts
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

// =============================================================================
// Stock Types
// =============================================================================

export interface StockPick {
  ticker: string;
  companyName: string;
  currentPrice: number;
  priceChange: number;
  priceChangePercent: number;
  convictionScore: number; // 0-1
  timeframe: Timeframe;
  thesis: string;
  riskFactors: string[];
  sector: Sector;
  entryPrice?: number;
  targetPrice?: number;
  stopLoss?: number;
  marketCap?: number;
  peRatio?: number;
  volume?: number;
}

export interface StockDetail extends StockPick {
  priceHistory: PricePoint[];
  relatedNews: NewsItem[];
  fundamentals: StockFundamentals;
}

export interface StockFundamentals {
  peTrailing?: number;
  peForward?: number;
  pegRatio?: number;
  priceToBook?: number;
  revenueGrowth?: number;
  profitMargin?: number;
  dividendYield?: number;
  beta?: number;
  fiftyTwoWeekHigh?: number;
  fiftyTwoWeekLow?: number;
  avgVolume?: number;
}

// =============================================================================
// Macro Types
// =============================================================================

export interface MacroIndicator {
  id: string;
  name: string;
  value: number;
  previousValue?: number;
  unit: string;
  trend: Trend;
  source: string;
  updatedAt: string; // ISO date string
  description?: string;
}

export interface MacroRisk {
  id: string;
  name: string;
  severity: Severity;
  description: string;
  affectedSectors: Sector[];
  likelihood?: number; // 0-1
  potentialImpact?: string;
}

export interface MacroContext {
  indicators: MacroIndicator[];
  risks: MacroRisk[];
  marketSentiment: Trend;
  lastUpdated: string;
}

// =============================================================================
// News Types
// =============================================================================

export interface NewsItem {
  id: string;
  headline: string;
  source: string;
  url: string;
  publishedAt: string; // ISO date string
  category: NewsCategory;
  relevanceScore: number; // 0-1
  tickersMentioned: string[];
  excerpt?: string;
  imageUrl?: string;
}

// =============================================================================
// Report Types (Root)
// =============================================================================

export interface FinancialReport {
  generatedAt: string; // ISO date string
  version: string;
  watchlist: string[];

  // Stock picks by timeframe
  picks: {
    short: StockPick[];
    medium: StockPick[];
    long: StockPick[];
  };

  // Detailed stock data with price history
  stockDetails: Record<string, StockDetail>;

  // Macro data
  macro: MacroContext;

  // News
  news: {
    market: NewsItem[];
    company: NewsItem[];
  };

  // Summary metrics
  summary: ReportSummary;
}

export interface ReportSummary {
  totalPicks: number;
  avgConviction: number;
  topSector: Sector;
  highRiskCount: number;
  newsCount: number;
  marketTrend: Trend;
}

// =============================================================================
// Filter/Sort Types
// =============================================================================

export interface FilterState {
  timeframe: Timeframe | "all";
  sector?: Sector;
  sortBy: SortOption;
  sortOrder: "asc" | "desc";
}

export interface NewsFilterState {
  category: NewsCategory | "all";
  ticker?: string;
}

// =============================================================================
// Legacy Types (for backwards compatibility)
// =============================================================================

/** @deprecated Use FinancialReport instead */
export interface ReportData {
  generated_at: string;
  watchlist: string[];
  macro_indicators: MacroIndicator[];
  macro_risks: MacroRisk[];
  short_term_picks: StockPick[];
  medium_term_picks: StockPick[];
  long_term_picks: StockPick[];
  market_news: NewsItem[];
  company_news: NewsItem[];
  stock_metrics?: Record<string, StockMetrics>;
}

/** @deprecated Use StockDetail.fundamentals instead */
export interface StockMetrics {
  ticker: string;
  price: number;
  previous_close: number;
  change: number;
  change_percent: number;
  volume: number;
  market_cap?: number;
  pe_trailing?: number;
  pe_forward?: number;
  peg_ratio?: number;
  revenue_growth?: number;
  profit_margin?: number;
}
