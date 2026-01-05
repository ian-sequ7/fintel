import { useEffect, useState } from "react";

type MarketState = "pre-market" | "open" | "after-hours" | "closed";

interface MarketStatusInfo {
  state: MarketState;
  label: string;
  nextEvent: string;
}

// US market holidays (NYSE/NASDAQ) - 2024-2026
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
  // 2026
  "2026-01-01", // New Year's Day
  "2026-01-19", // MLK Day
  "2026-02-16", // Presidents Day
  "2026-04-03", // Good Friday
  "2026-05-25", // Memorial Day
  "2026-06-19", // Juneteenth
  "2026-07-03", // Independence Day (observed)
  "2026-09-07", // Labor Day
  "2026-11-26", // Thanksgiving
  "2026-12-25", // Christmas
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
    };
  }

  if (isHoliday) {
    return {
      state: "closed",
      label: "Market Closed (Holiday)",
      nextEvent: "Opens Next Trading Day 9:30 AM ET",
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
    };
  }

  // Outside trading hours
  return {
    state: "closed",
    label: "Market Closed",
    nextEvent: "Opens 9:30 AM ET",
  };
}

// SVG Icons for each market state
function SunriseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2v4" />
      <path d="m4.93 4.93 2.83 2.83" />
      <path d="M2 12h4" />
      <path d="m4.93 19.07 2.83-2.83" />
      <path d="M12 18v4" />
      <path d="m19.07 19.07-2.83-2.83" />
      <path d="M22 12h-4" />
      <path d="m19.07 4.93-2.83 2.83" />
      <path d="M12 12a4 4 0 0 0-4 4" />
      <path d="M12 12a4 4 0 0 1 4 4" />
      <line x1="2" y1="20" x2="22" y2="20" />
    </svg>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="m7 16 4-4 4 4 6-6" />
      <circle cx="21" cy="10" r="1" fill="currentColor" />
    </svg>
  );
}

function MoonIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

// Get icon and styling for each market state
function _getMarketIcon(state: MarketState) {
  switch (state) {
    case "pre-market":
      return {
        Icon: SunriseIcon,
        bgClass: "bg-[var(--market-premarket-bg)]",
        textClass: "text-[var(--market-premarket)]",
        borderClass: "border-[var(--market-premarket)]",
      };
    case "open":
      return {
        Icon: ChartIcon,
        bgClass: "bg-[var(--market-open-bg)]",
        textClass: "text-[var(--market-open)]",
        borderClass: "border-[var(--market-open)]",
      };
    case "after-hours":
      return {
        Icon: MoonIcon,
        bgClass: "bg-[var(--market-afterhours-bg)]",
        textClass: "text-[var(--market-afterhours)]",
        borderClass: "border-[var(--market-afterhours)]",
      };
    case "closed":
    default:
      return {
        Icon: ClockIcon,
        bgClass: "bg-[var(--market-closed-bg)]",
        textClass: "text-[var(--market-closed)]",
        borderClass: "border-[var(--market-closed)]",
      };
  }
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
        <span className="text-text-secondary">Loading...</span>
      </div>
    );
  }

  const { Icon, bgClass, textClass, borderClass } = _getMarketIcon(status.state);

  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${bgClass} ${textClass} border ${borderClass}`}>
        <Icon className="w-3.5 h-3.5" />
        <span>{status.label}</span>
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md border ${bgClass} ${textClass} ${borderClass}`}>
      <Icon className={`w-4 h-4 ${status.state === "open" ? "animate-pulse" : ""}`} />
      <div className="flex items-center gap-2 text-sm">
        <span className="font-semibold">{status.label}</span>
        <span className="opacity-75 text-xs">{status.nextEvent}</span>
      </div>
    </div>
  );
}
