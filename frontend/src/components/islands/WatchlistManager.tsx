import { useEffect, useState } from "react";

const STORAGE_KEY = "fintel_watchlist";

export type WatchlistStock = {
  ticker: string;
  companyName: string;
  addedAt: string; // ISO date string
  notes?: string;
};

// Get watchlist from localStorage
export function _getWatchlist(): WatchlistStock[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

// Save watchlist to localStorage
function _saveWatchlist(stocks: WatchlistStock[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(stocks));
  window.dispatchEvent(new CustomEvent("watchlist-updated", { detail: stocks }));
}

// Add stock to watchlist
export function addToWatchlist(ticker: string, companyName: string): boolean {
  const current = _getWatchlist();
  if (current.some((s) => s.ticker === ticker)) return false;
  _saveWatchlist([
    ...current,
    { ticker, companyName, addedAt: new Date().toISOString() },
  ]);
  return true;
}

// Remove stock from watchlist
export function removeFromWatchlist(ticker: string): void {
  const current = _getWatchlist();
  _saveWatchlist(current.filter((s) => s.ticker !== ticker));
}

// Check if stock is in watchlist
export function isInWatchlist(ticker: string): boolean {
  return _getWatchlist().some((s) => s.ticker === ticker);
}

// Update notes for a stock
export function updateWatchlistNotes(ticker: string, notes: string): void {
  const current = _getWatchlist();
  _saveWatchlist(
    current.map((s) => (s.ticker === ticker ? { ...s, notes } : s))
  );
}

interface WatchlistButtonProps {
  ticker: string;
  companyName: string;
  size?: "sm" | "md";
  variant?: "icon" | "text";
}

// Button to add/remove stock from watchlist
export function WatchlistButton({
  ticker,
  companyName,
  size = "md",
  variant = "icon",
}: WatchlistButtonProps) {
  const [inWatchlist, setInWatchlist] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setInWatchlist(isInWatchlist(ticker));

    const handleUpdate = () => setInWatchlist(isInWatchlist(ticker));
    window.addEventListener("watchlist-updated", handleUpdate);
    window.addEventListener("storage", handleUpdate);

    return () => {
      window.removeEventListener("watchlist-updated", handleUpdate);
      window.removeEventListener("storage", handleUpdate);
    };
  }, [ticker]);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (inWatchlist) {
      removeFromWatchlist(ticker);
    } else {
      addToWatchlist(ticker, companyName);
    }
  };

  if (!mounted) return null;

  if (variant === "icon") {
    const sizeClass = size === "sm" ? "w-6 h-6" : "w-8 h-8";
    return (
      <button
        onClick={handleClick}
        className={`${sizeClass} flex items-center justify-center rounded transition-colors ${
          inWatchlist
            ? "text-warning hover:text-warning/80"
            : "text-text-muted hover:text-warning"
        }`}
        title={inWatchlist ? "Remove from watchlist" : "Add to watchlist"}
      >
        <svg
          className="w-5 h-5"
          fill={inWatchlist ? "currentColor" : "none"}
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
          />
        </svg>
      </button>
    );
  }

  const sizeClasses = size === "sm" ? "text-xs px-2 py-1" : "text-sm px-3 py-1.5";

  return (
    <button
      onClick={handleClick}
      className={`${sizeClasses} rounded font-medium transition-colors flex items-center gap-1 ${
        inWatchlist
          ? "bg-warning/20 text-warning hover:bg-warning/30"
          : "bg-bg-elevated text-text-secondary hover:text-text-primary hover:bg-bg-surface border border-border"
      }`}
      title={inWatchlist ? "Remove from watchlist" : "Add to watchlist"}
    >
      <svg
        className="w-4 h-4"
        fill={inWatchlist ? "currentColor" : "none"}
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
        />
      </svg>
      {inWatchlist ? "Watching" : "Watch"}
    </button>
  );
}

// Watchlist count badge for header
export function WatchlistBadge() {
  const [count, setCount] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setCount(_getWatchlist().length);

    const handleUpdate = () => setCount(_getWatchlist().length);
    window.addEventListener("watchlist-updated", handleUpdate);
    window.addEventListener("storage", handleUpdate);

    return () => {
      window.removeEventListener("watchlist-updated", handleUpdate);
      window.removeEventListener("storage", handleUpdate);
    };
  }, []);

  if (!mounted || count === 0) return null;

  return (
    <span className="absolute -top-1 -right-1 w-4 h-4 bg-warning text-white text-[10px] font-bold rounded-full flex items-center justify-center">
      {count > 9 ? "9+" : count}
    </span>
  );
}
