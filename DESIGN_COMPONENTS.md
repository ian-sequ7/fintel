# Financial Dashboard Component Library
## Reusable Patterns from Bloomberg & MarketWatch

---

## Component 1: Tabbed Data Grid

**Use Case:** Display different views of the same data (US/Europe/Asia markets, or Holdings/Performance/Risk)

**Key Features:**
- Semantic `<table>` with tablist for switching views
- Compact typography (13px, 1.4 line-height)
- Green/red for status only
- Responsive: tabs scroll horizontally on mobile

**Code:**

```jsx
import React, { useState } from 'react';

export function TabbedDataGrid({
  title,
  tabs,
  columns,
  data,
  selectedTab,
  onTabChange
}) {
  const currentTabData = data[selectedTab] || [];

  return (
    <section className="data-grid">
      <h2>{title}</h2>

      <div className="tab-bar" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={selectedTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => onTabChange(tab.id)}
            className={selectedTab === tab.id ? 'active' : ''}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`panel-${selectedTab}`}
        className="table-container"
      >
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={col.align ? `align-${col.align}` : ''}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {currentTabData.map((row, idx) => (
              <tr key={idx}>
                {columns.map((col) => {
                  const value = row[col.key];
                  const isChange = col.key.includes('change') ||
                                   col.key.includes('pct');
                  const isPositive =
                    typeof value === 'number' ? value >= 0 :
                    String(value).startsWith('+');

                  return (
                    <td
                      key={col.key}
                      className={`
                        ${col.align ? `align-${col.align}` : ''}
                        ${isChange ? (isPositive ? 'positive' : 'negative') : ''}
                      `}
                    >
                      {col.format ? col.format(value) : value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// Usage Example:
export function MarketsOverview() {
  const [selectedTab, setSelectedTab] = useState('us');

  const marketData = {
    us: [
      { name: 'Dow', price: 49504.07, change: 237.96, pct: 0.48 },
      { name: 'S&P 500', price: 6966.28, change: 44.82, pct: 0.65 },
      { name: 'Nasdaq', price: 23671.35, change: 191.33, pct: 0.81 },
    ],
    eu: [
      { name: 'DAX', price: 20945.5, change: -52.3, pct: -0.25 },
      { name: 'FTSE 100', price: 8234.7, change: 15.2, pct: 0.18 },
    ],
    asia: [
      { name: 'Nikkei', price: 40189.3, change: 385.2, pct: 0.96 },
      { name: 'Shanghai', price: 3298.5, change: -45.1, pct: -1.35 },
    ],
  };

  return (
    <TabbedDataGrid
      title="Market Overview"
      tabs={[
        { id: 'us', label: 'US' },
        { id: 'eu', label: 'Europe' },
        { id: 'asia', label: 'Asia' },
      ]}
      columns={[
        { key: 'name', label: 'Index', align: 'left' },
        { key: 'price', label: 'Price', align: 'right', format: (v) => v.toFixed(2) },
        { key: 'change', label: 'Change', align: 'right', format: (v) => (v >= 0 ? '+' : '') + v.toFixed(2) },
        { key: 'pct', label: '% Change', align: 'right', format: (v) => (v >= 0 ? '+' : '') + v.toFixed(2) + '%' },
      ]}
      data={marketData}
      selectedTab={selectedTab}
      onTabChange={setSelectedTab}
    />
  );
}
```

**CSS:**

```css
.data-grid {
  margin: 20px 0;
}

.data-grid h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
  color: #000;
}

.tab-bar {
  display: flex;
  border-bottom: 1px solid #e0e0e0;
  margin-bottom: 0;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

[role="tab"] {
  flex: 0 0 auto;
  padding: 12px 16px;
  border: none;
  background: none;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  white-space: nowrap;
}

[role="tab"]:hover {
  color: #000;
  background: #f9f9f9;
}

[role="tab"][aria-selected="true"] {
  color: #000;
  border-bottom-color: #000;
  font-weight: 600;
}

.table-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table thead {
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
}

.data-table th {
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: #333;
  border-right: 1px solid #e0e0e0;
}

.data-table th:last-child {
  border-right: none;
}

.data-table td {
  padding: 10px 12px;
  border-right: 1px solid #f0f0f0;
}

.data-table td:last-child {
  border-right: none;
}

.data-table tbody tr {
  border-bottom: 1px solid #f0f0f0;
}

.data-table tbody tr:hover {
  background: #fafafa;
}

.data-table td.align-right {
  text-align: right;
  font-family: 'Monaco', 'Courier New', monospace;
}

.data-table td.positive {
  color: #00a651;
  font-weight: 600;
}

.data-table td.negative {
  color: #d2201a;
  font-weight: 600;
}
```

