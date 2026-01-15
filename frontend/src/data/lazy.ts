/**
 * Lazy-loading utilities for split JSON data.
 *
 * Heavy data (stockDetails, allStocks, smartMoney) is loaded on-demand
 * from /data/*.json to reduce initial bundle size.
 */

import type { StockDetail, LiteStock } from "./types";

// Cache for loaded data
const cache: {
  stockDetails: Record<string, StockDetail> | null;
  allStocks: LiteStock[] | null;
  smartMoney: SmartMoneyData | null;
} = {
  stockDetails: null,
  allStocks: null,
  smartMoney: null,
};

// Loading state to prevent duplicate fetches
const loading: {
  stockDetails: Promise<Record<string, StockDetail>> | null;
  allStocks: Promise<LiteStock[]> | null;
  smartMoney: Promise<SmartMoneyData> | null;
} = {
  stockDetails: null,
  allStocks: null,
  smartMoney: null,
};

export interface SmartMoneyData {
  signals: unknown[];
  congress: unknown[];
  options: unknown[];
  hedgeFunds: unknown[];
  lastUpdated: string;
}

/**
 * Fetch and cache stock details data.
 * Used by: PortfolioView, WatchlistView, CompareView
 */
export async function getStockDetails(): Promise<Record<string, StockDetail>> {
  if (cache.stockDetails) {
    return cache.stockDetails;
  }

  if (loading.stockDetails) {
    return loading.stockDetails;
  }

  loading.stockDetails = fetch("/data/stockDetails.json")
    .then((res) => {
      if (!res.ok) throw new Error(`Failed to load stockDetails: ${res.status}`);
      return res.json();
    })
    .then((data) => {
      cache.stockDetails = data;
      loading.stockDetails = null;
      return data;
    })
    .catch((err) => {
      loading.stockDetails = null;
      console.error("Failed to load stockDetails:", err);
      return {};
    });

  return loading.stockDetails;
}

/**
 * Fetch and cache all stocks data.
 * Used by: HeatMap, stock ticker pages
 */
export async function getAllStocksLazy(): Promise<LiteStock[]> {
  if (cache.allStocks) {
    return cache.allStocks;
  }

  if (loading.allStocks) {
    return loading.allStocks;
  }

  loading.allStocks = fetch("/data/allStocks.json")
    .then((res) => {
      if (!res.ok) throw new Error(`Failed to load allStocks: ${res.status}`);
      return res.json();
    })
    .then((data) => {
      cache.allStocks = data;
      loading.allStocks = null;
      return data;
    })
    .catch((err) => {
      loading.allStocks = null;
      console.error("Failed to load allStocks:", err);
      return [];
    });

  return loading.allStocks;
}

/**
 * Fetch and cache smart money data.
 * Used by: Smart money page/section
 */
export async function getSmartMoney(): Promise<SmartMoneyData> {
  if (cache.smartMoney) {
    return cache.smartMoney;
  }

  if (loading.smartMoney) {
    return loading.smartMoney;
  }

  const defaultData: SmartMoneyData = {
    signals: [],
    congress: [],
    options: [],
    hedgeFunds: [],
    lastUpdated: new Date().toISOString(),
  };

  loading.smartMoney = fetch("/data/smartMoney.json")
    .then((res) => {
      if (!res.ok) throw new Error(`Failed to load smartMoney: ${res.status}`);
      return res.json();
    })
    .then((data) => {
      cache.smartMoney = data;
      loading.smartMoney = null;
      return data;
    })
    .catch((err) => {
      loading.smartMoney = null;
      console.error("Failed to load smartMoney:", err);
      return defaultData;
    });

  return loading.smartMoney;
}

/**
 * Get a single stock's details by ticker.
 * Loads all stockDetails on first call, then returns from cache.
 */
export async function getStockDetail(ticker: string): Promise<StockDetail | null> {
  const details = await getStockDetails();
  return details[ticker.toUpperCase()] ?? null;
}

/**
 * Preload all lazy data in parallel.
 * Call this on app mount if you want to preload everything.
 */
export async function preloadAll(): Promise<void> {
  await Promise.all([
    getStockDetails(),
    getAllStocksLazy(),
    getSmartMoney(),
  ]);
}

/**
 * Clear the cache (useful for testing or forced refresh).
 */
export function clearCache(): void {
  cache.stockDetails = null;
  cache.allStocks = null;
  cache.smartMoney = null;
}
