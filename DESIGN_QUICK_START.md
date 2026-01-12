# Financial Dashboard Design - Quick Start Guide
## Immediate Implementation Checklist

---

## The 80/20 Rule: Do These 5 Things First

### 1. Color System (15 minutes)

Copy into your CSS:

```css
:root {
  /* Status Colors - ONLY colors you'll ever use */
  --positive: #00a651;   /* Green for gains/up */
  --negative: #d2201a;   /* Red for losses/down */

  /* Everything else is neutral */
  --text-primary: #000;
  --text-secondary: #666;
  --bg-primary: #fff;
  --bg-secondary: #f5f5f5;
  --border: #e0e0e0;
}
```

**Rule:** Every color must mean something. No colors for decoration.

---

### 2. Typography (15 minutes)

Set this globally:

```css
* {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
}

body {
  font-size: 13px;
  line-height: 1.4;
  color: var(--text-primary);
}

/* All headings */
h1, h2, h3, h4, h5, h6 {
  font-weight: 600;
  margin: 0;
}

h1 { font-size: 24px; }
h2 { font-size: 16px; }
h3 { font-size: 14px; }

/* Data numbers - use monospace */
.number {
  font-family: 'Monaco', 'Courier New', monospace;
}
```

**Rule:** Everything is 13px or 14px. Hierarchy comes from weight and spacing, not size.

---

### 3. Table Defaults (20 minutes)

```css
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.4;
}

thead {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}

th {
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: var(--text-primary);
}

td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
}

tbody tr:hover {
  background: #fafafa;
}

/* Right-align numbers */
td.number, th.number {
  text-align: right;
}

/* Status colors */
td.positive { color: var(--positive); font-weight: 600; }
td.negative { color: var(--negative); font-weight: 600; }
```

**Rule:** No hover effects on headers. Text-align=right for all numeric data.

---

### 4. Navigation (20 minutes)

```css
nav {
  display: flex;
  align-items: center;
  padding: 0 16px;
  height: 56px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-primary);
  position: sticky;
  top: 0;
  z-index: 1000;
  gap: 16px;
}

nav a {
  padding: 8px 16px;
  color: var(--text-secondary);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  font-size: 14px;
  white-space: nowrap;
}

nav a:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

nav a.active {
  color: var(--text-primary);
  border-bottom-color: var(--text-primary);
  font-weight: 600;
}

/* Mobile: hamburger menu */
@media (max-width: 768px) {
  nav {
    justify-content: space-between;
  }

  .nav-menu { display: none; }
  .nav-menu.open { display: flex; flex-direction: column; }
}
```

**Rule:** One underline for active state. No hover underlines.

---

### 5. Card/Section Spacing (10 minutes)

```css
section {
  margin: 20px 0;
}

.card {
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 16px;
  background: var(--bg-primary);
}

.card h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
}

/* Gaps between elements */
.gap-sm { margin: 8px 0; }
.gap-md { margin: 12px 0; }
.gap-lg { margin: 16px 0; }
```

**Rule:** 16px or 20px between sections. Never 24px, 32px, or 40px.

---

## Copy-Paste Template