---

## Component 2: Dense Information Cards

**Use Case:** Display multiple metric cards with minimal whitespace (Holdings count, Total value, YTD return, etc.)

**Key Features:**
- Minimal padding (8px vertical, 12px horizontal)
- Hierarchy through font-weight, not size
- Supports large numbers and small labels
- Responsive grid

**Code:**

```jsx
export function MetricCard({ label, value, change, format = 'number' }) {
  const isPositive = change >= 0;

  let formattedValue = value;
  let formattedChange = change;

  if (format === 'percent') {
    formattedValue = (value * 100).toFixed(2) + '%';
    formattedChange = (change * 100).toFixed(2) + '%';
  } else if (format === 'currency') {
    formattedValue = '$' + value.toLocaleString('en-US', {
      maximumFractionDigits: 2
    });
    formattedChange = (change >= 0 ? '+' : '') + '$' +
      Math.abs(change).toLocaleString('en-US', {
        maximumFractionDigits: 2
      });
  }

  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{formattedValue}</div>
      {change !== undefined && (
        <div className={`metric-change ${isPositive ? 'positive' : 'negative'}`}>
          {isPositive ? '↑' : '↓'} {formattedChange}
        </div>
      )}
    </div>
  );
}

export function MetricsGrid() {
  return (
    <div className="metrics-container">
      <MetricCard
        label="Total Value"
        value={1250000}
        change={15000}
        format="currency"
      />
      <MetricCard
        label="YTD Return"
        value={0.042}
        change={0.005}
        format="percent"
      />
      <MetricCard
        label="Holdings"
        value={23}
      />
      <MetricCard
        label="Cash Available"
        value={45000}
        change={-5000}
        format="currency"
      />
    </div>
  );
}
```

**CSS:**

```css
.metrics-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 16px 0;
}

.metric-card {
  border: 1px solid #e0e0e0;
  padding: 12px;
  border-radius: 4px;
  background: #fff;
}

.metric-label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.metric-value {
  font-size: 20px;
  font-weight: 600;
  color: #000;
  margin-bottom: 4px;
  font-family: 'Monaco', 'Courier New', monospace;
  line-height: 1.2;
}

.metric-change {
  font-size: 13px;
  font-weight: 500;
}

.metric-change.positive {
  color: #00a651;
}

.metric-change.negative {
  color: #d2201a;
}

/* Responsive */
@media (max-width: 768px) {
  .metrics-container {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .metrics-container {
    grid-template-columns: 1fr;
  }

  .metric-value {
    font-size: 18px;
  }
}
```

---

## Component 3: Responsive Navigation

**Use Case:** Primary navigation that works from mobile to desktop

**Key Features:**
- Hamburger menu on mobile
- Horizontal items on desktop
- Sticky header
- Account menu dropdown

**Code:**

```jsx
import React, { useState } from 'react';

export function MainNavigation({ items, user }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="main-nav">
      <div className="nav-left">
        <button
          className="nav-toggle"
          onClick={() => setIsOpen(!isOpen)}
          aria-label="Toggle menu"
          aria-expanded={isOpen}
        >
          <span className="hamburger"></span>
        </button>

        <a href="/" className="nav-logo">
          FINTEL
        </a>
      </div>

      <div className={`nav-items ${isOpen ? 'open' : ''}`}>
        {items.map((item) => (
          <a
            key={item.id}
            href={item.href}
            className={item.active ? 'active' : ''}
          >
            {item.label}
          </a>
        ))}
      </div>

      <div className="nav-right">
        <button className="nav-search" aria-label="Search">
          🔍
        </button>

        <div className="nav-account">
          <button className="account-button">
            {user.initials}
          </button>
          <div className="account-menu">
            <a href="/settings">Settings</a>
            <a href="/help">Help</a>
            <a href="/logout">Logout</a>
          </div>
        </div>
      </div>
    </nav>
  );
}

// Usage:
export function App() {
  return (
    <MainNavigation
      items={[
        { id: 1, label: 'Portfolio', href: '/portfolio', active: true },
        { id: 2, label: 'Research', href: '/research' },
        { id: 3, label: 'Trading', href: '/trading' },
        { id: 4, label: 'Account', href: '/account' },
      ]}
      user={{ initials: 'IS' }}
    />
  );
}
```

