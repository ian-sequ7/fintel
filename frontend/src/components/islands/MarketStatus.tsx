import { useEffect, useState } from "react";

type MarketState = "pre-market" | "open" | "after-hours" | "closed";

interface MarketStatusInfo {
  state: MarketState;
  label: string;
  nextEvent: string;
  color: string;
}

// US market holidays (NYSE/NASDAQ) - 2024-2025
const MARKET_HOLIDAYS = new Set([
  // 2024
  "2024-01-01", // New Year's Day
  "2024-01-15", // MLK Day
  "2024-02-19", // Presidents Day
  "2024-03-29", // Good Friday
  "2024-05-27", // Memorial Day
  "2024-06-19", // Juneteenth
  "2024-07-04", // Independence Day
  "2024-09-02", // Labor Day
  "2024-11-28", // Thanksgiving
  "2024-12-25", // Christmas
  // 2025
  "2025-01-01", // New Year's Day
  "2025-01-20", // MLK Day
  "2025-02-17", // Presidents Day
  "2025-04-18", // Good Friday
  "2025-05-26", // Memorial Day
  "2025-06-19", // Juneteenth
  "2025-07-04", // Independence Day
  "2025-09-01", // Labor Day
  "2025-11-27", // Thanksgiving
  "2025-12-25", // Christmas
]);

function _getMarketStatus(): MarketStatusInfo {
  const now = new Date();

  // Get Eastern Time (US markets)
  const etFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    weekday: "short",
  });

  const etParts = etFormatter.formatToParts(now);
  const weekday = etParts.find((p) => p.type === "weekday")?.value || "";
  const hour = parseInt(etParts.find((p) => p.type === "hour")?.value || "0");
  const minute = parseInt(etParts.find((p) => p.type === "minute")?.value || "0");

  const currentMinutes = hour * 60 + minute;

  // Pre-market: 4:00 AM - 9:30 AM ET
  const preMarketStart = 4 * 60; // 4:00 AM
  const marketOpen = 9 * 60 + 30; // 9:30 AM
  const marketClose = 16 * 60; // 4:00 PM
  const afterHoursEnd = 20 * 60; // 8:00 PM

  // Check if weekend
  const isWeekend = weekday === "Sat" || weekday === "Sun";

  // Check if holiday
  const dateStr = now.toISOString().split("T")[0];
  const isHoliday = MARKET_HOLIDAYS.has(dateStr);

  if (isWeekend) {
    return {
      state: "closed",
      label: "Market Closed",
      nextEvent: weekday === "Sat" ? "Opens Monday 9:30 AM ET" : "Opens Tomorrow 9:30 AM ET",
      color: "text-text-muted",
    };
  }

  if (isHoliday) {
    return {
      state: "closed",
      label: "Market Closed (Holiday)",
      nextEvent: "Opens Next Trading Day 9:30 AM ET",
      color: "text-text-muted",
    };
  }

  // Check market hours
  if (currentMinutes >= preMarketStart && currentMinutes < marketOpen) {
    const minsToOpen = marketOpen - currentMinutes;
    const hours = Math.floor(minsToOpen / 60);
    const mins = minsToOpen % 60;
    return {
      state: "pre-market",
      label: "Pre-Market",
      nextEvent: hours > 0 ? `Opens in ${hours}h ${mins}m` : `Opens in ${mins}m`,
      color: "text-warning",
    };
  }

  if (currentMinutes >= marketOpen && currentMinutes < marketClose) {
    const minsToClose = marketClose - currentMinutes;
    const hours = Math.floor(minsToClose / 60);
    const mins = minsToClose % 60;
    return {
      state: "open",
      label: "Market Open",
      nextEvent: hours > 0 ? `Closes in ${hours}h ${mins}m` : `Closes in ${mins}m`,
      color: "text-success",
    };
  }

  if (currentMinutes >= marketClose && currentMinutes < afterHoursEnd) {
    const minsToEnd = afterHoursEnd - currentMinutes;
    const hours = Math.floor(minsToEnd / 60);
    const mins = minsToEnd % 60;
    return {
      state: "after-hours",
      label: "After Hours",
      nextEvent: hours > 0 ? `Ends in ${hours}h ${mins}m` : `Ends in ${mins}m`,
      color: "text-warning",
    };
  }

  // Outside trading hours
  return {
    state: "closed",
    label: "Market Closed",
    nextEvent: "Opens 9:30 AM ET",
    color: "text-text-muted",
  };
}

interface Props {
  compact?: boolean;
}

export default function MarketStatus({ compact = false }: Props) {
  const [status, setStatus] = useState<MarketStatusInfo | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setStatus(_getMarketStatus());

    // Update every minute
    const interval = setInterval(() => {
      setStatus(_getMarketStatus());
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  if (!mounted || !status) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="w-2 h-2 rounded-full bg-bg-elevated animate-pulse" />
        <span className="text-text-muted">Loading...</span>
      </div>
    );
  }

  if (compact) {
    return (
      <div className="flex items-center gap-1.5 text-xs">
        <span
          className={`w-2 h-2 rounded-full ${
            status.state === "open"
              ? "bg-success animate-pulse"
              : status.state === "pre-market" || status.state === "after-hours"
                ? "bg-warning"
                : "bg-text-muted"
          }`}
        />
        <span className={status.color}>{status.label}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={`w-2.5 h-2.5 rounded-full ${
          status.state === "open"
            ? "bg-success animate-pulse"
            : status.state === "pre-market" || status.state === "after-hours"
              ? "bg-warning"
              : "bg-text-muted"
        }`}
      />
      <div>
        <span className={`font-medium ${status.color}`}>{status.label}</span>
        <span className="text-text-muted ml-2">{status.nextEvent}</span>
      </div>
    </div>
  );
}
