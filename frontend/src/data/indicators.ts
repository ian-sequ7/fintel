/**
 * Technical indicator calculations for frontend charting.
 * Matches Python domain/indicators/ implementations.
 *
 * @deprecated These functions are kept as fallback only.
 * Indicators are now computed server-side and included in StockDetail.indicators.
 * Frontend components should prefer pre-computed indicators when available.
 */

/**
 * Simple Moving Average - average of last N values.
 */
export function sma(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];

  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      const sum = values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
      result.push(sum / period);
    }
  }

  return result;
}

/**
 * Exponential Moving Average - weighted average giving more weight to recent values.
 */
export function ema(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  const multiplier = 2 / (period + 1);

  // First EMA value is SMA
  let ema: number | null = null;

  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else if (i === period - 1) {
      // First EMA is SMA
      const sum = values.slice(0, period).reduce((a, b) => a + b, 0);
      ema = sum / period;
      result.push(ema);
    } else {
      // EMA = (Close - EMA(previous)) * multiplier + EMA(previous)
      ema = (values[i] - ema!) * multiplier + ema!;
      result.push(ema);
    }
  }

  return result;
}

/**
 * RSI calculation using Wilder's smoothing.
 * Returns values from 0-100, with >70 overbought, <30 oversold.
 */
export function rsi(closes: number[], period: number = 14): (number | null)[] {
  const result: (number | null)[] = [];

  if (closes.length < period + 1) {
    return new Array(closes.length).fill(null);
  }

  // Calculate price changes
  const changes: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    changes.push(closes[i] - closes[i - 1]);
  }

  // Separate gains and losses
  const gains = changes.map(c => c > 0 ? c : 0);
  const losses = changes.map(c => c < 0 ? -c : 0);

  // First average gain/loss (simple average)
  let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
  let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;

  // First RSI value
  result.push(null); // No RSI for first data point
  for (let i = 0; i < period; i++) {
    result.push(null); // Not enough data yet
  }

  const rs = avgGain / (avgLoss || 1e-10); // Avoid division by zero
  const rsiValue = 100 - (100 / (1 + rs));
  result.push(rsiValue);

  // Subsequent RSI values using Wilder's smoothing
  for (let i = period; i < changes.length; i++) {
    avgGain = (avgGain * (period - 1) + gains[i]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i]) / period;

    const rs = avgGain / (avgLoss || 1e-10);
    const rsi = 100 - (100 / (1 + rs));
    result.push(rsi);
  }

  return result;
}

/**
 * MACD (Moving Average Convergence Divergence).
 * Returns MACD line, signal line, and histogram.
 */
export function macd(
  closes: number[],
  fast: number = 12,
  slow: number = 26,
  signal: number = 9
): { line: (number | null)[]; signal: (number | null)[]; histogram: (number | null)[] } {
  // Calculate fast and slow EMAs
  const fastEMA = ema(closes, fast);
  const slowEMA = ema(closes, slow);

  // MACD line = fastEMA - slowEMA
  const macdLine: (number | null)[] = fastEMA.map((fast, i) => {
    const slow = slowEMA[i];
    if (fast === null || slow === null) return null;
    return fast - slow;
  });

  // Signal line = EMA of MACD line
  const macdValues = macdLine.filter((v): v is number => v !== null);
  const signalEMA = ema(macdValues, signal);

  // Pad signal line with nulls to match length
  const nullCount = macdLine.findIndex(v => v !== null) + slow - 1;
  const signalLine: (number | null)[] = [
    ...new Array(nullCount).fill(null),
    ...signalEMA.slice(slow - 1)
  ];

  // Histogram = MACD line - Signal line
  const histogram: (number | null)[] = macdLine.map((macd, i) => {
    const sig = signalLine[i];
    if (macd === null || sig === null) return null;
    return macd - sig;
  });

  return {
    line: macdLine,
    signal: signalLine,
    histogram
  };
}

/**
 * Bollinger Bands - volatility indicator with upper/lower bands around SMA.
 */
export function bollingerBands(
  closes: number[],
  period: number = 20,
  stdDev: number = 2
): { upper: (number | null)[]; middle: (number | null)[]; lower: (number | null)[] } {
  const middle = sma(closes, period);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];

  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1 || middle[i] === null) {
      upper.push(null);
      lower.push(null);
    } else {
      // Calculate standard deviation for this window
      const window = closes.slice(i - period + 1, i + 1);
      const mean = middle[i]!;
      const variance = window.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / period;
      const std = Math.sqrt(variance);

      upper.push(mean + stdDev * std);
      lower.push(mean - stdDev * std);
    }
  }

  return { upper, middle, lower };
}
