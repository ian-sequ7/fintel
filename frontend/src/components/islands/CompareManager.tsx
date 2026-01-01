import { useEffect, useState } from "react";

const STORAGE_KEY = "fintel_compare_stocks";
const MAX_COMPARE = 3;

export type CompareStock = {
  ticker: string;
  companyName: string;
};

// Get compared stocks from localStorage
export function _getCompareStocks(): CompareStock[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

// Save compared stocks to localStorage
function _saveCompareStocks(stocks: CompareStock[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(stocks));
  // Dispatch custom event for other components to listen
  window.dispatchEvent(new CustomEvent("compare-updated", { detail: stocks }));
}

// Add stock to compare list
export function addToCompare(stock: CompareStock): boolean {
  const current = _getCompareStocks();
  if (current.length >= MAX_COMPARE) return false;
  if (current.some((s) => s.ticker === stock.ticker)) return false;
  _saveCompareStocks([...current, stock]);
  return true;
}

// Remove stock from compare list
export function removeFromCompare(ticker: string): void {
  const current = _getCompareStocks();
  _saveCompareStocks(current.filter((s) => s.ticker !== ticker));
}

// Clear all stocks from compare list
export function clearCompare(): void {
  _saveCompareStocks([]);
}

// Check if stock is in compare list
export function isInCompare(ticker: string): boolean {
  return _getCompareStocks().some((s) => s.ticker === ticker);
}

interface CompareButtonProps {
  ticker: string;
  companyName: string;
  size?: "sm" | "md";
}

// Button to add/remove stock from compare
export function CompareButton({ ticker, companyName, size = "md" }: CompareButtonProps) {
  const [inCompare, setInCompare] = useState(false);
  const [compareCount, setCompareCount] = useState(0);

  useEffect(() => {
    const updateState = () => {
      setInCompare(isInCompare(ticker));
      setCompareCount(_getCompareStocks().length);
    };

    updateState();

    const handleUpdate = () => updateState();
    window.addEventListener("compare-updated", handleUpdate);
    window.addEventListener("storage", handleUpdate);

    return () => {
      window.removeEventListener("compare-updated", handleUpdate);
      window.removeEventListener("storage", handleUpdate);
    };
  }, [ticker]);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (inCompare) {
      removeFromCompare(ticker);
    } else {
      if (compareCount >= MAX_COMPARE) {
        alert(`You can only compare up to ${MAX_COMPARE} stocks at a time.`);
        return;
      }
      addToCompare({ ticker, companyName });
    }
  };

  const sizeClasses = size === "sm"
    ? "text-xs px-2 py-1"
    : "text-sm px-3 py-1.5";

  return (
    <button
      onClick={handleClick}
      className={`${sizeClasses} rounded font-medium transition-colors ${
        inCompare
          ? "bg-accent text-white hover:bg-accent/80"
          : "bg-bg-elevated text-text-secondary hover:text-text-primary hover:bg-bg-surface border border-border"
      }`}
      title={inCompare ? "Remove from comparison" : "Add to comparison"}
    >
      {inCompare ? "✓ Comparing" : "+ Compare"}
    </button>
  );
}

// Floating compare bar that shows when stocks are selected
export function CompareBar() {
  const [stocks, setStocks] = useState<CompareStock[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setStocks(_getCompareStocks());

    const handleUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<CompareStock[]>;
      setStocks(customEvent.detail || _getCompareStocks());
    };

    window.addEventListener("compare-updated", handleUpdate);
    window.addEventListener("storage", () => setStocks(_getCompareStocks()));

    return () => {
      window.removeEventListener("compare-updated", handleUpdate);
      window.removeEventListener("storage", () => setStocks(_getCompareStocks()));
    };
  }, []);

  if (!mounted || stocks.length === 0) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-bg-surface border border-border rounded-lg shadow-lg p-3 flex items-center gap-3">
      <div className="flex items-center gap-2">
        {stocks.map((stock) => (
          <div
            key={stock.ticker}
            className="flex items-center gap-1.5 bg-bg-elevated rounded px-2 py-1"
          >
            <span className="font-mono font-medium text-accent text-sm">
              {stock.ticker}
            </span>
            <button
              onClick={() => removeFromCompare(stock.ticker)}
              className="text-text-muted hover:text-danger text-xs"
              title="Remove"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 ml-2">
        <a
          href="/compare"
          className="bg-accent text-white px-4 py-1.5 rounded text-sm font-medium hover:bg-accent/90 transition-colors"
        >
          Compare {stocks.length}
        </a>
        <button
          onClick={() => clearCompare()}
          className="text-text-muted hover:text-danger text-sm"
          title="Clear all"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
