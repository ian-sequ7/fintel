/**
 * Data loading utilities for the financial dashboard.
 * Provides functions to load and query report data.
 */

import type {
  FinancialReport,
  StockPick,
  StockDetail,
  LiteStock,
  MacroIndicator,
  MacroRisk,
  MacroContext,
  NewsItem,
  Timeframe,
  SortOption,
  NewsCategory,
  Sector,
  PricePoint,
  SmartMoneySignal,
  SmartMoneyContext,
  SmartMoneySignalType,
  HedgeFundDetails,
} from "./types";

// =============================================================================
// Data Loading
// =============================================================================

let _cachedReport: FinancialReport | null = null;

/**
 * Load the financial report data.
 * Caches the result for subsequent calls.
 */
export async function getReport(): Promise<FinancialReport> {
  if (_cachedReport) {
    return _cachedReport;
  }

  try {
    const data = await import("./report.json");
    _cachedReport = data.default as FinancialReport;
    return _cachedReport;
  } catch (error) {
    console.warn("Failed to load report.json, using mock data:", error);
    _cachedReport = _generateMockReport();
    return _cachedReport;
  }
}

/**
 * Synchronous version for Astro components.
 * Must be called after getReport() or will return mock data.
 */
export function getReportSync(): FinancialReport {
  if (_cachedReport) {
    return _cachedReport;
  }
  // Return mock data if not loaded
  _cachedReport = _generateMockReport();
  return _cachedReport;
}

// Initialize cache at module load (for static builds)
try {
  const data = await import("./report.json");
  _cachedReport = data.default as FinancialReport;
} catch {
  // Will use mock data
}

// =============================================================================
// Stock Picks
// =============================================================================

/**
 * Get all stock picks, optionally filtered and sorted.
 */
export function getPicks(
  timeframe?: Timeframe | "all",
  sortBy: SortOption = "conviction",
  sortOrder: "asc" | "desc" = "desc"
): StockPick[] {
  const report = getReportSync();
  let picks: StockPick[];

  if (!timeframe || timeframe === "all") {
    picks = [
      ...report.picks.short,
      ...report.picks.medium,
      ...report.picks.long,
    ];
  } else {
    picks = [...report.picks[timeframe]];
  }

  // Sort
  picks.sort((a, b) => {
    let comparison = 0;
    switch (sortBy) {
      case "conviction":
        comparison = a.convictionScore - b.convictionScore;
        break;
      case "ticker":
        comparison = a.ticker.localeCompare(b.ticker);
        break;
      case "price":
        comparison = a.currentPrice - b.currentPrice;
        break;
      case "change":
        comparison = a.priceChangePercent - b.priceChangePercent;
        break;
    }
    return sortOrder === "desc" ? -comparison : comparison;
  });

  return picks;
}

/**
 * Get picks by sector.
 */
export function getPicksBySector(sector: Sector): StockPick[] {
  return getPicks("all").filter((pick) => pick.sector === sector);
}

/**
 * Get top pick for each timeframe.
 */
export function getTopPicks(): StockPick[] {
  const report = getReportSync();
  const picks: StockPick[] = [];

  // Get highest conviction from each timeframe
  const timeframes: Timeframe[] = ["short", "medium", "long"];
  for (const tf of timeframes) {
    const tfPicks = report.picks[tf];
    if (tfPicks.length > 0) {
      const sorted = [...tfPicks].sort(
        (a, b) => b.convictionScore - a.convictionScore
      );
      picks.push(sorted[0]);
    }
  }

  return picks;
}

// =============================================================================
// Stock Details
// =============================================================================

/**
 * Get detailed stock data for a specific ticker.
 */
export function getStockDetail(ticker: string): StockDetail | null {
  const report = getReportSync();
  return report.stockDetails[ticker.toUpperCase()] ?? null;
}

/**
 * Get all S&P 500 stocks with prices (lite data for heatmap).
 * Returns ~500 stocks with current price, change, and sector.
 */
export function getAllStocks(): LiteStock[] {
  const report = getReportSync();
  return report.allStocks || [];
}

/**
 * Get all S&P 500 stocks grouped by sector.
 */
export function getStocksBySector(): Record<string, LiteStock[]> {
  const stocks = getAllStocks();
  const bySector: Record<string, LiteStock[]> = {};

  for (const stock of stocks) {
    const sector = stock.sector || "other";
    if (!bySector[sector]) {
      bySector[sector] = [];
    }
    bySector[sector].push(stock);
  }

  return bySector;
}

/**
 * Get all tickers that have picks or details.
 */
