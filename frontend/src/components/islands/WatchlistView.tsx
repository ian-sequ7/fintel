import { useCallback, useEffect, useMemo, useState } from "react";
import {
  _getWatchlist,
  removeFromWatchlist,
  updateWatchlistNotes,
  type WatchlistStock,
} from "./WatchlistManager";
import { getStockDetails } from "../../data/lazy";

interface StockDetail {
  ticker: string;
  companyName: string;
  currentPrice: number;
  priceChange: number;
  priceChangePercent: number;
  convictionScore: number;
  timeframe: string;
  sector: string;
  entryPrice?: number;
  targetPrice?: number;
}

interface Props {
  stockDetails?: Record<string, StockDetail>;
}

function _formatPrice(price?: number): string {
  if (price === undefined) return "-";
  return `$${price.toFixed(2)}`;
}

function _formatRelativeTime(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  return date.toLocaleDateString();
}

export default function WatchlistView({ stockDetails: initialStockDetails }: Props) {
  const [watchlist, setWatchlist] = useState<WatchlistStock[]>([]);
  const [mounted, setMounted] = useState(false);
  const [editingNotes, setEditingNotes] = useState<string | null>(null);
  const [noteText, setNoteText] = useState("");
  const [stockDetails, setStockDetails] = useState<Record<string, StockDetail>>(initialStockDetails ?? {});
  const [loading, setLoading] = useState(!initialStockDetails);

  useEffect(() => {
    setMounted(true);
    setWatchlist(_getWatchlist());

    // Lazy load stock details if not provided
    if (!initialStockDetails) {
      getStockDetails().then((data) => {
        setStockDetails(data as Record<string, StockDetail>);
        setLoading(false);
      });
    }

    const handleUpdate = () => setWatchlist(_getWatchlist());
    window.addEventListener("watchlist-updated", handleUpdate);
    window.addEventListener("storage", handleUpdate);

    return () => {
      window.removeEventListener("watchlist-updated", handleUpdate);
      window.removeEventListener("storage", handleUpdate);
    };
  }, []);

  const handleRemove = useCallback((ticker: string) => {
    removeFromWatchlist(ticker);
  }, []);

  const handleEditNotes = useCallback((ticker: string, currentNotes?: string) => {
    setEditingNotes(ticker);
    setNoteText(currentNotes || "");
  }, []);

  const handleSaveNotes = useCallback((ticker: string) => {
    updateWatchlistNotes(ticker, noteText);
    setEditingNotes(null);
    setNoteText("");
  }, [noteText]);

  if (!mounted) {
    return (
      <div className="text-center py-12 text-text-secondary">
        Loading watchlist...
      </div>
    );
  }

  if (watchlist.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-6xl mb-4">⭐</div>
        <h2 className="text-xl font-semibold text-text-primary mb-2">
          Your watchlist is empty
        </h2>
        <p className="text-text-secondary mb-4">
          Add stocks to your watchlist by clicking the star icon on any pick.
        </p>
        <a
          href="/picks"
          className="inline-block bg-text-primary text-bg-base px-4 py-2 rounded font-medium hover:opacity-90 transition-opacity"
        >
          Browse Picks
        </a>
      </div>
    );
  }

  // Calculate portfolio summary
  const { totalValue, totalChange, avgConviction } = useMemo(() => {
    const totalValue = watchlist.reduce((sum, item) => {
      const detail = stockDetails[item.ticker];
      return sum + (detail?.currentPrice || 0);
    }, 0);

    const totalChange = watchlist.reduce((sum, item) => {
      const detail = stockDetails[item.ticker];
      return sum + (detail?.priceChange || 0);
    }, 0);

    const avgConviction =
      watchlist.reduce((sum, item) => {
        const detail = stockDetails[item.ticker];
        return sum + (detail?.convictionScore || 0);
      }, 0) / watchlist.length;

    return { totalValue, totalChange, avgConviction };
  }, [watchlist, stockDetails]);

  return (
    <div>
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-bg-surface border border-border rounded-lg p-4">
          <p className="text-xs text-text-secondary uppercase tracking-wide mb-1">
            Stocks Watching
          </p>
          <p className="text-2xl font-bold text-text-primary">
            {watchlist.length}
          </p>
        </div>
        <div className="bg-bg-surface border border-border rounded-lg p-4">
          <p className="text-xs text-text-secondary uppercase tracking-wide mb-1">
            Combined Price
          </p>
          <p className="text-2xl font-bold text-text-primary">
            {_formatPrice(totalValue)}
          </p>
        </div>
        <div className="bg-bg-surface border border-border rounded-lg p-4">
          <p className="text-xs text-text-secondary uppercase tracking-wide mb-1">
            Today's Change
          </p>
          <p
            className={`text-2xl font-bold ${
              totalChange >= 0 ? "text-success" : "text-danger"
            }`}
          >
            {totalChange >= 0 ? "+" : ""}
            {totalChange.toFixed(2)}
          </p>
        </div>
        <div className="bg-bg-surface border border-border rounded-lg p-4">
          <p className="text-xs text-text-secondary uppercase tracking-wide mb-1">
            Avg Conviction
          </p>
          <p className="text-2xl font-bold text-text-primary">
            {Math.round(avgConviction * 100)}%
          </p>
        </div>
      </div>

      {/* Watchlist table */}
      <div className="bg-bg-surface border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border bg-bg-elevated">
                <th className="text-left p-4 text-text-secondary font-medium text-sm">
                  Stock
                </th>
                <th className="text-right p-4 text-text-secondary font-medium text-sm">
                  Price
                </th>
                <th className="text-right p-4 text-text-secondary font-medium text-sm">
                  Change
                </th>
                <th className="text-center p-4 text-text-secondary font-medium text-sm">
                  Conviction
                </th>
                <th className="text-left p-4 text-text-secondary font-medium text-sm">
                  Notes
                </th>
                <th className="text-center p-4 text-text-secondary font-medium text-sm">
                  Added
                </th>
                <th className="text-center p-4 text-text-secondary font-medium text-sm w-20">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {watchlist.map((item) => {
                const detail = stockDetails[item.ticker];
                const isEditing = editingNotes === item.ticker;

                return (
                  <tr
                    key={item.ticker}
                    className="border-b border-border last:border-0 hover:bg-bg-elevated/50"
                  >
                    <td className="p-4">
                      <a
                        href={`/stock/${item.ticker}`}
                        className="flex items-center gap-3 hover:text-accent"
                      >
                        <span className="font-mono font-bold text-accent">
                          {item.ticker}
                        </span>
                        <span className="text-text-secondary text-sm">
                          {item.companyName}
                        </span>
                      </a>
                    </td>
                    <td className="p-4 text-right font-semibold text-text-primary">
                      {_formatPrice(detail?.currentPrice)}
                    </td>
                    <td
                      className={`p-4 text-right font-medium ${
                        (detail?.priceChange || 0) >= 0
                          ? "text-success"
                          : "text-danger"
                      }`}
                    >
                      {detail
                        ? `${detail.priceChange >= 0 ? "+" : ""}${detail.priceChange.toFixed(2)} (${detail.priceChangePercent >= 0 ? "+" : ""}${detail.priceChangePercent.toFixed(2)}%)`
                        : "-"}
                    </td>
                    <td className="p-4 text-center">
                      {detail ? (
                        <span
                          className={`inline-block px-2 py-1 rounded text-sm font-medium ${
                            detail.convictionScore >= 0.7
                              ? "bg-success/20 text-success"
                              : detail.convictionScore >= 0.4
                                ? "bg-warning/20 text-warning"
                                : "bg-danger/20 text-danger"
                          }`}
                        >
                          {Math.round(detail.convictionScore * 100)}%
                        </span>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td className="p-4 max-w-[200px]">
                      {isEditing ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={noteText}
                            onChange={(e) => setNoteText(e.target.value)}
                            className="flex-1 bg-bg-elevated border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                            placeholder="Add notes..."
                            autoFocus
                          />
                          <button
                            onClick={() => handleSaveNotes(item.ticker)}
                            className="text-success hover:text-success/80 text-sm"
                          >
                            Save
                          </button>
                          <button
                            onClick={() => setEditingNotes(null)}
                            className="text-text-muted hover:text-danger text-sm"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleEditNotes(item.ticker, item.notes)}
                          className="text-sm text-text-secondary hover:text-text-primary truncate block max-w-full text-left"
                        >
                          {item.notes || (
                            <span className="text-text-muted italic">
                              Add notes...
                            </span>
                          )}
                        </button>
                      )}
                    </td>
                    <td className="p-4 text-center text-sm text-text-secondary">
                      {_formatRelativeTime(item.addedAt)}
                    </td>
                    <td className="p-4 text-center">
                      <button
                        onClick={() => handleRemove(item.ticker)}
                        className="text-text-muted hover:text-danger transition-colors p-1"
                        title="Remove from watchlist"
                      >
                        <svg
                          className="w-5 h-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
