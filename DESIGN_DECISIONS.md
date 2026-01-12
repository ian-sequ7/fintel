# Design Decision Framework
## When to Choose Between Patterns

---

## Navigation Structure Decision Tree

### Question 1: How many top-level sections do you have?

```
1-4 sections
    └─ Top horizontal nav only
       (Example: Fintel with Portfolio, Research, Trading)

5-6 sections
    └─ Top horizontal nav only (full width at 1200px+)
       └─ Tabs scroll horizontally on mobile

7+ sections
    └─ TWO OPTIONS:
       A) Hamburger menu (simplify to 4 main + "More")
       B) Add left sidebar for desktop
          └─ Hamburger menu on mobile (sidebar becomes drawer)
```

**MarketWatch chose:** Option 1 (4 primary sections only)
**Why:** Users rarely need all sections visible. Better to have clear primaries.

---

## Tabs vs. Navigation Decision Matrix

### Use Tabs (horizontal selector) when:
- [ ] Data is related (US/Europe/Asia markets)
- [ ] One tab shows at a time
- [ ] Switching tabs doesn't go to new URL
- [ ] 3-8 options maximum
- [ ] User frequently switches between them
- Example: Market data tables (US/Europe/Asia)

### Use Navigation (links) when:
- [ ] Sections are unrelated (Portfolio vs. Research)
- [ ] Each option is a different page/URL
- [ ] More than 8 options
- [ ] User goes there once, stays for a while
- Example: Main menu (Portfolio, Research, Trading)

**Hybrid Pattern (Bloomberg/MarketWatch):**
```
Top Nav: [Portfolio] [Research] [Trading] [Account]
         ↓ (go to different page)

Inside Portfolio Page:
    Tab Set: [Holdings] [Performance] [Risk] [Allocation]
             ↓ (same page, different data)
```

---

## Data Density Decision Matrix

### How many rows of data fit in your viewport?

**Current viewport height:** 1080px
**Allocated for header/nav:** ~100px
**Allocated for footer/margin:** ~50px
**Available for data:** ~930px

**At 13px font with 1.4 line-height:**
- Row height = 35px (10px padding + 13px font + 12px gap)
- Rows per viewport = 930 / 35 = **26 rows visible**

| Font Size | Line-Height | Row Height | Rows/Viewport |
|-----------|-------------|-----------|---------------|
| 12px | 1.3 | 32px | 29 |
| 13px | 1.4 | 35px | 26 |
| 14px | 1.5 | 38px | 24 |
| 16px | 1.6 | 43px | 21 |

**Choose 13px if:**
- [ ] You have 50+ rows of data (stocks, holdings, transactions)
- [ ] Users scan frequently
- [ ] Mobile users have small screens

**Choose 14px if:**
- [ ] You have 10-20 rows of data
- [ ] Users are older (50+)
- [ ] Readability > density

**Choose 16px if:**
- [ ] You have <10 rows of data
- [ ] It's a mobile-first app
- [ ] Accessibility is paramount

**MarketWatch chose:** 13px (heavy density, lots of data)

---

## Color Strategy: Which Scheme?

### Scenario A: Status-Focused (Bloomberg/MarketWatch)

**When to use:**
- Data is inherently positive/negative (gains/losses, up/down)
- User needs to assess sentiment quickly
- Color is the primary indicator

**Color palette:**
```
Positive (up):    #00a651 (green)
Negative (down):  #d2201a (red)
Neutral:          #000, #666, #fff, #f5f5f5 (monochromatic)
```

**Use case example:**
```
Stock     Price    Change    % Change
AAPL      235.50   +5.30     +2.3%    ← Both change cells are GREEN
TSLA      420.30   -8.90     -2.1%    ← Both change cells are RED
```

---

### Scenario B: Category-Focused (Uncommon in finance)

**When to use:**
- Different colors for different asset classes (stocks=blue, ETFs=purple)
- You need to distinguish types at a glance

**WARNING:** Financial users are trained that green=good, red=bad. Using other colors for categories confuses them.

**RECOMMENDED:** Don't use this unless necessary. Stick with Scenario A.

---

### Scenario C: Hybrid (High-Performance Dashboards)

**When to use:**
- Large matrices (50+ rows x 10+ columns)
- Users scan data quickly
- You need visual hierarchy without color

**Palette:**
```
Positive: Green text + light green background
Negative: Red text + light red background
Neutral: Black text, no background

Light green background: #e8f5f3 (for +values)
Light red background:   #fde8e6 (for -values)
```

**Use case example:**
```
AAPL    235.50   [+5.30]     [+2.3%]    ← Light green background
TSLA    420.30   [-8.90]     [-2.1%]    ← Light red background
```

Improves scannability for large datasets.

---

## Layout Decision: Sidebar vs. Top Nav

### Use Top Nav Only when:
- [ ] 4-6 primary sections
- [ ] All are equally important
- [ ] Mobile is important
- [ ] Content is the star, not navigation
- **Example:** MarketWatch, Bloomberg

### Use Sidebar when:
- [ ] 8+ primary sections
- [ ] Clear hierarchy (some sections more important)
- [ ] Deep nesting needed
- [ ] Desktop-first product
- **Example:** Administrative dashboards, design tools

