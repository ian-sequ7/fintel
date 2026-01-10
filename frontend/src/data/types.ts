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
  entryPrice?: number | null;
  targetPrice?: number | null;
  stopLoss?: number | null;
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
  pegRatio?: number | null;
  priceToBook?: number | null;
  revenueGrowth?: number;
  profitMargin?: number;
  dividendYield?: number | null;
  beta?: number | null;
  fiftyTwoWeekHigh?: number;
  fiftyTwoWeekLow?: number;
  avgVolume?: number;
}

/**
 * Lite stock data - minimal price info for S&P 500 heatmap display.
 * Full fundamentals/history only available for scored picks.
 */
export interface LiteStock {
  ticker: string;
  companyName: string;
  sector: Sector | string;
  currentPrice: number;
  priceChange: number;
  priceChangePercent: number;
  volume?: number;
  marketCap?: number;
  isLite: true;
}

// =============================================================================
// Macro Types
// =============================================================================

export interface MacroIndicator {
  id: string;
  name: string;
  value: number;
  previousValue?: number | null;
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
// Smart Money Types
// =============================================================================

export type SmartMoneySignalType = "congress" | "options" | "darkpool" | "13f";
export type TradeDirection = "buy" | "sell" | "exchange";
export type HedgeFundAction = "new" | "increased" | "decreased" | "sold" | "unchanged";
export type PoliticalParty = "D" | "R" | "I";
export type Chamber = "House" | "Senate";
export type OptionType = "call" | "put";

export interface CongressDetails {
  politician: string;
  party: PoliticalParty;
  chamber: Chamber;
  amount_low: number;
  amount_high: number;
  asset_description?: string | null;
  transaction_date?: string | null;
  disclosure_date: string | null;
}

export interface OptionsDetails {
  option_type: OptionType;
  strike: number;
  expiry: string;
  volume: number;
  open_interest: number;
  volume_oi_ratio: number;
  implied_volatility?: number;
  premium_total?: number;
}

export interface DarkPoolDetails {
  dark_pool_percent: number;
  total_volume: number;
  dark_pool_volume: number;
  reporting_period: string;
  source_venue?: string;
}

export interface HedgeFundDetails {
  fund_name: string;
  manager: string;
  shares: number;
  value: number;
  action: HedgeFundAction;
  shares_change?: number | null;
  shares_change_pct?: number | null;
  value_change?: number | null;
  portfolio_pct?: number | null;
  filing_date: string;
  quarter: string;
}

export type SmartMoneyDetails = CongressDetails | OptionsDetails | DarkPoolDetails | HedgeFundDetails;

export interface SmartMoneySignal {
  id: string;
  type: SmartMoneySignalType;
  ticker: string;
  direction: TradeDirection;
  strength: number; // 0-1
  summary: string;
  timestamp: string;
  source: string;
  details: SmartMoneyDetails;
}

export interface SmartMoneyContext {
  signals: SmartMoneySignal[];
  congress: SmartMoneySignal[];
  options: SmartMoneySignal[];
  hedgeFunds: SmartMoneySignal[];
  lastUpdated: string;
}

// =============================================================================
// Briefing Types
// =============================================================================

export type EventImpact = "high" | "medium" | "low";

export interface EconomicEvent {
  event: string;
  time: string; // ISO datetime
  impact: EventImpact;
  actual: number | null;
  forecast: number | null;
  previous: number | null;
  unit: string;
  isReleased: boolean;
}

export type NewsPriority = "critical" | "high" | "medium" | "low";
export type NewsImpactCategory = "market_wide" | "sector" | "company" | "social" | "fed" | "unknown";

export interface BriefingNewsItem {
  headline: string;
  source: string;
  url: string | null;
  timestamp: string;
  priority?: NewsPriority;
  relevanceScore?: number;
  category?: NewsImpactCategory;
  keywords?: string[];
  tickers?: string[];
}

export interface PreMarketMover {
  ticker: string;
  companyName: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  previousClose: number;
  isGainer: boolean;
}

export interface EarningsAnnouncement {
  symbol: string;
  date: string; // ISO date
  hour: string; // "bmo" (before open), "amc" (after close), "" (TBD)
  timingDisplay: string; // "Before Open", "After Close", "TBD"
  year: number;
  quarter: number;
  epsEstimate: number | null;
  epsActual: number | null;
  revenueEstimate: number | null;
  revenueActual: number | null;
  isReported: boolean;
}

export type SurpriseDirection = "beat" | "miss" | "in_line";

export interface HistoricalReaction {
  eventType: string; // "NFP", "CPI", "GDP", etc.
  eventName: string; // "Nonfarm Payrolls", etc.
  eventDate: string; // ISO date
  actual: number | null;
  forecast: number | null;
  surpriseDirection: SurpriseDirection;
  spyReaction1d: number; // SPY % change next trading day
  spyReaction5d: number | null; // SPY % change over 5 days
  summary: string; // "Last NFP beat → SPY +1.2%"
}

export interface DailyBriefing {
  date: string; // ISO date
  generatedAt: string;
  eventsToday: EconomicEvent[];
  eventsUpcoming: EconomicEvent[];
  nextMajorEvent: {
    event: string;
    time: string;
    impact: EventImpact;
  } | null;
  premarketGainers: PreMarketMover[];
  premarketLosers: PreMarketMover[];
  earningsToday: EarningsAnnouncement[];
  earningsBeforeOpen: EarningsAnnouncement[];
  earningsAfterClose: EarningsAnnouncement[];
  hasEarningsToday: boolean;
  marketNews: BriefingNewsItem[];
  fedNews: BriefingNewsItem[];
  hasHighImpactToday: boolean;
  historicalContext: Record<string, HistoricalReaction>; // event_type -> reaction
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

  // All S&P 500 stocks with prices (for heatmap)
  allStocks: LiteStock[];

  // Macro data
  macro: MacroContext;

  // News
  news: {
    market: NewsItem[];
    company: NewsItem[];
  };

  // Smart Money
  smartMoney: SmartMoneyContext;

  // Daily Briefing
  briefing?: DailyBriefing;

  // Summary metrics
  summary: ReportSummary;
}

export interface ReportSummary {
  totalPicks: number;
  totalStocks: number;
  avgConviction: number;
  topSector: Sector;
  highRiskCount: number;
  newsCount: number;
  marketTrend: Trend;
  smartMoneySignals?: number;
  congressTrades?: number;
  unusualOptions?: number;
  hedgeFundSignals?: number;
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

// =============================================================================
// Paper Trading Types
// =============================================================================

export type TradeStatus = "open" | "closed";

export interface PaperTrade {
  id: string;
  ticker: string;
  companyName: string;
  shares: number;
  entryPrice: number;
  entryDate: string; // ISO date string
  exitPrice?: number;
  exitDate?: string; // ISO date string
  status: TradeStatus;
  notes?: string;
}

export interface TradePerformance {
  trade: PaperTrade;
  currentPrice: number;
  marketValue: number;
  costBasis: number;
  pnl: number;
  pnlPercent: number;
  dayChange?: number;
  dayChangePercent?: number;
}

export interface PortfolioSummary {
  totalValue: number;
  totalCost: number;
  totalPnL: number;
  totalPnLPercent: number;
  openPositions: number;
  closedPositions: number;
  winRate: number; // % of closed trades with positive P&L
  bestTrade?: TradePerformance;
  worstTrade?: TradePerformance;
}
