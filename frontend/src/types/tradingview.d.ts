// TypeScript declarations for TradingView Advanced Chart Widget
// Documentation: https://www.tradingview.com/widget/advanced-chart/

declare namespace TradingView {
  interface WidgetOptions {
    container_id: string;
    autosize?: boolean;
    width?: string | number;
    height?: number;
    symbol: string;
    interval: string;
    timezone?: string;
    theme: "light" | "dark";
    style: string;
    locale: string;
    toolbar_bg?: string;
    enable_publishing?: boolean;
    allow_symbol_change?: boolean;
    hide_side_toolbar?: boolean;
    details?: boolean;
    hotlist?: boolean;
    calendar?: boolean;
    studies?: string[];
    show_popup_button?: boolean;
    popup_width?: string;
    popup_height?: string;
    save_image?: boolean;
    hide_top_toolbar?: boolean;
    hide_legend?: boolean;
    withdateranges?: boolean;
  }

  class widget {
    constructor(options: WidgetOptions);
    remove(): void;
  }
}

declare global {
  interface Window {
    TradingView?: typeof TradingView;
  }
}

export {};
