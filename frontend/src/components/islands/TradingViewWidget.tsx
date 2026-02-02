import { useEffect, useRef, useState } from "react";

interface TradingViewWidgetProps {
  symbol: string; // e.g., "NASDAQ:AAPL" or "AAPL"
  height?: number;
  theme?: "light" | "dark";
  // Indicator presets
  showRSI?: boolean;
  showMACD?: boolean;
  showBollingerBands?: boolean;
  showVolume?: boolean;
  // Chart settings
  interval?: "D" | "W" | "M" | "1" | "5" | "15" | "60";
  allowSymbolChange?: boolean;
}

// Theme colors matching PriceChart
const LIGHT_THEME = {
  background: "#ffffff",
  toolbar: "#f1f5f9",
};

const DARK_THEME = {
  background: "#1e293b",
  toolbar: "#334155",
};

// Detect current theme from document
function _getTheme(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  const theme = document.documentElement.dataset.theme;
  return theme === "dark" ? "dark" : "light";
}

// Format symbol to TradingView format
function _formatSymbol(symbol: string): string {
  // If already formatted (contains :), return as-is
  if (symbol.includes(":")) return symbol;
  // Default to NASDAQ for most stocks
  return `NASDAQ:${symbol}`;
}

// Build studies array from boolean flags
function _buildStudies(props: TradingViewWidgetProps): string[] {
  const studies: string[] = [];
  if (props.showRSI) studies.push("RSI@tv-basicstudies");
  if (props.showMACD) studies.push("MACD@tv-basicstudies");
  if (props.showBollingerBands) studies.push("BB@tv-basicstudies");
  if (props.showVolume) studies.push("Volume@tv-basicstudies");
  return studies;
}

export default function TradingViewWidget(props: TradingViewWidgetProps) {
  const {
    symbol,
    height = 500,
    theme,
    interval = "D",
    allowSymbolChange = false,
  } = props;

  const containerRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<TradingView.widget | null>(null);
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [scriptError, setScriptError] = useState(false);
  const [mounted, setMounted] = useState(false);
  const containerIdRef = useRef(`tradingview_${Math.random().toString(36).substring(7)}`);

  // Load TradingView script
  useEffect(() => {
    setMounted(true);

    // Check if script already loaded
    if (window.TradingView) {
      setScriptLoaded(true);
      return;
    }

    // Check if script is already being loaded
    const existingScript = document.querySelector('script[src*="tradingview.com/tv.js"]');
    if (existingScript) {
      existingScript.addEventListener("load", () => setScriptLoaded(true));
      existingScript.addEventListener("error", () => setScriptError(true));
      return;
    }

    // Load script
    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;
    script.onload = () => setScriptLoaded(true);
    script.onerror = () => setScriptError(true);
    document.head.appendChild(script);

    return () => {
      // Cleanup: remove script if component unmounts during load
      if (!scriptLoaded && !scriptError) {
        script.remove();
      }
    };
  }, []);

  // Initialize widget when script loads
  useEffect(() => {
    if (!mounted || !scriptLoaded || !containerRef.current || !window.TradingView) return;

    // Cleanup previous widget
    if (widgetRef.current) {
      try {
        widgetRef.current.remove();
      } catch (e) {
        console.warn("Failed to remove previous TradingView widget:", e);
      }
      widgetRef.current = null;
    }

    // Determine theme
    const currentTheme = theme ?? _getTheme();
    const themeColors = currentTheme === "dark" ? DARK_THEME : LIGHT_THEME;

    // Create widget
    try {
      widgetRef.current = new window.TradingView.widget({
        container_id: containerIdRef.current,
        symbol: _formatSymbol(symbol),
        interval,
        timezone: "Etc/UTC",
        theme: currentTheme,
        style: "1", // Candlestick
        locale: "en",
        toolbar_bg: themeColors.toolbar,
        enable_publishing: false,
        allow_symbol_change: allowSymbolChange,
        hide_side_toolbar: false,
        studies: _buildStudies(props),
        width: "100%",
        height,
        save_image: false,
        details: true,
        hotlist: false,
        calendar: false,
      });
    } catch (e) {
      console.error("Failed to create TradingView widget:", e);
      setScriptError(true);
    }

    return () => {
      if (widgetRef.current) {
        try {
          widgetRef.current.remove();
        } catch (e) {
          console.warn("Failed to remove TradingView widget:", e);
        }
        widgetRef.current = null;
      }
    };
  }, [mounted, scriptLoaded, symbol, interval, theme, allowSymbolChange, height, props]);

  // Watch for theme changes
  useEffect(() => {
    if (!mounted || theme) return; // Skip if theme is explicitly set

    const themeObserver = new MutationObserver(() => {
      // Recreate widget when theme changes
      if (widgetRef.current && window.TradingView) {
        try {
          widgetRef.current.remove();
        } catch (e) {
          console.warn("Failed to remove widget on theme change:", e);
        }

        const currentTheme = _getTheme();
        const themeColors = currentTheme === "dark" ? DARK_THEME : LIGHT_THEME;

        widgetRef.current = new window.TradingView.widget({
          container_id: containerIdRef.current,
          symbol: _formatSymbol(symbol),
          interval,
          timezone: "Etc/UTC",
          theme: currentTheme,
          style: "1",
          locale: "en",
          toolbar_bg: themeColors.toolbar,
          enable_publishing: false,
          allow_symbol_change: allowSymbolChange,
          hide_side_toolbar: false,
          studies: _buildStudies(props),
          width: "100%",
          height,
          save_image: false,
          details: true,
          hotlist: false,
          calendar: false,
        });
      }
    });

    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    return () => {
      themeObserver.disconnect();
    };
  }, [mounted, theme, symbol, interval, allowSymbolChange, height, props]);

  // Loading state
  if (!mounted || !scriptLoaded) {
    return (
      <div
        className="bg-bg-surface rounded-lg animate-pulse flex items-center justify-center"
        style={{ height }}
      >
        <span className="text-text-secondary text-sm">Loading TradingView chart...</span>
      </div>
    );
  }

  // Error state
  if (scriptError) {
    return (
      <div
        className="bg-bg-surface rounded-lg border border-danger/20 flex flex-col items-center justify-center gap-2 p-6"
        style={{ height }}
      >
        <span className="text-danger text-sm font-medium">Failed to load TradingView chart</span>
        <span className="text-text-muted text-xs">
          External scripts may be blocked by your browser or network
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Widget container */}
      <div
        id={containerIdRef.current}
        ref={containerRef}
        className="w-full rounded-lg overflow-hidden"
        style={{ height }}
        role="img"
        aria-label={`TradingView advanced chart for ${symbol}`}
      />
    </div>
  );
}
