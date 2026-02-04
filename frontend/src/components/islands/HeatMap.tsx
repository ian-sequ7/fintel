/**
 * HeatMap Component
 * Interactive Finviz-style heat map visualization of stock picks
 */

import React, { useState, useEffect, useRef, useMemo } from "react";
import type { StockPick } from "../../data/types";
import {
  _transformToHeatMapData,
  _calculateTileLayout,
  _filterByView,
  _groupBySector,
  _getColorForChange,
  _getTextColorForChange,
  _formatMarketCap,
  _formatPrice,
  _formatPercent,
  SECTOR_LABELS,
  SECTOR_COLORS,
  type HeatMapTileData,
  type TileLayout,
  type SizeByOption,
  type ViewOption,
} from "../../data/heatmap-utils";

// ============================================================================
// Types
// ============================================================================

interface HeatMapProps {
  stocks: StockPick[];
  initialSizeBy?: SizeByOption;
  initialView?: ViewOption;
}

interface TooltipData {
  tile: HeatMapTileData;
  x: number;
  y: number;
}

// ============================================================================
// Watchlist Integration
// ============================================================================

const WATCHLIST_KEY = "fintel_watchlist";

function _getWatchlistTickers(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = localStorage.getItem(WATCHLIST_KEY);
    if (!stored) return [];
    const watchlist = JSON.parse(stored);
    return watchlist.map((item: { ticker: string }) => item.ticker);
  } catch {
    return [];
  }
}

// ============================================================================
// Component
// ============================================================================

