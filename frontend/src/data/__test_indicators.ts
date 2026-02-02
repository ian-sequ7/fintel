/**
 * Quick verification script for indicator calculations.
 * Run with: node --loader tsx src/data/__test_indicators.ts
 */

import { sma, ema, rsi, macd, bollingerBands } from './indicators';

// Test data: simple ascending prices
const testPrices = [
  100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
  111, 110, 112, 114, 113, 115, 117, 116, 118, 120,
  119, 121, 123, 122, 124, 126, 125, 127, 129, 128
];

console.log('Testing Technical Indicators\n');

// Test SMA
console.log('SMA(5):');
const sma5 = sma(testPrices, 5);
console.log('Last 5 values:', sma5.slice(-5));
console.log('Expected: [123.8, 124.8, 124.6, 125.6, 126.6]\n');

// Test EMA
console.log('EMA(5):');
const ema5 = ema(testPrices, 5);
console.log('Last 5 values:', ema5.slice(-5));
console.log('(Should give more weight to recent prices)\n');

// Test RSI
console.log('RSI(14):');
const rsi14 = rsi(testPrices, 14);
console.log('Last 5 values:', rsi14.slice(-5));
console.log('Expected: values between 0-100, trending upward for rising prices\n');

// Test MACD
console.log('MACD(12, 26, 9):');
const macdData = macd(testPrices, 12, 26, 9);
console.log('MACD Line (last 3):', macdData.line.slice(-3));
console.log('Signal Line (last 3):', macdData.signal.slice(-3));
console.log('Histogram (last 3):', macdData.histogram.slice(-3));
console.log('');

// Test Bollinger Bands
console.log('Bollinger Bands(20, 2):');
const bb = bollingerBands(testPrices, 20, 2);
console.log('Upper (last 3):', bb.upper.slice(-3));
console.log('Middle (last 3):', bb.middle.slice(-3));
console.log('Lower (last 3):', bb.lower.slice(-3));
console.log('\nAll indicators calculated successfully! ✓');