### Use Hybrid when:
- [ ] 6-8 primary sections
- [ ] Desktop: sidebar + main nav
- [ ] Mobile: hamburger replaces sidebar
- **Example:** Gmail, Slack, most SaaS apps

**For Fintel:** Choose TOP NAV ONLY
- Portfolio, Research, Trading, Account = 4 items
- Clean, mobile-friendly, content-focused
- Tabs inside Portfolio page handle subsections

---

## Mobile Breakpoint Strategy

### Three-tier responsive design:

```
Desktop (1200px+)
    └─ Full width
    └─ Two-column layouts
    └─ Sidebar visible
    └─ All nav items visible

Tablet (768px-1199px)
    └─ Adjusted column widths
    └─ Single column for small elements
    └─ Nav items visible or hamburger
    └─ Tables scroll horizontally

Mobile (375px-767px)
    └─ Single column only
    └─ Hamburger menu mandatory
    └─ Tables scroll horizontally
    └─ Tabs scroll horizontally
    └─ Max width 100%, padding 12px
```

**CSS:**
```css
/* Desktop first (default) */
.layout { display: grid; grid-template-columns: 250px 1fr; }

/* Tablet */
@media (max-width: 1024px) {
  .layout { grid-template-columns: 200px 1fr; }
}

/* Mobile */
@media (max-width: 768px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { display: none; }
}
```

---

## Typography Scale Decision

### Option 1: Minimal (Bloomberg/MarketWatch approach)

```
Body text:      13px
Small text:     12px (labels, captions)
Large text:     14px (section titles, form labels)
Heading 2:      16px (page sections)
Heading 1:      24px (page title)
```

**Best for:** Data-heavy applications, financial dashboards
**Pros:** Consistent, predictable, dense
**Cons:** Not great for accessibility without proper contrast

---

### Option 2: Generous (Modern SaaS approach)

```
Body text:      16px
Small text:     14px (labels, captions)
Large text:     18px (section titles)
Heading 2:      20px (page sections)
Heading 1:      32px (page title)
```

**Best for:** Content-focused apps, user-facing platforms
**Pros:** More accessible, modern feel
**Cons:** Less data density, requires larger screens

---

### Option 3: Hybrid (Recommended for Fintel)

```
Heading 1:      24px (app title)
Heading 2:      16px (section headers)
Heading 3:      14px (subsection headers)
Body text:      14px (default)
Data numbers:   13px (monospace, right-aligned)
Labels:         12px (uppercase, secondary color)
Captions:       11px (muted color, line-height 1.3)
```

**Why:** Readable but still dense where data lives

---

## State Indicator Decision: Icons vs. Color vs. Text

### Option 1: Color Only (Bloomberg)

```html
<td class="positive">+237.96</td>  ← User relies on color
```

**Pros:** Minimal visual noise, familiar to financial users
**Cons:** Not accessible if user is colorblind

---

### Option 2: Icon + Color (MarketWatch)

```html
<td class="positive">
  ↑ +237.96
</td>
```

**Pros:** Color + icon + text direction is redundant (good UX)
**Cons:** Takes more horizontal space

---

### Option 3: Color + Text Label

```html
<td class="positive">
  <span class="badge">Up</span> +237.96
</td>
```

**Pros:** Super clear for colorblind users
**Cons:** Excessive for financial data (users expect color to mean sentiment)

---

### **RECOMMENDATION FOR FINTEL:**
Use **Option 2: Icon + Color**

```html
<td class="number positive">
  ↑ +237.96 (+0.48%)
</td>

<td class="number negative">
  ↓ -237.96 (-0.48%)
</td>
```

CSS:
```css
.positive { color: #00a651; }
.negative { color: #d2201a; }
```

This is:
- Accessible (color + direction icon + text)
- Familiar to financial users
- Minimal visual weight

---

## Card vs. Table Decision: When to Use Each

### Use Tables when:
- [ ] Data has 3+ columns
- [ ] User needs to compare rows
- [ ] Data is structured and tabular
- [ ] You have lots of rows (10+)
- **Example:** Holdings, transactions, market data

### Use Cards when:
- [ ] Data is sparse (1-2 fields per item)
- [ ] Visual hierarchy matters
- [ ] You have few items (3-6)
- [ ] Items are not directly comparable
- **Example:** Portfolio summary, featured holdings

### Avoid Cards for:
- [ ] Dense data (50+ rows)
- [ ] Numeric comparisons
- [ ] Financial tables

---

## Sorting & Filtering Decision

### Sorting: Click column header or dedicated controls?

**Click header (MarketWatch):**
```html
<th onclick="sort('price')">
  Price ↑  ← Click to toggle asc/desc
</th>
```

**Pros:** Discoverable, expected behavior
**Cons:** Requires JavaScript

**Dedicated controls:**
```html
<select onchange="sort(event.target.value)">
  <option>Sort by Price (High to Low)</option>
  <option>Sort by Price (Low to High)</option>
</select>
```

**Pros:** Explicit, accessible
**Cons:** Takes space