export function getAllTickers(): string[] {
  const report = getReportSync();
  const tickerSet = new Set<string>();

  // From picks
  for (const pick of getPicks("all")) {
    tickerSet.add(pick.ticker);
  }

  // From stock details
  for (const ticker of Object.keys(report.stockDetails)) {
    tickerSet.add(ticker);
  }

  return Array.from(tickerSet).sort();
}

/**
 * Get price history for a stock.
 */
export function getPriceHistory(ticker: string): PricePoint[] {
  const detail = getStockDetail(ticker);
  return detail?.priceHistory ?? [];
}

// =============================================================================
// Macro Data
// =============================================================================

/**
 * Get all macro data (indicators and risks).
 */
export function getMacroData(): MacroContext {
  const report = getReportSync();
  return report.macro;
}

/**
 * Get macro indicators.
 */
export function getMacroIndicators(): MacroIndicator[] {
  return getMacroData().indicators;
}

/**
 * Get macro risks, optionally filtered by severity.
 */
export function getMacroRisks(severity?: "low" | "medium" | "high"): MacroRisk[] {
  const risks = getMacroData().risks;
  if (!severity) {
    return risks;
  }
  return risks.filter((risk) => risk.severity === severity);
}

// =============================================================================
// News
// =============================================================================

/**
 * Get news items, optionally filtered by category or ticker.
 */