export default function HeatMap({
  stocks,
  initialSizeBy = "marketCap",
  initialView = "all",
}: HeatMapProps) {
  // Hydration safety
  const [mounted, setMounted] = useState(false);

  // Component state
  const [sizeBy, setSizeBy] = useState<SizeByOption>(initialSizeBy);
  const [view, setView] = useState<ViewOption>(initialView);
  const [watchlistTickers, setWatchlistTickers] = useState<string[]>([]);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);

  // Hydration
  useEffect(() => {
    setMounted(true);
    setWatchlistTickers(_getWatchlistTickers());
  }, []);

  // Watchlist sync
  useEffect(() => {
    if (!mounted) return;

    const handleUpdate = () => {
      setWatchlistTickers(_getWatchlistTickers());
    };

    window.addEventListener("watchlist-updated", handleUpdate);
    return () => window.removeEventListener("watchlist-updated", handleUpdate);
  }, [mounted]);

  // Responsive sizing
  useEffect(() => {
    if (!mounted || !containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width;
        if (width > 0) {
          setDimensions({
            width,
            height: Math.max(400, Math.min(600, width * 0.6)),
          });
        }
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [mounted]);

  // Transform data
  const tileData = useMemo(() => {
    if (!mounted) return [];
    const transformed = _transformToHeatMapData(stocks, sizeBy, watchlistTickers);
    return _filterByView(transformed, view);
  }, [stocks, sizeBy, view, watchlistTickers, mounted]);

  // Calculate layout
  const layouts = useMemo(() => {
    if (tileData.length === 0) return [];
    return _calculateTileLayout(tileData, dimensions.width, dimensions.height);
  }, [tileData, dimensions]);

  // Create tile lookup
  const tileMap = useMemo(() => {
    const map = new Map<string, HeatMapTileData>();
    for (const tile of tileData) {
      map.set(tile.ticker, tile);
    }
    return map;
  }, [tileData]);

  // Group by sector for "bySector" view
  const sectorGroups = useMemo(() => {
    if (view !== "bySector") return null;
    return _groupBySector(tileData);
  }, [tileData, view]);

  // Handle tile hover
  const handleTileHover = (
    ticker: string | null,
    event?: React.MouseEvent
  ) => {
    if (!ticker || !event) {
      setTooltip(null);
      return;
    }

    const tile = tileMap.get(ticker);
    if (tile) {
      const rect = containerRef.current?.getBoundingClientRect();
      setTooltip({
        tile,
        x: event.clientX - (rect?.left || 0),
        y: event.clientY - (rect?.top || 0),
      });
    }
  };

  // Handle tile click
  const handleTileClick = (ticker: string) => {
    window.location.href = `/stock/${ticker}`;
  };

  // Loading state
  if (!mounted) {
    return (
      <div className="bg-bg-surface border border-border rounded-lg p-8">
        <div className="animate-pulse flex flex-col items-center justify-center h-[400px]">
          <div className="h-4 bg-bg-elevated rounded w-32 mb-2" />
          <div className="text-text-secondary text-sm">Loading heat map...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="bg-bg-surface border border-border rounded-lg p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Index Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">Index:</span>
            <div className="flex rounded-lg border border-border overflow-hidden" role="group" aria-label="Index filter">
              {(
                [
                  { value: "all", label: "All" },
                  { value: "sp500", label: "S&P 500" },
                  { value: "dow", label: "Dow 30" },
                  { value: "nasdaq100", label: "NASDAQ-100" },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  onClick={() => setView(option.value)}
                  aria-label={`Filter by ${option.label}`}
                  aria-pressed={view === option.value}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                    view === option.value
                      ? "bg-text-primary text-bg-base"
                      : "bg-bg-elevated text-text-secondary hover:bg-bg-surface"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* View Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">View:</span>
            <div className="flex rounded-lg border border-border overflow-hidden" role="group" aria-label="View filter">
              {(
                [
                  { value: "watchlist", label: "Watchlist" },
                  { value: "topConviction", label: "Top 20" },
                  { value: "bySector", label: "By Sector" },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  onClick={() => setView(option.value)}
                  aria-label={`View ${option.label}`}
                  aria-pressed={view === option.value}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                    view === option.value
                      ? "bg-text-primary text-bg-base"
                      : "bg-bg-elevated text-text-secondary hover:bg-bg-surface"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Size By Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">Size by:</span>
            <div className="flex rounded-lg border border-border overflow-hidden" role="group" aria-label="Size by filter">
              {(
                [
                  { value: "marketCap", label: "Market Cap" },
                  { value: "conviction", label: "Conviction" },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  onClick={() => setSizeBy(option.value)}
                  aria-label={`Size by ${option.label}`}
                  aria-pressed={sizeBy === option.value}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                    sizeBy === option.value
                      ? "bg-text-primary text-bg-base"
                      : "bg-bg-elevated text-text-secondary hover:bg-bg-surface"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Legend */}
          <div className="flex items-center gap-2" role="img" aria-label="Color legend: red for negative 5% change, gray for neutral, green for positive 5% change">
            <div className="flex items-center gap-1">
              <div
                className="w-4 h-4 rounded"
                style={{ backgroundColor: "rgba(239, 68, 68, 0.8)" }}
                aria-hidden="true"
              />
              <span className="text-xs text-text-secondary">-5%</span>
            </div>
            <div className="w-24 h-4 rounded bg-gradient-to-r from-red-500 via-gray-400 to-green-500" aria-hidden="true" />
            <div className="flex items-center gap-1">
              <span className="text-xs text-text-secondary">+5%</span>
              <div
                className="w-4 h-4 rounded"
                style={{ backgroundColor: "rgba(34, 197, 94, 0.8)" }}
                aria-hidden="true"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Heat Map Container */}
      <div
        ref={containerRef}
        className="bg-bg-surface border border-border rounded-lg overflow-hidden relative"
        style={{ height: dimensions.height }}
      >
        {view === "bySector" && sectorGroups ? (
          // Sector-grouped view
          <div className="flex flex-wrap h-full">
            {Object.entries(sectorGroups).map(([sector, tiles]) => {
              if (tiles.length === 0) return null;
              const sectorWidth =
                (tiles.reduce((sum, t) => sum + t.value, 0) /
                  tileData.reduce((sum, t) => sum + t.value, 0)) *
                100;

              return (
                <div
                  key={sector}
                  className="relative border-r border-border last:border-r-0"
                  style={{ width: `${Math.max(sectorWidth, 8)}%`, height: "100%" }}
                >
                  <div
                    className="absolute top-0 left-0 right-0 px-2 py-1 text-xs font-medium text-white z-10"
                    style={{
                      backgroundColor: SECTOR_COLORS[sector as keyof typeof SECTOR_COLORS],
                    }}
                  >
                    {SECTOR_LABELS[sector as keyof typeof SECTOR_LABELS]}
                  </div>
                  <div className="pt-6 h-full relative">
                    {_calculateTileLayout(
                      tiles,
                      (dimensions.width * sectorWidth) / 100,
                      dimensions.height - 24
                    ).map((layout) => {
                      const tile = tileMap.get(layout.ticker);
                      if (!tile) return null;

                      return (
                        <HeatMapTile
                          key={tile.ticker}
                          tile={tile}
                          layout={layout}
                          onHover={handleTileHover}
                          onClick={handleTileClick}
                        />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          // Standard treemap view
          <>
            {layouts.map((layout) => {
              const tile = tileMap.get(layout.ticker);
              if (!tile) return null;

              return (
                <HeatMapTile
                  key={tile.ticker}
                  tile={tile}
                  layout={layout}
                  onHover={handleTileHover}
                  onClick={handleTileClick}
                />
              );
            })}
          </>
        )}

        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute z-50 bg-bg-elevated border border-border rounded-lg shadow-lg p-3 pointer-events-none"
            style={{
              left: Math.min(tooltip.x + 10, dimensions.width - 220),
              top: Math.min(tooltip.y + 10, dimensions.height - 180),
              maxWidth: 200,
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="font-mono font-bold text-accent">
                {tooltip.tile.ticker}
              </span>
              {tooltip.tile.isWatchlist && (
                <span className="text-yellow-500" aria-label="In watchlist">★</span>
              )}
            </div>
            <div className="text-sm text-text-secondary mb-2 line-clamp-1">
              {tooltip.tile.companyName}
            </div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Price:</span>
                <span className="font-medium">
                  {_formatPrice(tooltip.tile.currentPrice)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Change:</span>
                <span
                  className={`font-medium ${
                    tooltip.tile.priceChangePercent >= 0
                      ? "text-success"
                      : "text-danger"
                  }`}
                >
                  {_formatPercent(tooltip.tile.priceChangePercent)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Market Cap:</span>
                <span className="font-medium">
                  {_formatMarketCap(tooltip.tile.marketCap)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Conviction:</span>
                <span className="font-medium">
                  {Math.round(tooltip.tile.convictionScore * 10)}/10
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Sector:</span>
                <span className="font-medium">
                  {SECTOR_LABELS[tooltip.tile.sector]}
                </span>
              </div>
              {tooltip.tile.indices.length > 0 && (
                <div className="flex justify-between">
                  <span className="text-text-secondary">Indices:</span>
                  <span className="font-medium text-right">
                    {tooltip.tile.indices.join(", ")}
                  </span>
                </div>
              )}
            </div>
            <div className="mt-2 pt-2 border-t border-border text-xs text-text-secondary">
              Click to view details
            </div>
          </div>
        )}

        {/* Empty state */}
        {tileData.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="text-4xl mb-2" aria-hidden="true">
                {view === "watchlist" ? "★" : "📊"}
              </div>
              <div className="text-text-secondary">
                {view === "watchlist"
                  ? "No stocks in your watchlist"
                  : "No stocks to display"}
              </div>
              {view === "watchlist" && (
                <a
                  href="/picks"
                  className="text-accent hover:underline text-sm mt-2 inline-block"
                >
                  Browse picks to add to watchlist
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="flex flex-wrap gap-4 text-sm text-text-secondary">
        <span>{tileData.length} stocks</span>
        <span>•</span>
        <span>
          Avg change:{" "}
          <span
            className={
              tileData.reduce((sum, t) => sum + t.priceChangePercent, 0) /
                (tileData.length || 1) >=
              0
                ? "text-success"
                : "text-danger"
            }
          >
            {_formatPercent(
              tileData.reduce((sum, t) => sum + t.priceChangePercent, 0) /
                (tileData.length || 1)
            )}
          </span>
        </span>
        <span>•</span>
        <span>
          Total market cap:{" "}
          {_formatMarketCap(tileData.reduce((sum, t) => sum + t.marketCap, 0))}
        </span>
      </div>
    </div>
  );
}

// ============================================================================
// Tile Component
// ============================================================================

interface TileProps {
  tile: HeatMapTileData;
  layout: TileLayout;
  onHover: (ticker: string | null, event?: React.MouseEvent) => void;
  onClick: (ticker: string) => void;
}

const HeatMapTile = React.memo(
  ({ tile, layout, onHover, onClick }: TileProps) => {
    const isSmall = layout.width < 60 || layout.height < 40;
    const isTiny = layout.width < 40 || layout.height < 30;

    return (
      <div
        className="absolute cursor-pointer transition-all duration-150 hover:z-10 hover:scale-[1.02] hover:shadow-lg border border-black/10"
        style={{
          left: layout.x,
          top: layout.y,
          width: layout.width,
          height: layout.height,
          backgroundColor: _getColorForChange(tile.priceChangePercent),
          color: _getTextColorForChange(tile.priceChangePercent),
        }}
        role="button"
        tabIndex={0}
        aria-label={`${tile.ticker}, ${tile.priceChangePercent >= 0 ? "up" : "down"} ${Math.abs(tile.priceChangePercent).toFixed(2)}%, click for details`}
        onMouseEnter={(e) => onHover(tile.ticker, e)}
        onMouseMove={(e) => onHover(tile.ticker, e)}
        onMouseLeave={() => onHover(null)}
        onClick={() => onClick(tile.ticker)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick(tile.ticker);
          }
        }}
      >
        <div className="absolute inset-0 p-1 overflow-hidden flex flex-col justify-center items-center">
          {/* Ticker */}
          <div
            className={`font-mono font-bold leading-none ${
              isTiny ? "text-[8px]" : isSmall ? "text-xs" : "text-sm"
            }`}
          >
            {tile.ticker}
          </div>

          {/* Change % - hidden on tiny tiles */}
          {!isTiny && (
            <div
              className={`leading-none mt-0.5 ${
                isSmall ? "text-[8px]" : "text-xs"
              }`}
            >
              {_formatPercent(tile.priceChangePercent)}
            </div>
          )}

          {/* Watchlist star */}
          {tile.isWatchlist && !isTiny && (
            <div className="absolute top-0.5 right-0.5 text-yellow-300 text-xs" aria-hidden="true">
              ★
            </div>
          )}
        </div>
      </div>
    );
  },
  (prevProps, nextProps) => {
    // WHY: Custom comparison prevents re-renders when only parent callbacks change.
    // Only re-render if tile data or layout position/size actually changed.
    return (
      prevProps.tile.ticker === nextProps.tile.ticker &&
      prevProps.tile.priceChangePercent === nextProps.tile.priceChangePercent &&
      prevProps.tile.isWatchlist === nextProps.tile.isWatchlist &&
      prevProps.layout.x === nextProps.layout.x &&
      prevProps.layout.y === nextProps.layout.y &&
      prevProps.layout.width === nextProps.layout.width &&
      prevProps.layout.height === nextProps.layout.height
    );
  }
);

export { HeatMap };