**RECOMMENDATION:** Use click-to-sort on headers. It's standard financial UI.

---

### Filtering: Dropdown, sidebar, or search?

**Dropdown (simplest):**
```html
<select>
  <option>All Assets</option>
  <option>Stocks</option>
  <option>ETFs</option>
</select>
```

**Sidebar (more options):**
```html
<aside>
  <h3>Filter</h3>
  <div>
    <label><input type="checkbox"> Stocks</label>
    <label><input type="checkbox"> ETFs</label>
    <label><input type="checkbox"> Bonds</label>
  </div>
</aside>
```

**Search (for >20 items):**
```html
<input type="search" placeholder="Find holding...">
```

**RECOMMENDATION:** Use dropdown for 3-5 options, search for 20+

---

## Form Input Styling Decision

### Inline (minimal) approach:

```css
input {
  border: 1px solid #e0e0e0;
  padding: 8px 12px;
  font-size: 13px;
  border-radius: 3px;
}

input:focus {
  outline: none;
  border-color: #0073e6;
  box-shadow: 0 0 0 2px rgba(0, 115, 230, 0.1);
}
```

**Pros:** Compact, financial style
**Cons:** Users might miss active state

### Generous (accessible) approach:

```css
input {
  border: 2px solid #e0e0e0;
  padding: 12px;
  font-size: 16px;
  border-radius: 4px;
}

input:focus {
  outline: none;
  border-color: #0073e6;
}
```

**Pros:** Easier to see and interact with
**Cons:** Takes more space

**RECOMMENDATION:** Use inline (minimal) to match financial dashboards. Ensure contrast ratio is 4.5:1.

---

## Dark Mode Decision: To Build or Not?

### Option 1: Light Mode Only

**Pros:**
- Faster to ship
- Matches Bloomberg/WSJ
- Standard for financial apps
- Better for elderly users

**Cons:**
- Users may request dark mode
- Modern apps have it

---

### Option 2: System Preference Only

```css
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a1a;
    --text: #fff;
  }
}
```

**Pros:**
- Respects OS setting
- Zero user confusion
- Minimal code

**Cons:**
- Some users want to override

---

### Option 3: User Toggle

```html
<button onclick="toggleDarkMode()">
  🌙 Dark Mode
</button>
```

**Pros:**
- User control
- Modern feel

**Cons:**
- More code
- Must persist setting
- Adds complexity

**RECOMMENDATION FOR FINTEL:** Option 2
- Use system preference detection
- No manual toggle
- Keep it simple

---

## Performance Decision: CSS-in-JS vs. CSS Files

### Option 1: CSS Files (Recommended)

```html
<link rel="stylesheet" href="/styles/main.css">
```

**Pros:**
- Cached separately
- Smaller JS bundle
- Familiar to teams
- Financial sites use this

**Cons:**
- One more HTTP request

---

### Option 2: CSS-in-JS (Tailwind, styled-components)

```jsx
<div className="flex gap-4 p-16">
```

**Pros:**
- Dynamic styling
- Scoped styles
- Single bundle

**Cons:**
- Larger JS bundle
- Slower runtime
- Financial dashboards don't need this

**RECOMMENDATION:** CSS Files (plain CSS or SCSS)

No Tailwind, no styled-components. Keep it fast.

---

## Summary Decision Matrix

| Decision | Fintel Choice | Reason |
|----------|---|---|
| Navigation | Top nav + tabs | 4 primary sections, mobile-friendly |
| Tab count | Max 7 per group | Prevent horizontal scroll on desktop |
| Font size | 13px body, 16px headings | Data-dense dashboard |
| Status colors | Green/red only | Financial standard |
| Layout | Single column mobile, 2-col desktop | Responsive at 768px |
| Tables | Native `<table>` | Semantic, fast, accessible |
| Sorting | Click column header | Expected behavior |
| Filtering | Dropdown (3-5 options) | Compact, simple |
| Dark mode | System preference | Minimal code |
| CSS | Plain CSS/SCSS | Fast, no overhead |
| Icons | Unicode symbols (↑ ↓) | No image files |
| Fonts | System sans-serif | Fast, OS-native |
| Components | Reusable CSS classes | No framework overhead |

---

## Implementation Priority

### Week 1: Foundations
1. Color system (CSS variables)
2. Typography baseline
3. Table styling
4. Navigation structure

### Week 2: Components
1. Tabbed data grid
2. Metric cards
3. Holdings table
4. Responsive layout

### Week 3: Polish
1. Dark mode (if using system preference)
2. Animations (hover effects)
3. Accessibility audit
4. Performance optimization

---

## Testing Checklist Before Launch

- [ ] Test in Safari, Chrome, Firefox
- [ ] Test on iPhone 12 (375px viewport)
- [ ] Test on iPad (768px viewport)
- [ ] Test on desktop (1200px+)
- [ ] Color contrast ratio 4.5:1 minimum
- [ ] Screen reader navigation works
- [ ] Keyboard navigation works (Tab key)
- [ ] No layout shift on scroll
- [ ] Load time under 2 seconds
- [ ] Performance: Lighthouse score 90+

This is your decision framework. Refer back to it when faced with design choices.
