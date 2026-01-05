import { useState } from "react";
import { addPaperTrade } from "../../data/portfolio";

interface PaperTradeFormProps {
  ticker: string;
  companyName: string;
  currentPrice: number;
  onClose: () => void;
  onSuccess?: () => void;
}

export default function PaperTradeForm({
  ticker,
  companyName,
  currentPrice,
  onClose,
  onSuccess,
}: PaperTradeFormProps) {
  const [shares, setShares] = useState<number>(1);
  const [entryPrice, setEntryPrice] = useState<number>(currentPrice);
  const [notes, setNotes] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const totalCost = shares * entryPrice;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (shares <= 0) {
      setError("Shares must be greater than 0");
      return;
    }

    if (entryPrice <= 0) {
      setError("Entry price must be greater than 0");
      return;
    }

    try {
      addPaperTrade({
        ticker: ticker.toUpperCase(),
        companyName,
        shares,
        entryPrice,
        entryDate: new Date().toISOString(),
        notes: notes.trim() || undefined,
      });

      onSuccess?.();
      onClose();
    } catch (err) {
      setError("Failed to save trade. Please try again.");
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-bg-surface border border-border rounded-lg shadow-xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div>
            <h2 className="text-lg font-bold text-text-primary">Paper Trade</h2>
            <p className="text-sm text-text-secondary">
              <span className="font-mono font-bold text-accent">{ticker}</span>
              {" · "}
              {companyName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-text-muted hover:text-text-primary hover:bg-bg-elevated rounded transition-colors"
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
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-3 bg-danger/10 border border-danger/30 rounded text-danger text-sm">
              {error}
            </div>
          )}

          {/* Current Price Display */}
          <div className="p-3 bg-bg-elevated rounded-lg">
            <div className="text-xs text-text-secondary mb-1">Current Market Price</div>
            <div className="text-xl font-bold text-text-primary">
              ${currentPrice.toFixed(2)}
            </div>
          </div>

          {/* Shares Input */}
          <div>
            <label
              htmlFor="shares"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Number of Shares
            </label>
            <input
              type="number"
              id="shares"
              value={shares}
              onChange={(e) => setShares(Math.max(0, parseInt(e.target.value) || 0))}
              min="1"
              step="1"
              className="w-full bg-bg-elevated border border-border rounded-lg px-3 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
            />
          </div>

          {/* Entry Price Input */}
          <div>
            <label
              htmlFor="entryPrice"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Entry Price
              <span className="text-text-muted font-normal ml-2">
                (defaults to current price)
              </span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary">
                $
              </span>
              <input
                type="number"
                id="entryPrice"
                value={entryPrice}
                onChange={(e) => setEntryPrice(Math.max(0, parseFloat(e.target.value) || 0))}
                min="0.01"
                step="0.01"
                className="w-full bg-bg-elevated border border-border rounded-lg pl-7 pr-3 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
              />
            </div>
            {entryPrice !== currentPrice && (
              <button
                type="button"
                onClick={() => setEntryPrice(currentPrice)}
                className="text-xs text-accent hover:underline mt-1"
              >
                Reset to current price
              </button>
            )}
          </div>

          {/* Notes Input */}
          <div>
            <label
              htmlFor="notes"
              className="block text-sm font-medium text-text-secondary mb-1"
            >
              Notes
              <span className="text-text-muted font-normal ml-2">(optional)</span>
            </label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Why are you making this trade?"
              className="w-full bg-bg-elevated border border-border rounded-lg px-3 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent resize-none"
            />
          </div>

          {/* Total Cost Display */}
          <div className="p-3 bg-accent/10 border border-accent/30 rounded-lg">
            <div className="flex justify-between items-center">
              <span className="text-sm text-text-secondary">Total Cost</span>
              <span className="text-lg font-bold text-accent">
                ${totalCost.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            </div>
            <div className="text-xs text-text-muted mt-1">
              {shares} shares × ${entryPrice.toFixed(2)}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-border rounded-lg text-text-secondary hover:bg-bg-elevated transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors font-medium"
            >
              Enter Trade
            </button>
          </div>
        </form>

        {/* Footer disclaimer */}
        <div className="px-4 pb-4">
          <p className="text-xs text-text-muted text-center">
            This is a paper trade for educational purposes only. No real money is involved.
          </p>
        </div>
      </div>
    </div>
  );
}