export function getNews(
  category?: NewsCategory | "all",
  ticker?: string
): NewsItem[] {
  const report = getReportSync();
  let news: NewsItem[];

  if (!category || category === "all") {
    news = [...report.news.market, ...report.news.company];
  } else if (category === "market" || category === "macro") {
    news = [...report.news.market];
  } else {
    news = [...report.news.company];
  }

  // Filter by ticker if specified
  if (ticker) {
    news = news.filter((item) =>
      item.tickersMentioned.includes(ticker.toUpperCase())
    );
  }

  // Sort by date (newest first)
  news.sort(
    (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
  );

  return news;
}

/**
 * Get news for a specific stock.
 */
export function getNewsForStock(ticker: string): NewsItem[] {
  return getNews("all", ticker);
}

/**
 * Get latest news items.
 */
export function getLatestNews(limit: number = 10): NewsItem[] {
  return getNews("all").slice(0, limit);
}

// =============================================================================
// Smart Money
// =============================================================================

/**
 * Get smart money context (all signals).
 */
export function getSmartMoneyData(): SmartMoneyContext {
  const report = getReportSync();
  return report.smartMoney ?? { signals: [], congress: [], options: [], hedgeFunds: [], lastUpdated: new Date().toISOString() };
}

/**
 * Get smart money signals, optionally filtered by type.
 */
export function getSmartMoneySignals(
  type?: SmartMoneySignalType | "all"
): SmartMoneySignal[] {
  const data = getSmartMoneyData();

  if (!type || type === "all") {
    return data.signals;
  }

  return data.signals.filter((signal) => signal.type === type);
}

/**
 * Get smart money signals for a specific ticker.
 */
export function getSmartMoneyForStock(ticker: string): SmartMoneySignal[] {
  const signals = getSmartMoneySignals("all");
  return signals.filter((s) => s.ticker.toUpperCase() === ticker.toUpperCase());
}

/**
 * Get smart money summary stats.
 */
export function getSmartMoneySummary(): {
  total: number;
  congress: number;
  options: number;
  hedgeFunds: number;
  buySignals: number;
  sellSignals: number;
} {
  const data = getSmartMoneyData();
  const buySignals = data.signals.filter((s) => s.direction === "buy").length;
  const sellSignals = data.signals.filter((s) => s.direction === "sell").length;

  return {
    total: data.signals.length,
    congress: data.congress.length,
    options: data.options.length,
    hedgeFunds: data.hedgeFunds?.length ?? 0,
    buySignals,
    sellSignals,
  };
}

/**
 * Get top smart money signals by strength.
 */
export function getTopSmartMoneySignals(limit: number = 10): SmartMoneySignal[] {
  const signals = getSmartMoneySignals("all");
  return [...signals]
    .sort((a, b) => b.strength - a.strength)
    .slice(0, limit);
}

/**
 * Format smart money signal strength as percentage.
 */
export function formatSignalStrength(strength: number): string {
  return `${Math.round(strength * 100)}%`;
}

/**
 * Get signal strength level.
 */
export function getSignalStrengthLevel(strength: number): "strong" | "moderate" | "weak" {
  if (strength >= 0.7) return "strong";
  if (strength >= 0.4) return "moderate";
  return "weak";
}

/**
 * Get hedge fund holdings signals.
 */
export function getHedgeFundSignals(): SmartMoneySignal[] {
  return getSmartMoneySignals("13f");
}

/**
 * Get hedge fund signals grouped by fund.
 */
export function getHedgeFundsByFund(): Map<string, SmartMoneySignal[]> {
  const signals = getHedgeFundSignals();
  const byFund = new Map<string, SmartMoneySignal[]>();

  for (const signal of signals) {
    const details = signal.details as HedgeFundDetails;
    const fundName = details.fund_name;
    if (!byFund.has(fundName)) {
      byFund.set(fundName, []);
    }
    byFund.get(fundName)!.push(signal);
  }

  return byFund;
}

/**
 * Format shares for display.
 */
export function formatShares(shares: number): string {
  if (shares >= 1e9) return `${(shares / 1e9).toFixed(2)}B`;
  if (shares >= 1e6) return `${(shares / 1e6).toFixed(2)}M`;
  if (shares >= 1e3) return `${(shares / 1e3).toFixed(1)}K`;
  return shares.toLocaleString();
}

/**
 * Format hedge fund action for display.
 */
export function formatHedgeFundAction(action: string): { label: string; color: string; icon: string } {
  switch (action) {
    case "new":
      return { label: "New Position", color: "text-success", icon: "🆕" };
    case "increased":
      return { label: "Increased", color: "text-success", icon: "📈" };
    case "decreased":
      return { label: "Decreased", color: "text-danger", icon: "📉" };
    case "sold":
      return { label: "Sold", color: "text-danger", icon: "🚫" };
    default:
      return { label: "Unchanged", color: "text-text-secondary", icon: "➡️" };
  }
}

/**
 * Format amount range for congress trades.
 */
export function formatAmountRange(low: number, high: number): string {
  const formatAmount = (n: number) => {
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${n}`;
  };
  return `${formatAmount(low)} - ${formatAmount(high)}`;
}

// =============================================================================
// Summary & Stats
// =============================================================================

/**
 * Get report summary.
 */
export function getSummary() {
  const report = getReportSync();
  return report.summary;
}

/**
 * Get the report generation timestamp.
 */
export function getGeneratedAt(): Date {
  const report = getReportSync();
  return new Date(report.generatedAt);
}

/**
 * Get the prices last updated timestamp.
 * Falls back to generatedAt if no incremental update has been done.
 */
export function getPricesUpdatedAt(): Date {
  const report = getReportSync();
  const pricesTs = (report as any).pricesUpdatedAt || (report as any).meta?.pricesUpdatedAt;
  return new Date(pricesTs || report.generatedAt);
}

/**
 * Check if prices were updated incrementally (vs full pipeline).
 */
export function wasPriceUpdateIncremental(): boolean {
  const report = getReportSync();
  return (report as any).meta?.priceUpdateMethod === "incremental";
}

/**
 * Get the watchlist.
 */
export function getWatchlist(): string[] {
  const report = getReportSync();
  return report.watchlist;
}

// =============================================================================
// Formatting Utilities
// =============================================================================

/**
 * Format relative time from ISO date string.
 */
export function formatRelativeTime(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

/**
 * Format conviction score as percentage.
 */
export function formatConviction(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Get conviction level label.
 */
export function getConvictionLevel(score: number): "high" | "medium" | "low" {
  if (score >= 0.7) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

/**
 * Format price change with sign.
 */
export function formatChange(change: number, isPercent = false): string {
  const sign = change >= 0 ? "+" : "";
  const suffix = isPercent ? "%" : "";
  return `${sign}${change.toFixed(2)}${suffix}`;
}

/**
 * Format large numbers (market cap, volume).
 */
export function formatLargeNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return "-";
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  if (num >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
  return `$${num.toFixed(2)}`;
}

/**
 * Format price.
 */
export function formatPrice(price: number | null | undefined): string {
  if (price === null || price === undefined) return "-";
  return `$${price.toFixed(2)}`;
}

// =============================================================================
// Mock Data Generator
// =============================================================================

function _generatePriceHistory(
  basePrice: number,
  days: number = 30
): PricePoint[] {
  const history: PricePoint[] = [];
  let price = basePrice * 0.95; // Start 5% lower
  const today = new Date();

  for (let i = days; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);

    // Skip weekends
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const volatility = 0.02;
    const drift = 0.001; // Slight upward bias
    const change = (Math.random() - 0.48 + drift) * volatility * price;

    const open = price;
    const close = price + change;
    const high = Math.max(open, close) * (1 + Math.random() * 0.01);
    const low = Math.min(open, close) * (1 - Math.random() * 0.01);

    history.push({
      time: date.toISOString().split("T")[0],
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume: Math.floor(Math.random() * 50000000) + 10000000,
    });

    price = close;
  }

  return history;
}

function _generateMockReport(): FinancialReport {
  const now = new Date().toISOString();

  // Stock data
  const stocks: Record<string, { name: string; price: number; sector: Sector }> = {
    AAPL: { name: "Apple Inc.", price: 227.80, sector: "technology" },
    MSFT: { name: "Microsoft Corp.", price: 420.50, sector: "technology" },
    NVDA: { name: "NVIDIA Corp.", price: 892.50, sector: "technology" },
    GOOGL: { name: "Alphabet Inc.", price: 178.20, sector: "communications" },
    AMZN: { name: "Amazon.com Inc.", price: 188.50, sector: "consumer" },
    META: { name: "Meta Platforms Inc.", price: 495.00, sector: "communications" },
    TSLA: { name: "Tesla Inc.", price: 248.50, sector: "consumer" },
    JPM: { name: "JPMorgan Chase", price: 198.75, sector: "finance" },
    V: { name: "Visa Inc.", price: 285.30, sector: "finance" },
    JNJ: { name: "Johnson & Johnson", price: 156.80, sector: "healthcare" },
    UNH: { name: "UnitedHealth Group", price: 528.40, sector: "healthcare" },
    XOM: { name: "Exxon Mobil", price: 112.50, sector: "energy" },
    CVX: { name: "Chevron Corp.", price: 148.20, sector: "energy" },
    PG: { name: "Procter & Gamble", price: 165.40, sector: "consumer" },
    HD: { name: "Home Depot", price: 378.60, sector: "consumer" },
  };

  // Generate stock details with price history
  const stockDetails: Record<string, StockDetail> = {};

  for (const [ticker, info] of Object.entries(stocks)) {
    const priceHistory = _generatePriceHistory(info.price, 30);
    const lastPrice = priceHistory[priceHistory.length - 1]?.close ?? info.price;
    const prevPrice = priceHistory[priceHistory.length - 2]?.close ?? lastPrice;
    const change = lastPrice - prevPrice;

    stockDetails[ticker] = {
      ticker,
      companyName: info.name,
      currentPrice: lastPrice,
      priceChange: change,
      priceChangePercent: (change / prevPrice) * 100,
      convictionScore: 0.5 + Math.random() * 0.4,
      timeframe: "medium",
      thesis: `Strong fundamentals with growth potential in ${info.sector} sector.`,
      riskFactors: ["Market volatility", "Competition"],
      sector: info.sector,
      entryPrice: lastPrice * 0.98,
      targetPrice: lastPrice * 1.15,
      marketCap: lastPrice * 1e9 * (5 + Math.random() * 10),
      priceHistory,
      relatedNews: [],
      fundamentals: {
        peTrailing: 20 + Math.random() * 30,
        peForward: 18 + Math.random() * 25,
        pegRatio: 1 + Math.random() * 2,
        priceToBook: 3 + Math.random() * 10,
        revenueGrowth: 0.05 + Math.random() * 0.15,
        profitMargin: 0.1 + Math.random() * 0.2,
        dividendYield: Math.random() * 0.03,
        beta: 0.8 + Math.random() * 0.6,
        fiftyTwoWeekHigh: lastPrice * 1.2,
        fiftyTwoWeekLow: lastPrice * 0.75,
        avgVolume: 20000000 + Math.random() * 50000000,
      },
    };
  }

  // Create picks
  const shortPicks: StockPick[] = [
    { ...stockDetails.NVDA, timeframe: "short", convictionScore: 0.88, thesis: "AI infrastructure demand accelerating. Data center revenue growth exceeding expectations. Near-term catalyst with earnings." },
    { ...stockDetails.META, timeframe: "short", convictionScore: 0.76, thesis: "Reels monetization improving rapidly. Cost discipline driving margin expansion. Ad market recovery underway." },
    { ...stockDetails.AMZN, timeframe: "short", convictionScore: 0.72, thesis: "AWS re-acceleration visible. Retail margins expanding. Advertising business growing 20%+ YoY." },
    { ...stockDetails.TSLA, timeframe: "short", convictionScore: 0.65, thesis: "Cybertruck production ramping. Energy storage business accelerating. FSD improvements driving take rate." },
  ];

  const mediumPicks: StockPick[] = [
    { ...stockDetails.MSFT, timeframe: "medium", convictionScore: 0.85, thesis: "Azure growth reaccelerating with AI workloads. Copilot monetization just beginning. Enterprise moat strengthening." },
    { ...stockDetails.GOOGL, timeframe: "medium", convictionScore: 0.78, thesis: "Search moat intact despite AI fears. Cloud growth strong. Gemini integration across products." },
    { ...stockDetails.V, timeframe: "medium", convictionScore: 0.74, thesis: "Cross-border travel recovery ongoing. Digital payments secular growth. Pricing power intact." },
    { ...stockDetails.UNH, timeframe: "medium", convictionScore: 0.70, thesis: "Healthcare cost management expertise. Optum growth engine. Demographic tailwinds." },
    { ...stockDetails.HD, timeframe: "medium", convictionScore: 0.68, thesis: "Pro segment resilient. Housing turnover will recover. Market share gains from competitors." },
  ];

  const longPicks: StockPick[] = [
    { ...stockDetails.AAPL, timeframe: "long", convictionScore: 0.86, thesis: "Services flywheel compounding. Ecosystem stickiness unmatched. Vision Pro opens new category. India growth." },
    { ...stockDetails.JPM, timeframe: "long", convictionScore: 0.75, thesis: "Best-in-class bank. Net interest income benefiting from rates. Investment banking recovery coming." },
    { ...stockDetails.JNJ, timeframe: "long", convictionScore: 0.72, thesis: "Pharma pipeline strong post-split. MedTech recovery. Dividend aristocrat with pricing power." },
    { ...stockDetails.XOM, timeframe: "long", convictionScore: 0.68, thesis: "Low-cost producer. Pioneer acquisition accretive. Strong capital return program." },
    { ...stockDetails.PG, timeframe: "long", convictionScore: 0.65, thesis: "Pricing power demonstrated. Volume recovery in emerging markets. Innovation pipeline strong." },
  ];

  // Macro indicators
  const indicators: MacroIndicator[] = [
    { id: "gdp", name: "GDP Growth (QoQ)", value: 2.8, previousValue: 2.1, unit: "%", trend: "up", source: "BEA", updatedAt: now, description: "Real GDP growth rate" },
    { id: "cpi", name: "CPI (YoY)", value: 3.2, previousValue: 3.4, unit: "%", trend: "down", source: "BLS", updatedAt: now, description: "Consumer Price Index" },
    { id: "pce", name: "Core PCE (YoY)", value: 2.8, previousValue: 2.9, unit: "%", trend: "down", source: "BEA", updatedAt: now, description: "Fed's preferred inflation measure" },
    { id: "unrate", name: "Unemployment Rate", value: 4.2, previousValue: 4.1, unit: "%", trend: "up", source: "BLS", updatedAt: now, description: "U.S. unemployment rate" },
    { id: "fedfunds", name: "Fed Funds Rate", value: 5.25, previousValue: 5.25, unit: "%", trend: "flat", source: "Federal Reserve", updatedAt: now, description: "Target federal funds rate" },
    { id: "10y", name: "10Y Treasury Yield", value: 4.35, previousValue: 4.28, unit: "%", trend: "up", source: "Treasury", updatedAt: now, description: "10-year Treasury yield" },
    { id: "vix", name: "VIX", value: 14.5, previousValue: 15.2, unit: "", trend: "down", source: "CBOE", updatedAt: now, description: "Market volatility index" },
    { id: "consumer", name: "Consumer Confidence", value: 102.5, previousValue: 99.8, unit: "", trend: "up", source: "Conference Board", updatedAt: now, description: "Consumer confidence index" },
  ];

  // Macro risks
  const risks: MacroRisk[] = [
    { id: "inflation", name: "Inflation Persistence", severity: "medium", description: "Core inflation remains sticky above Fed's 2% target, particularly in services and shelter.", affectedSectors: ["consumer", "real_estate", "utilities"], likelihood: 0.65, potentialImpact: "May delay rate cuts, pressure growth stock multiples" },
    { id: "geopolitical", name: "Geopolitical Tensions", severity: "high", description: "Escalating conflicts in multiple regions affecting supply chains and commodity prices.", affectedSectors: ["energy", "industrials", "materials", "technology"], likelihood: 0.75, potentialImpact: "Oil price spikes, semiconductor supply disruption, defense rotation" },
    { id: "china", name: "China Economic Slowdown", severity: "medium", description: "Property sector stress and weak consumer spending in China affecting global growth.", affectedSectors: ["materials", "consumer", "industrials"], likelihood: 0.70, potentialImpact: "Commodity demand weakness, multinational revenue headwinds" },
    { id: "tech_valuation", name: "Tech Valuation Correction", severity: "low", description: "AI enthusiasm has pushed tech valuations to elevated levels relative to history.", affectedSectors: ["technology", "communications"], likelihood: 0.45, potentialImpact: "Mean reversion if growth disappoints, rotation to value" },
    { id: "credit", name: "Credit Tightening", severity: "medium", description: "Banks maintaining tight lending standards, commercial real estate stress ongoing.", affectedSectors: ["finance", "real_estate"], likelihood: 0.55, potentialImpact: "Higher borrowing costs, CRE defaults, bank stress" },
  ];

  // News items
  const marketNews: NewsItem[] = [
    { id: "m1", headline: "Fed Officials Signal Patience on Rate Cuts Amid Sticky Inflation", source: "Reuters", url: "https://reuters.com/1", publishedAt: new Date(Date.now() - 1800000).toISOString(), category: "macro", relevanceScore: 0.95, tickersMentioned: [], excerpt: "Federal Reserve officials indicated they need more confidence inflation is heading to 2% before cutting rates." },
    { id: "m2", headline: "S&P 500 Hits Record High as Tech Rally Continues", source: "Bloomberg", url: "https://bloomberg.com/2", publishedAt: new Date(Date.now() - 3600000).toISOString(), category: "market", relevanceScore: 0.92, tickersMentioned: ["AAPL", "MSFT", "NVDA"], excerpt: "The benchmark index reached new all-time highs driven by strong earnings from technology giants." },
    { id: "m3", headline: "Treasury Yields Rise After Strong Employment Report", source: "WSJ", url: "https://wsj.com/3", publishedAt: new Date(Date.now() - 7200000).toISOString(), category: "macro", relevanceScore: 0.88, tickersMentioned: [], excerpt: "Bond yields climbed after data showed the labor market remains resilient." },
    { id: "m4", headline: "Oil Prices Surge on Middle East Supply Concerns", source: "CNBC", url: "https://cnbc.com/4", publishedAt: new Date(Date.now() - 10800000).toISOString(), category: "market", relevanceScore: 0.85, tickersMentioned: ["XOM", "CVX"], excerpt: "Crude oil jumped 3% as geopolitical tensions raised supply disruption fears." },
    { id: "m5", headline: "Q4 Earnings Season Off to Strong Start", source: "MarketWatch", url: "https://marketwatch.com/5", publishedAt: new Date(Date.now() - 14400000).toISOString(), category: "earnings", relevanceScore: 0.82, tickersMentioned: [], excerpt: "Early reporters beating estimates at higher rate than historical average." },
    { id: "m6", headline: "Dollar Strengthens as Rate Cut Expectations Moderate", source: "FT", url: "https://ft.com/6", publishedAt: new Date(Date.now() - 18000000).toISOString(), category: "macro", relevanceScore: 0.78, tickersMentioned: [], excerpt: "The dollar index rose to three-week highs as traders push back rate cut timing." },
    { id: "m7", headline: "China Manufacturing PMI Unexpectedly Contracts", source: "Reuters", url: "https://reuters.com/7", publishedAt: new Date(Date.now() - 21600000).toISOString(), category: "macro", relevanceScore: 0.75, tickersMentioned: [], excerpt: "Factory activity shrank for the first time in three months, signaling ongoing economic challenges." },
    { id: "m8", headline: "Consumer Spending Remains Resilient Despite High Rates", source: "Bloomberg", url: "https://bloomberg.com/8", publishedAt: new Date(Date.now() - 25200000).toISOString(), category: "market", relevanceScore: 0.72, tickersMentioned: ["AMZN", "HD"], excerpt: "Retail sales data beat expectations, showing American consumers continue to spend." },
  ];

  const companyNews: NewsItem[] = [
    { id: "c1", headline: "NVIDIA Unveils Next-Generation Blackwell AI Chips", source: "TechCrunch", url: "https://techcrunch.com/1", publishedAt: new Date(Date.now() - 2400000).toISOString(), category: "company", relevanceScore: 0.96, tickersMentioned: ["NVDA"], excerpt: "The new architecture promises 4x improvement in AI training efficiency." },
    { id: "c2", headline: "Apple Vision Pro Sales Exceed Initial Forecasts", source: "CNBC", url: "https://cnbc.com/c2", publishedAt: new Date(Date.now() - 5400000).toISOString(), category: "company", relevanceScore: 0.88, tickersMentioned: ["AAPL"], excerpt: "Spatial computing device seeing strong enterprise adoption." },
    { id: "c3", headline: "Microsoft Azure Revenue Growth Accelerates to 29%", source: "Bloomberg", url: "https://bloomberg.com/c3", publishedAt: new Date(Date.now() - 9000000).toISOString(), category: "earnings", relevanceScore: 0.92, tickersMentioned: ["MSFT"], excerpt: "Cloud business shows re-acceleration driven by AI workloads." },
    { id: "c4", headline: "Amazon AWS Announces New AI Services at re:Invent", source: "AWS Blog", url: "https://aws.com/c4", publishedAt: new Date(Date.now() - 12600000).toISOString(), category: "company", relevanceScore: 0.85, tickersMentioned: ["AMZN"], excerpt: "New Bedrock features and custom chip announcements." },
    { id: "c5", headline: "Meta's Reality Labs Losses Narrow as Headset Sales Grow", source: "The Verge", url: "https://theverge.com/c5", publishedAt: new Date(Date.now() - 16200000).toISOString(), category: "earnings", relevanceScore: 0.78, tickersMentioned: ["META"], excerpt: "Quest 3 sales strong heading into holiday season." },
    { id: "c6", headline: "Tesla Cybertruck Deliveries Ramp to 2,500 Per Week", source: "Electrek", url: "https://electrek.com/c6", publishedAt: new Date(Date.now() - 19800000).toISOString(), category: "company", relevanceScore: 0.82, tickersMentioned: ["TSLA"], excerpt: "Production improvements at Texas Gigafactory." },
    { id: "c7", headline: "Alphabet's Waymo Expands to Three New Cities", source: "Reuters", url: "https://reuters.com/c7", publishedAt: new Date(Date.now() - 23400000).toISOString(), category: "company", relevanceScore: 0.75, tickersMentioned: ["GOOGL"], excerpt: "Autonomous taxi service launching in Austin, Atlanta, and Miami." },
    { id: "c8", headline: "JPMorgan Raises Dividend, Announces $30B Buyback", source: "WSJ", url: "https://wsj.com/c8", publishedAt: new Date(Date.now() - 27000000).toISOString(), category: "company", relevanceScore: 0.80, tickersMentioned: ["JPM"], excerpt: "Bank passes stress test with flying colors, boosts capital return." },
    { id: "c9", headline: "UnitedHealth Optum Revenue Grows 14% Year-Over-Year", source: "HealthcareFinance", url: "https://hf.com/c9", publishedAt: new Date(Date.now() - 30600000).toISOString(), category: "earnings", relevanceScore: 0.72, tickersMentioned: ["UNH"], excerpt: "Healthcare services segment continues to drive growth." },
    { id: "c10", headline: "Visa Reports Record Holiday Transaction Volumes", source: "PaymentsSource", url: "https://payments.com/c10", publishedAt: new Date(Date.now() - 34200000).toISOString(), category: "company", relevanceScore: 0.68, tickersMentioned: ["V"], excerpt: "Cross-border volumes up 15% as international travel recovers." },
    { id: "c11", headline: "Johnson & Johnson Cancer Drug Shows Strong Phase 3 Results", source: "FiercePharma", url: "https://fierce.com/c11", publishedAt: new Date(Date.now() - 37800000).toISOString(), category: "company", relevanceScore: 0.85, tickersMentioned: ["JNJ"], excerpt: "New therapy could become standard of care for lung cancer." },
    { id: "c12", headline: "ExxonMobil Pioneer Acquisition Closes, Integration Begins", source: "OilPrice", url: "https://oilprice.com/c12", publishedAt: new Date(Date.now() - 41400000).toISOString(), category: "company", relevanceScore: 0.75, tickersMentioned: ["XOM"], excerpt: "Combined entity now largest Permian Basin producer." },
  ];

  // Link news to stock details
  for (const news of companyNews) {
    for (const ticker of news.tickersMentioned) {
      if (stockDetails[ticker]) {
        stockDetails[ticker].relatedNews.push(news);
      }
    }
  }

  // Smart money signals
  const congressSignals: SmartMoneySignal[] = [
    {
      id: "cong_1",
      type: "congress",
      ticker: "NVDA",
      direction: "buy",
      strength: 0.85,
      summary: "Nancy Pelosi (D-House) bought NVDA ($100,001 - $250,000)",
      timestamp: new Date(Date.now() - 86400000 * 3).toISOString(),
      source: "congress",
      details: {
        politician: "Nancy Pelosi",
        party: "D",
        chamber: "House",
        amount_low: 100001,
        amount_high: 250000,
        disclosure_date: new Date(Date.now() - 86400000 * 3).toISOString(),
      },
    },
    {
      id: "cong_2",
      type: "congress",
      ticker: "MSFT",
      direction: "buy",
      strength: 0.7,
      summary: "Dan Crenshaw (R-House) bought MSFT ($50,001 - $100,000)",
      timestamp: new Date(Date.now() - 86400000 * 5).toISOString(),
      source: "congress",
      details: {
        politician: "Dan Crenshaw",
        party: "R",
        chamber: "House",
        amount_low: 50001,
        amount_high: 100000,
        disclosure_date: new Date(Date.now() - 86400000 * 5).toISOString(),
      },
    },
    {
      id: "cong_3",
      type: "congress",
      ticker: "AAPL",
      direction: "sell",
      strength: 0.5,
      summary: "Tommy Tuberville (R-Senate) sold AAPL ($15,001 - $50,000)",
      timestamp: new Date(Date.now() - 86400000 * 7).toISOString(),
      source: "congress",
      details: {
        politician: "Tommy Tuberville",
        party: "R",
        chamber: "Senate",
        amount_low: 15001,
        amount_high: 50000,
        disclosure_date: new Date(Date.now() - 86400000 * 7).toISOString(),
      },
    },
  ];

  const optionsSignals: SmartMoneySignal[] = [
    {
      id: "opt_1",
      type: "options",
      ticker: "NVDA",
      direction: "buy",
      strength: 0.82,
      summary: "Unusual CALL activity on NVDA: $950 2025-01-17, Volume/OI=6.2x, $1.2M premium",
      timestamp: new Date(Date.now() - 3600000 * 2).toISOString(),
      source: "yahoo",
      details: {
        option_type: "call",
        strike: 950,
        expiry: "2025-01-17",
        volume: 12400,
        open_interest: 2000,
        volume_oi_ratio: 6.2,
        implied_volatility: 0.52,
        premium_total: 1240000,
      },
    },
    {
      id: "opt_2",
      type: "options",
      ticker: "TSLA",
      direction: "sell",
      strength: 0.68,
      summary: "Unusual PUT activity on TSLA: $220 2025-01-17, Volume/OI=4.5x",
      timestamp: new Date(Date.now() - 3600000 * 4).toISOString(),
      source: "yahoo",
      details: {
        option_type: "put",
        strike: 220,
        expiry: "2025-01-17",
        volume: 9000,
        open_interest: 2000,
        volume_oi_ratio: 4.5,
        implied_volatility: 0.65,
        premium_total: 540000,
      },
    },
    {
      id: "opt_3",
      type: "options",
      ticker: "META",
      direction: "buy",
      strength: 0.75,
      summary: "Unusual CALL activity on META: $550 2025-02-21, Volume/OI=5.0x",
      timestamp: new Date(Date.now() - 3600000 * 6).toISOString(),
      source: "yahoo",
      details: {
        option_type: "call",
        strike: 550,
        expiry: "2025-02-21",
        volume: 5000,
        open_interest: 1000,
        volume_oi_ratio: 5.0,
        implied_volatility: 0.48,
        premium_total: 750000,
      },
    },
  ];

  const allSmartMoneySignals = [...congressSignals, ...optionsSignals].sort(
    (a, b) => b.strength - a.strength
  );

  return {
    generatedAt: now,
    version: "1.0.0",
    watchlist: Object.keys(stocks),
    picks: {
      short: shortPicks,
      medium: mediumPicks,
      long: longPicks,
    },
    stockDetails,
    allStocks: [],
    macro: {
      indicators,
      risks,
      marketSentiment: "up",
      lastUpdated: now,
    },
    news: {
      market: marketNews,
      company: companyNews,
    },
    smartMoney: {
      signals: allSmartMoneySignals,
      congress: congressSignals,
      options: optionsSignals,
      hedgeFunds: [],
      lastUpdated: now,
    },
    summary: {
      totalPicks: shortPicks.length + mediumPicks.length + longPicks.length,
      totalStocks: 0,
      avgConviction:
        [...shortPicks, ...mediumPicks, ...longPicks].reduce(
          (sum, p) => sum + p.convictionScore,
          0
        ) / (shortPicks.length + mediumPicks.length + longPicks.length),
      topSector: "technology",
      highRiskCount: risks.filter((r) => r.severity === "high").length,
      newsCount: marketNews.length + companyNews.length,
      marketTrend: "up",
      smartMoneySignals: allSmartMoneySignals.length,
      congressTrades: congressSignals.length,
      unusualOptions: optionsSignals.length,
    },
  };
}

// =============================================================================
// Legacy API (backwards compatibility)
// =============================================================================

/** @deprecated Use getReportSync() instead */
export function loadReport() {
  return getReportSync();
}

/** @deprecated Use getPicks() instead */
export function getAllPicks() {
  return getPicks("all");
}

/** @deprecated Use getPicks(timeframe) instead */
export function getPicksByTimeframe(
  _report: unknown,
  timeframe: Timeframe
) {
  return getPicks(timeframe);
}
