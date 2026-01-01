/**
 * Heat Map Utility Functions
 * Data transformation and layout algorithms for the heat map visualization
 */

import type { StockPick, Sector } from "./types";

// ============================================================================
// Types
// ============================================================================

export interface HeatMapTileData {
  ticker: string;
  companyName: string;
  sector: Sector;
  priceChange: number;
  priceChangePercent: number;
  currentPrice: number;
  marketCap: number;
  convictionScore: number;
  timeframe: string;
  targetPrice?: number;
  stopLoss?: number;
  value: number; // Normalized value for sizing (0-1)
  isWatchlist: boolean;
}

export interface TileLayout {
  ticker: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export type SizeByOption = "marketCap" | "conviction";
export type ViewOption = "all" | "watchlist" | "topConviction" | "bySector";

// ============================================================================
// Color Utilities
// ============================================================================

/**
 * Get background color for a tile based on price change percentage
 * Uses CSS variables for theme support
 */
export function _getColorForChange(percent: number): string {
  if (percent <= -5) return "rgba(239, 68, 68, 1)"; // Full red
  if (percent <= -2) return "rgba(239, 68, 68, 0.7)";
  if (percent < 0) return "rgba(239, 68, 68, 0.4)";
  if (percent === 0) return "rgba(148, 163, 184, 0.3)"; // Neutral gray
  if (percent < 2) return "rgba(34, 197, 94, 0.4)";
  if (percent < 5) return "rgba(34, 197, 94, 0.7)";
  return "rgba(34, 197, 94, 1)"; // Full green
}

/**
 * Get text color for a tile (ensure contrast with background)
 */
export function _getTextColorForChange(percent: number): string {
  if (Math.abs(percent) >= 3) return "white";
  return "inherit";
}

// ============================================================================
// Data Transformation
// ============================================================================

/**
 * Transform stock picks into heat map tile data
 * Applies log scale for market cap normalization
 */
export function _transformToHeatMapData(
  stocks: StockPick[],
  sizeBy: SizeByOption,
  watchlistTickers: string[] = []
): HeatMapTileData[] {
  if (stocks.length === 0) return [];

  const watchlistSet = new Set(watchlistTickers);

  // Calculate min/max for normalization
  let minValue = Infinity;
  let maxValue = -Infinity;

  const rawData = stocks.map((stock) => {
    let value: number;
    if (sizeBy === "marketCap") {
      // Use log scale for market cap (range is huge: $12B to $3.7T)
      value = stock.marketCap ? Math.log10(stock.marketCap) : 10;
    } else {
      // Conviction is already 0-1
      value = stock.convictionScore;
    }
    minValue = Math.min(minValue, value);
    maxValue = Math.max(maxValue, value);
    return { stock, value };
  });

  // Normalize values to 0-1 range
  const range = maxValue - minValue || 1;

  return rawData.map(({ stock, value }) => ({
    ticker: stock.ticker,
    companyName: stock.companyName,
    sector: stock.sector,
    priceChange: stock.priceChange,
    priceChangePercent: stock.priceChangePercent,
    currentPrice: stock.currentPrice,
    marketCap: stock.marketCap || 0,
    convictionScore: stock.convictionScore,
    timeframe: stock.timeframe,
    targetPrice: stock.targetPrice,
    stopLoss: stock.stopLoss,
    value: (value - minValue) / range,
    isWatchlist: watchlistSet.has(stock.ticker),
  }));
}

/**
 * Group tiles by sector
 */
export function _groupBySector(
  data: HeatMapTileData[]
): Record<Sector, HeatMapTileData[]> {
  const groups: Record<string, HeatMapTileData[]> = {};

  for (const tile of data) {
    if (!groups[tile.sector]) {
      groups[tile.sector] = [];
    }
    groups[tile.sector].push(tile);
  }

  return groups as Record<Sector, HeatMapTileData[]>;
}

/**
 * Filter tiles based on view option
 */
export function _filterByView(
  data: HeatMapTileData[],
  view: ViewOption
): HeatMapTileData[] {
  switch (view) {
    case "watchlist":
      return data.filter((tile) => tile.isWatchlist);
    case "topConviction":
      return [...data]
        .sort((a, b) => b.convictionScore - a.convictionScore)
        .slice(0, 20);
    case "all":
    case "bySector":
    default:
      return data;
  }
}

// ============================================================================
// Layout Algorithm - Squarified Treemap
// ============================================================================

interface LayoutRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Calculate the aspect ratio of a rectangle
 */
function _aspectRatio(width: number, height: number): number {
  return Math.max(width / height, height / width);
}

/**
 * Calculate worst aspect ratio for a row of items
 */
function _worstAspectRatio(
  items: HeatMapTileData[],
  totalValue: number,
  length: number,
  totalArea: number
): number {
  if (items.length === 0) return Infinity;

  const rowArea = items.reduce((sum, item) => sum + item.value, 0) / totalValue * totalArea;
  const rowWidth = rowArea / length;

  let worst = 0;
  for (const item of items) {
    const itemArea = (item.value / totalValue) * totalArea;
    const itemHeight = itemArea / rowWidth;
    worst = Math.max(worst, _aspectRatio(rowWidth, itemHeight));
  }

  return worst;
}

/**
 * Layout a single row of items within a rectangle
 */
function _layoutRow(
  items: HeatMapTileData[],
  rect: LayoutRect,
  totalValue: number,
  totalArea: number,
  isVertical: boolean
): { layouts: TileLayout[]; remaining: LayoutRect } {
  const layouts: TileLayout[] = [];
  const rowValue = items.reduce((sum, item) => sum + item.value, 0);
  const rowArea = (rowValue / totalValue) * totalArea;

  if (isVertical) {
    const rowWidth = rowArea / rect.height;
    let y = rect.y;

    for (const item of items) {
      const itemArea = (item.value / totalValue) * totalArea;
      const itemHeight = itemArea / rowWidth;

      layouts.push({
        ticker: item.ticker,
        x: rect.x,
        y: y,
        width: rowWidth,
        height: itemHeight,
      });

      y += itemHeight;
    }

    return {
      layouts,
      remaining: {
        x: rect.x + rowWidth,
        y: rect.y,
        width: rect.width - rowWidth,
        height: rect.height,
      },
    };
  } else {
    const rowHeight = rowArea / rect.width;
    let x = rect.x;

    for (const item of items) {
      const itemArea = (item.value / totalValue) * totalArea;
      const itemWidth = itemArea / rowHeight;

      layouts.push({
        ticker: item.ticker,
        x: x,
        y: rect.y,
        width: itemWidth,
        height: rowHeight,
      });

      x += itemWidth;
    }

    return {
      layouts,
      remaining: {
        x: rect.x,
        y: rect.y + rowHeight,
        width: rect.width,
        height: rect.height - rowHeight,
      },
    };
  }
}

/**
 * Squarified treemap layout algorithm
 * Produces tiles with aspect ratios close to 1 (more square-like)
 */
export function _calculateTileLayout(
  data: HeatMapTileData[],
  containerWidth: number,
  containerHeight: number
): TileLayout[] {
  if (data.length === 0 || containerWidth <= 0 || containerHeight <= 0) {
    return [];
  }

  // Sort by value descending for better layout
  const sorted = [...data].sort((a, b) => b.value - a.value);

  // Ensure minimum values
  const minValue = 0.05;
  const adjusted = sorted.map((item) => ({
    ...item,
    value: Math.max(item.value, minValue),
  }));

  const totalValue = adjusted.reduce((sum, item) => sum + item.value, 0);
  const totalArea = containerWidth * containerHeight;

  const layouts: TileLayout[] = [];
  let remaining: LayoutRect = {
    x: 0,
    y: 0,
    width: containerWidth,
    height: containerHeight,
  };

  let items = [...adjusted];

  while (items.length > 0) {
    const isVertical = remaining.width > remaining.height;
    const length = isVertical ? remaining.height : remaining.width;

    // Find the best row
    let row: HeatMapTileData[] = [];
    let currentWorst = Infinity;

    for (let i = 0; i < items.length; i++) {
      const testRow = [...row, items[i]];
      const testWorst = _worstAspectRatio(testRow, totalValue, length, totalArea);

      if (testWorst <= currentWorst) {
        row = testRow;
        currentWorst = testWorst;
      } else {
        break;
      }
    }

    // Layout the row
    const result = _layoutRow(row, remaining, totalValue, totalArea, isVertical);
    layouts.push(...result.layouts);
    remaining = result.remaining;

    // Remove laid out items
    items = items.slice(row.length);
  }

  return layouts;
}

// ============================================================================
// Sector Utilities
// ============================================================================

export const SECTOR_LABELS: Record<Sector, string> = {
  technology: "Technology",
  healthcare: "Healthcare",
  finance: "Finance",
  consumer: "Consumer",
  energy: "Energy",
  industrials: "Industrials",
  materials: "Materials",
  utilities: "Utilities",
  real_estate: "Real Estate",
  communications: "Communications",
};

export const SECTOR_COLORS: Record<Sector, string> = {
  technology: "#3b82f6", // blue
  healthcare: "#ec4899", // pink
  finance: "#8b5cf6", // purple
  consumer: "#f59e0b", // amber
  energy: "#ef4444", // red
  industrials: "#6b7280", // gray
  materials: "#78716c", // stone
  utilities: "#22c55e", // green
  real_estate: "#14b8a6", // teal
  communications: "#06b6d4", // cyan
};

// ============================================================================
// Formatting Utilities
// ============================================================================

export function _formatMarketCap(value: number): string {
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
  return `$${value.toLocaleString()}`;
}

export function _formatPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function _formatPercent(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}