**Minimal dashboard HTML:**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fintel - Portfolio</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
      --positive: #00a651;
      --negative: #d2201a;
      --text-primary: #000;
      --text-secondary: #666;
      --bg-primary: #fff;
      --bg-secondary: #f5f5f5;
      --border: #e0e0e0;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 13px;
      line-height: 1.4;
      color: var(--text-primary);
    }

    nav {
      display: flex;
      align-items: center;
      padding: 0 16px;
      height: 56px;
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 1000;
    }

    nav a {
      padding: 8px 16px;
      color: var(--text-secondary);
      text-decoration: none;
      border-bottom: 2px solid transparent;
      font-size: 14px;
      white-space: nowrap;
    }

    nav a.active {
      color: var(--text-primary);
      border-bottom-color: var(--text-primary);
      font-weight: 600;
    }

    main {
      padding: 16px;
      max-width: 1400px;
      margin: 0 auto;
    }

    h2 {
      font-size: 16px;
      font-weight: 600;
      margin: 20px 0 16px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
    }

    thead {
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
    }

    th {
      padding: 10px 12px;
      text-align: left;
      font-weight: 600;
      font-size: 12px;
      color: var(--text-primary);
    }

    td {
      padding: 10px 12px;
      border-bottom: 1px solid #f0f0f0;
    }

    td.number {
      text-align: right;
      font-family: 'Monaco', 'Courier New', monospace;
    }

    td.positive {
      color: var(--positive);
      font-weight: 600;
    }

    td.negative {
      color: var(--negative);
      font-weight: 600;
    }

    tbody tr:hover {
      background: #fafafa;
    }

    /* Tabs */
    [role="tablist"] {
      display: flex;
      border-bottom: 1px solid var(--border);
      gap: 0;
      margin: 16px 0;
    }

    [role="tab"] {
      padding: 12px 16px;
      border: none;
      background: none;
      cursor: pointer;
      color: var(--text-secondary);
      font-size: 14px;
      border-bottom: 2px solid transparent;
      white-space: nowrap;
    }

    [role="tab"][aria-selected="true"] {
      color: var(--text-primary);
      border-bottom-color: var(--text-primary);
      font-weight: 600;
    }
  </style>
</head>
<body>
  <nav>
    <a href="/" style="font-weight: 700; font-size: 18px;">FINTEL</a>
    <a href="/portfolio" class="active">Portfolio</a>
    <a href="/research">Research</a>
    <a href="/trading">Trading</a>
  </nav>

  <main>
    <h2>Markets</h2>

    <div role="tablist">
      <button role="tab" aria-selected="true">US</button>
      <button role="tab" aria-selected="false">Europe</button>
      <button role="tab" aria-selected="false">Asia</button>
    </div>

    <table>
      <thead>
        <tr>
          <th>Index</th>
          <th class="number">Price</th>
          <th class="number">Change</th>
          <th class="number">% Change</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>S&P 500</td>
          <td class="number">6,966.28</td>
          <td class="number positive">+44.82</td>
          <td class="number positive">+0.65%</td>
        </tr>
        <tr>
          <td>Nasdaq</td>
          <td class="number">23,671.35</td>
          <td class="number positive">+191.33</td>
          <td class="number positive">+0.81%</td>
        </tr>
        <tr>
          <td>Dow</td>
          <td class="number">49,504.07</td>
          <td class="number positive">+237.96</td>
          <td class="number positive">+0.48%</td>
        </tr>
      </tbody>
    </table>

    <h2>Portfolio</h2>

    <table>
      <thead>
        <tr>
          <th>Holding</th>
          <th class="number">Shares</th>
          <th class="number">Price</th>
          <th class="number">Value</th>
          <th class="number">Gain</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Apple (AAPL)</td>
          <td class="number">100.00</td>
          <td class="number">$235.50</td>
          <td class="number">$23,550.00</td>
          <td class="number positive">+$2,450.00 (+11.6%)</td>
        </tr>
        <tr>
          <td>Tesla (TSLA)</td>
          <td class="number">50.00</td>
          <td class="number">$420.30</td>
          <td class="number">$21,015.00</td>
          <td class="number negative">-$1,200.00 (-5.4%)</td>
        </tr>
      </tbody>
    </table>
  </main>
</body>
</html>
```

**That's it.** This is the baseline. Everything else is components built on top.

---

## Common Patterns: Quick Solutions

### Problem: I have 15+ tabs, where do they go?

**Solution: Group by semantic meaning**

```html
<nav>
  <a href="#portfolio">Portfolio</a>
  <a href="#research">Research</a>
  <a href="#account">Account</a>
</nav>

<!-- Within Portfolio page: -->
<div role="tablist">
  <button role="tab">Holdings</button>
  <button role="tab">Performance</button>
  <button role="tab">Risk</button>
  <button role="tab">Allocation</button>
</div>
```

Max 7-8 tabs per level. More than that means you need another nav level.

---

### Problem: How do I make text bold for emphasis?

**Don't.** Use color (green/red) or weight (600 vs 400).

```html
<!-- YES -->
<td class="positive">+$2,450.00</td>

