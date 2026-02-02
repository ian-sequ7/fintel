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

/**
 * Pre-computed technical indicators from server.
 * Avoids duplicating indicator logic in TypeScript.
 */
export interface PrecomputedIndicators {
  rsi: (number | null)[];
  macdLine: (number | null)[];
  macdSignal: (number | null)[];
  macdHistogram: (number | null)[];
  bbUpper: (number | null)[];
  bbMiddle: (number | null)[];
  bbLower: (number | null)[];
  sma50: (number | null)[];
  sma200: (number | null)[];
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
  indices?: IndexMembership[]; // Which indices this stock belongs to
}

export interface StockDetail extends StockPick {
  priceHistory: PricePoint[];
  relatedNews: NewsItem[];
  fundamentals: StockFundamentals;
  indicators?: PrecomputedIndicators; // Server-computed indicators (avoids TS duplication)
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
 * Index membership - which major US indices the stock belongs to.
 */
export type IndexMembership = "S&P 500" | "Dow 30" | "NASDAQ-100";

/**
 * Lite stock data - price info with chart history for heatmap and stock pages.
 * Includes S&P 500 + Dow 30 + NASDAQ-100 stocks.
 * Full fundamentals only available for scored picks, but all stocks get price history.
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
  indices?: IndexMembership[]; // Which indices this stock belongs to
  priceHistory?: PricePoint[]; // 90 days of OHLCV data for charts
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
// Backtest/Performance Types
// =============================================================================

export type TradeOutcome = "win" | "loss" | "flat";

export interface BacktestTrade {
  ticker: string;
  entryDate: string;
  exitDate: string;
  entryPrice: number;
  exitPrice: number;
  conviction: number;
  timeframe: Timeframe;
  sector: string | null;
  returnPct: number;
  benchmarkReturnPct: number;
  alpha: number;
  outcome: TradeOutcome;
  beatBenchmark: boolean;
}

export interface MonthlyReturn {
  month: string; // YYYY-MM-DD
  portfolioReturn: number;
  benchmarkReturn: number;
  numPicks: number;
  topPerformer: string | null;
  worstPerformer: string | null;
}

export interface BacktestMetrics {
  totalReturn: number;
  benchmarkReturn: number;
  alpha: number;
  hitRate: number;
  winRate: number;
  avgTradeReturn: number;
  avgAlphaPerTrade: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winLossRatio: number;
}

export interface BacktestResult {
  startDate: string;
  endDate: string;
  timeframe: Timeframe;
  totalTrades: number;
  tickersAnalyzed: number;
  performance: BacktestMetrics;
  bestTrade: {
    ticker: string;
    returnPct: number;
  } | null;
  worstTrade: {
    ticker: string;
    returnPct: number;
  } | null;
  monthlyReturns: MonthlyReturn[];
  limitations: string[];
  executedAt: string;
}

export interface BacktestContext {
  short: BacktestResult | null;
  medium: BacktestResult | null;
  long: BacktestResult | null;
  lastUpdated: string;
}

// =============================================================================
// Report Types (Root)
// =============================================================================

export interface ReportMeta {
  pricesUpdatedAt?: string;
  priceUpdateMethod?: "incremental" | "full";
}

export interface FinancialReport {
  generatedAt: string; // ISO date string
  version: string;
  watchlist: string[];

  // Optional metadata for incremental updates
  pricesUpdatedAt?: string;
  meta?: ReportMeta;

  // Stock picks by timeframe
  picks: {
    short: StockPick[];
    medium: StockPick[];
    long: StockPick[];
  };

  // Detailed stock data with price history (lazy-loaded from /data/stockDetails.json)
  stockDetails?: Record<string, StockDetail>;

  // All S&P 500 stocks with prices (lazy-loaded from /data/allStocks.json)
  allStocks?: LiteStock[];

  // Macro data
  macro: MacroContext;

  // News
  news: {
    market: NewsItem[];
    company: NewsItem[];
  };

  // Smart Money (lazy-loaded from /data/smartMoney.json)
  smartMoney?: SmartMoneyContext;

  // Daily Briefing
  briefing?: DailyBriefing;

  // Backtest/Performance Results
  backtest?: BacktestContext;

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

// =============================================================================
// Algorithm Signal Types
// =============================================================================

export type AlgorithmSignalType =
  | "long_entry"
  | "long_exit"
  | "short_entry"
  | "short_exit"
  | "stop_loss"
  | "take_profit"
  | "no_signal";

export interface IndicatorSnapshot {
  rsi?: number;
  macdLine?: number;
  macdSignal?: number;
  macdHistogram?: number;
  bbUpper?: number;
  bbMiddle?: number;
  bbLower?: number;
  atr?: number;
  sma20?: number;
  sma50?: number;
  sma200?: number;
  ema12?: number;
  ema26?: number;
  volumeSurge?: boolean;
  volumeRatio?: number;
}

export interface AlgorithmSignal {
  ticker: string;
  algorithmId: string;
  algorithmName: string;
  signalType: AlgorithmSignalType;
  confidence: number;
  priceAtSignal: number;
  timestamp: string;
  indicators: IndicatorSnapshot;
  rationale: string;
  suggestedEntry?: number;
  suggestedStop?: number;
  suggestedTarget?: number;
  metadata?: Record<string, unknown>;
}

export interface AlgorithmParameter {
  name: string;
  type: "int" | "float" | "bool";
  default: number | boolean;
  min?: number;
  max?: number;
  description: string;
}

export interface AlgorithmConfig {
  algorithmId: string;
  name: string;
  description: string;
  version: string;
  parameters: AlgorithmParameter[];
}

export interface SignalsResponse {
  ticker: string;
  signals: AlgorithmSignal[];
  currentPrice: number;
  lastUpdated: string;
}

// =============================================================================
// Algorithm Backtest Types
// =============================================================================

export interface AlgorithmBacktestRequest {
  algorithmId: string;
  tickers: string[];
  startDate: string;
  endDate: string;
  parameters?: Record<string, number | boolean>;
}

export interface AlgorithmTrade {
  ticker: string;
  entryDate: string;
  entryPrice: number;
  entrySignal: AlgorithmSignalType;
  exitDate?: string;
  exitPrice?: number;
  exitSignal?: AlgorithmSignalType;
  returnPct?: number;
  holdingDays?: number;
  indicators: IndicatorSnapshot;
}

export interface AlgorithmBacktestMetrics {
  totalReturn: number;
  benchmarkReturn: number;
  alpha: number;
  sharpeRatio: number;
  sortinoRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  avgHoldingDays: number;
}

export interface AlgorithmBacktestResult {
  algorithmId: string;
  algorithmName: string;
  startDate: string;
  endDate: string;
  tickersTested: string[];
  performance: AlgorithmBacktestMetrics;
  signalBreakdown: {
    longEntry: number;
    longExit: number;
    shortEntry: number;
    shortExit: number;
    stopLoss: number;
    takeProfit: number;
  };
  trades: AlgorithmTrade[];
  equityCurve: { date: string; value: number }[];
}