**CSS:**

```css
.main-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  position: sticky;
  top: 0;
  z-index: 1000;
  gap: 16px;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-toggle {
  display: none;
  width: 40px;
  height: 40px;
  padding: 8px;
  background: none;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
}

.hamburger {
  display: block;
  width: 24px;
  height: 16px;
  position: relative;
}

.hamburger::before,
.hamburger::after,
.hamburger {
  content: '';
  position: absolute;
  width: 100%;
  height: 2px;
  background: #000;
  left: 0;
}

.hamburger::before {
  top: 0;
}

.hamburger {
  top: 7px;
}

.hamburger::after {
  top: 14px;
}

.nav-logo {
  font-size: 18px;
  font-weight: 700;
  color: #000;
  text-decoration: none;
  letter-spacing: 1px;
}

.nav-items {
  display: flex;
  gap: 0;
  flex: 1;
}

.nav-items a {
  padding: 8px 16px;
  font-size: 14px;
  color: #666;
  text-decoration: none;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  white-space: nowrap;
}

.nav-items a:hover {
  color: #000;
  background: #f5f5f5;
}

.nav-items a.active {
  color: #000;
  border-bottom-color: #000;
  font-weight: 600;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-search {
  width: 40px;
  height: 40px;
  border: none;
  background: none;
  font-size: 18px;
  cursor: pointer;
}

.nav-account {
  position: relative;
}

.account-button {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #f0f0f0;
  border: 1px solid #e0e0e0;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.account-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  min-width: 150px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
}

.nav-account:hover .account-menu {
  opacity: 1;
  pointer-events: auto;
}

.account-menu a {
  display: block;
  padding: 8px 16px;
  text-decoration: none;
  color: #333;
  font-size: 13px;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.2s;
}

.account-menu a:last-child {
  border-bottom: none;
}

.account-menu a:hover {
  background: #f5f5f5;
}

/* Tablet & Mobile */
@media (max-width: 768px) {
  .nav-toggle {
    display: block;
  }

  .nav-items {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    flex-direction: column;
    background: #fff;
    border-bottom: 1px solid #e0e0e0;
    opacity: 0;
    max-height: 0;
    overflow: hidden;
    transition: all 0.3s;
  }

  .nav-items.open {
    opacity: 1;
    max-height: 500px;
  }

  .nav-items a {
    border-bottom: none;
    border-left: 2px solid transparent;
    padding-left: 24px;
  }

  .nav-items a.active {
    border-bottom: none;
    border-left-color: #000;
  }
}

@media (max-width: 480px) {
  .main-nav {
    padding: 0 12px;
  }

  .nav-logo {
    font-size: 16px;
  }

  .nav-items a {
    padding: 12px 16px;
    font-size: 16px;
  }
}
```

---

## Component 4: Data Table with Sorting & Filtering

**Use Case:** Full portfolio holdings with sort, filter, and density options

**Code:**

