import { useState } from "react";
import PaperTradeForm from "./PaperTradeForm";

interface PaperTradeButtonProps {
  ticker: string;
  companyName: string;
  currentPrice: number;
  size?: "sm" | "md" | "lg";
  variant?: "primary" | "secondary" | "icon";
}

export default function PaperTradeButton({
  ticker,
  companyName,
  currentPrice,
  size = "md",
  variant = "primary",
}: PaperTradeButtonProps) {
  const [isOpen, setIsOpen] = useState(false);

  const sizeClasses = {
    sm: "px-2 py-1 text-xs",
    md: "px-3 py-1.5 text-sm",
    lg: "px-4 py-2 text-base",
  };

  const variantClasses = {
    primary: "bg-text-primary text-bg-base hover:opacity-90",
    secondary: "bg-bg-elevated border border-border text-text-primary hover:border-accent",
    icon: "p-2 bg-bg-elevated border border-border text-text-secondary hover:text-accent hover:border-accent",
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className={`
          rounded-lg font-medium transition-colors flex items-center gap-1.5
          ${variant === "icon" ? variantClasses.icon : `${sizeClasses[size]} ${variantClasses[variant]}`}
        `}
        title="Paper Trade"
      >
        {variant === "icon" ? (
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
              d="M12 6v6m0 0v6m0-6h6m-6 0H6"
            />
          </svg>
        ) : (
          <>
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6v6m0 0v6m0-6h6m-6 0H6"
              />
            </svg>
            <span>Paper Trade</span>
          </>
        )}
      </button>

      {isOpen && (
        <PaperTradeForm
          ticker={ticker}
          companyName={companyName}
          currentPrice={currentPrice}
          onClose={() => setIsOpen(false)}
        />
      )}
    </>
  );
}