<!-- NO -->
<td><strong>+$2,450.00</strong></td>

<!-- CSS -->
.positive {
  color: var(--positive);
  font-weight: 600;
}
```

---

### Problem: Where do I put filters/search?

**Above the data, not beside it.**

```html
<div style="display: flex; gap: 16px; margin-bottom: 16px; align-items: center;">
  <select>
    <option>All Assets</option>
    <option>Stocks</option>
    <option>ETFs</option>
  </select>

  <input type="search" placeholder="Find holding...">

  <span style="font-size: 12px; color: #666;">
    23 holdings
  </span>
</div>

<table>
  <!-- Table data -->
</table>
```

---

### Problem: How do I show positive/negative without color?

**Use a combination: color + icon + direction indicator**

```html
<td>
  <span class="positive">
    ↑ +$2,450 (11.6%)
  </span>
</td>

<!-- CSS -->
.positive { color: var(--positive); font-weight: 600; }
.negative { color: var(--negative); font-weight: 600; }
```

---

### Problem: Should I use dark mode?

**No, not yet.** Serve light mode. If you must:

```css
@media (prefers-color-scheme: dark) {
  :root {
    --text-primary: #fff;
    --text-secondary: #aaa;
    --bg-primary: #1a1a1a;
    --bg-secondary: #262626;
    --border: #333;

    /* Brighter status colors in dark */
    --positive: #00d084;
    --negative: #ff6b6b;
  }
}
```

Let the system setting decide. Don't force a toggle.

---

### Problem: How do I handle mobile?

**Single column. Tabs scroll horizontally. Nav collapses to hamburger.**

```css
@media (max-width: 768px) {
  /* Tables scroll horizontally */
  table {
    min-width: 600px;
  }

  /* Tabs scroll horizontally */
  [role="tablist"] {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  /* Nav items hide, show hamburger */
  .nav-items { display: none; }
  .nav-toggle { display: block; }
}
```

---

## Performance Checklist

- [ ] No custom fonts (use system -apple-system, BlinkMacSystemFont, etc.)
- [ ] Tables use native `<table>` (not div-based)
- [ ] No SVG icons in tables (use Unicode symbols or emoji: ↑ ↓)
- [ ] No animations on page load
- [ ] No shadows (use borders instead)
- [ ] CSS is under 20KB (no Tailwind or Bootstrap)
- [ ] No JavaScript for tabs (use CSS [aria-selected] selector)

---

## Accessibility Checklist

- [ ] Color contrast ratio 4.5:1 minimum
- [ ] All interactive elements are 40x40px minimum (buttons, links)
- [ ] Tables have `<thead>` and `<tbody>`
- [ ] Tabs use `role="tablist"` and `role="tab"`
- [ ] Links are underlined (or clearly styled)
- [ ] Form inputs have labels
- [ ] Images have alt text
- [ ] No placeholder-only labels

---

## Before You Ship

1. **Test in Safari, Chrome, Firefox** (just scroll, click tabs, resize)
2. **Test on iPhone 12 viewport** (375px width)
3. **Check with no custom fonts** (turn off CSS fonts in DevTools)
4. **Verify color contrast** (use WebAIM contrast checker)
5. **Read page aloud** (use macOS reader or screen reader)
6. **Resize to tablet** (does layout break nicely at 768px?)

---

## The One Rule

**Everything you see on the page should serve the data. Nothing else.**

No:
- Decorative colors
- Rounded corners (unless accessible)
- Large whitespace
- Bright gradients
- Custom fonts
- Fancy animations

Yes:
- Clear hierarchy
- Semantic structure
- Fast load times
- Information density
- Accessibility
- Consistency

---

## Next: Reading the Full Analysis

See these files for deep dives:

- `DESIGN_PATTERNS_ANALYSIS.md` - Full research with Bloomberg/MarketWatch analysis
- `DESIGN_COMPONENTS.md` - Complete React component code with examples

This guide is the Cliff's Notes version. Refer back to it constantly.