```jsx
import React, { useState, useMemo } from 'react';

export function HoldingsTable({ holdings }) {
  const [sortBy, setSortBy] = useState('value');
  const [sortDir, setSortDir] = useState('desc');
  const [filterType, setFilterType] = useState('all');

  const sorted = useMemo(() => {
    let data = [...holdings];

    // Filter
    if (filterType !== 'all') {
      data = data.filter((h) => h.type === filterType);
    }

    // Sort
    data.sort((a, b) => {
      const aVal = a[sortBy];
      const bVal = b[sortBy];
      const mult = sortDir === 'asc' ? 1 : -1;
      return (aVal > bVal ? 1 : -1) * mult;
    });

    return data;
  }, [holdings, sortBy, sortDir, filterType]);

  const handleSort = (key) => {
    if (sortBy === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(key);
      setSortDir('desc');
    }
  };

  return (
    <div className="holdings-section">
      <div className="holdings-controls">
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="filter-select"
        >
          <option value="all">All Assets</option>
          <option value="stock">Stocks</option>
          <option value="etf">ETFs</option>
          <option value="fund">Mutual Funds</option>
          <option value="crypto">Crypto</option>
        </select>

        <span className="results-count">
          {sorted.length} holding{sorted.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="table-container">
        <table className="holdings-table">
          <thead>
            <tr>
              <th
                className="sortable"
                onClick={() => handleSort('symbol')}
              >
                Symbol {sortBy === 'symbol' && (sortDir === 'asc' ? '↑' : '↓')}
              </th>
              <th
                className="sortable align-right"
                onClick={() => handleSort('shares')}
              >
                Shares {sortBy === 'shares' && (sortDir === 'asc' ? '↑' : '↓')}
              </th>
              <th
                className="sortable align-right"
                onClick={() => handleSort('price')}
              >
                Price {sortBy === 'price' && (sortDir === 'asc' ? '↑' : '↓')}
              </th>
              <th
                className="sortable align-right"
                onClick={() => handleSort('value')}
              >
                Value {sortBy === 'value' && (sortDir === 'asc' ? '↑' : '↓')}
              </th>
              <th
                className="sortable align-right"
                onClick={() => handleSort('gain')}
              >
                Gain {sortBy === 'gain' && (sortDir === 'asc' ? '↑' : '↓')}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((holding) => {
              const gainPct = (holding.gain / holding.cost) * 100;
              const isPositive = holding.gain >= 0;

              return (
                <tr key={holding.id}>
                  <td className="symbol">{holding.symbol}</td>
                  <td className="align-right number">
                    {holding.shares.toLocaleString('en-US', {
                      maximumFractionDigits: 4,
                    })}
                  </td>
                  <td className="align-right number">
                    ${holding.price.toFixed(2)}
                  </td>
                  <td className="align-right number bold">
                    ${holding.value.toLocaleString('en-US', {
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td
                    className={`align-right number ${isPositive ? 'positive' : 'negative'}`}
                  >
                    {isPositive ? '+' : ''}$
                    {Math.abs(holding.gain).toLocaleString('en-US', {
                      maximumFractionDigits: 2,
                    })}{' '}
                    ({isPositive ? '+' : ''}{gainPct.toFixed(2)}%)
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="table-footer">
        <div className="footer-stat">
          Total Value: $
          {sorted
            .reduce((sum, h) => sum + h.value, 0)
            .toLocaleString('en-US', { maximumFractionDigits: 2 })}
        </div>
        <div className={`footer-stat ${sorted.reduce((sum, h) => sum + h.gain, 0) >= 0 ? 'positive' : 'negative'}`}>
          Total Gain: $
          {sorted.reduce((sum, h) => sum + h.gain, 0).toLocaleString('en-US', {
            maximumFractionDigits: 2,
          })}
        </div>
      </div>
    </div>
  );
}
```

**CSS:**

```css
.holdings-section {
  margin: 24px 0;
}

.holdings-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 0 12px;
}

.filter-select {
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid #e0e0e0;
  border-radius: 3px;
  background: #fff;
  cursor: pointer;
}

.results-count {
  font-size: 12px;
  color: #666;
}

.table-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.holdings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.holdings-table thead {
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
}

.holdings-table th {
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: #333;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.holdings-table th.sortable:hover {
  background: #ececec;
}

.holdings-table th.align-right {
  text-align: right;
}

.holdings-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.holdings-table tbody tr:hover {
  background: #fafafa;
}

.holdings-table td.align-right {
  text-align: right;
}

.holdings-table td.number {
  font-family: 'Monaco', 'Courier New', monospace;
  font-weight: 400;
}

.holdings-table td.bold {
  font-weight: 600;
}

.holdings-table td.positive {
  color: #00a651;
}

.holdings-table td.negative {
  color: #d2201a;
}

.table-footer {
  display: flex;
  gap: 24px;
  padding: 12px;
  background: #f9f9f9;
  border-top: 1px solid #e0e0e0;
  font-size: 13px;
  font-weight: 600;
}

.footer-stat {
  color: #333;
}

.footer-stat.positive {
  color: #00a651;
}

.footer-stat.negative {
  color: #d2201a;
}

/* Responsive */
@media (max-width: 768px) {
  .holdings-controls {
    flex-wrap: wrap;
  }

  .table-footer {
    flex-direction: column;
    gap: 8px;
  }
}
```

---

## Component 5: Responsive Grid Layout

**Use Case:** Dashboard layout that works from mobile to desktop

**Code:**

```jsx
export function DashboardLayout({ children }) {
  return (
    <div className="dashboard">
      <div className="dashboard-grid">
        {children}
      </div>
    </div>
  );
}

export function DashboardCard({ title, children, span = 1 }) {
  return (
    <section className={`dashboard-card card-span-${span}`}>
      {title && <h3>{title}</h3>}
      {children}
    </section>
  );
}

// Usage:
export function Portfolio() {
  return (
    <DashboardLayout>
      <DashboardCard title="Portfolio Summary" span={2}>
        <MetricsGrid />
      </DashboardCard>

      <DashboardCard title="Asset Allocation">
        {/* Chart here */}
      </DashboardCard>

      <DashboardCard title="Holdings" span={2}>
        <HoldingsTable holdings={holdings} />
      </DashboardCard>

      <DashboardCard title="Performance">
        {/* Chart here */}
      </DashboardCard>

      <DashboardCard title="Recent Transactions" span={2}>
        {/* Table here */}
      </DashboardCard>
    </DashboardLayout>
  );
}
```

**CSS:**

```css
.dashboard {
  padding: 16px;
  background: #fff;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-card {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 16px;
  background: #fff;
}

.dashboard-card h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #000;
}

.card-span-1 {
  grid-column: span 1;
}

.card-span-2 {
  grid-column: span 2;
}

/* Tablet */
@media (max-width: 1024px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .card-span-1 {
    grid-column: span 1;
  }

  .card-span-2 {
    grid-column: span 1;
  }
}

/* Mobile */
@media (max-width: 768px) {
  .dashboard {
    padding: 12px;
  }

  .dashboard-grid {
    gap: 12px;
  }

  .dashboard-card {
    padding: 12px;
  }

  .dashboard-card h3 {
    margin-bottom: 12px;
    font-size: 14px;
  }
}
```

---

## Quick Reference: Color Palette

```css
/* Financial Status Colors */
:root {
  --color-positive: #00a651;  /* Green: up, gain, profit */
  --color-negative: #d2201a;  /* Red: down, loss, negative */
  --color-neutral: #666666;   /* Gray: inactive, secondary */

  /* Semantic */
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f5f5f5;
  --color-bg-hover: #fafafa;

  --color-text-primary: #000000;
  --color-text-secondary: #666666;
  --color-text-muted: #999999;

  --color-border: #e0e0e0;
  --color-border-light: #f0f0f0;

  /* Interactive */
  --color-link: #0073e6;
  --color-focus: #0056b3;
}

/* Dark Mode */
@media (prefers-color-scheme: dark) {
  :root {
    --color-bg-primary: #1a1a1a;
    --color-bg-secondary: #262626;
    --color-bg-hover: #333333;

    --color-text-primary: #ffffff;
    --color-text-secondary: #aaaaaa;
    --color-text-muted: #777777;

    --color-border: #333333;
    --color-border-light: #2a2a2a;

    --color-positive: #00d084;  /* Brighter green */
    --color-negative: #ff6b6b;  /* Brighter red */

    --color-link: #4da6ff;
  }
}
```

---

## Summary

These components implement the patterns observed in Bloomberg and MarketWatch:

1. **TabbedDataGrid** - Tab-based data filtering (US/Europe/Asia)
2. **MetricCard** - Compact information display with minimal whitespace
3. **MainNavigation** - Responsive top nav that collapses to hamburger
4. **HoldingsTable** - Full-featured table with sorting, filtering, and color coding
5. **DashboardLayout** - Responsive grid that adapts to screen size

All components use:
- 13px font size with 1.4 line-height
- Monochromatic palette with green/red accents only
- 8-12px padding for density
- Semantic HTML for accessibility
- System sans-serif fonts for performance
- Responsive breakpoints at 768px and 1024px
