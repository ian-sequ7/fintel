# Financial Dashboard Research Summary
## Bloomberg & MarketWatch Design Analysis

**Research Date:** January 11, 2026
**Method:** Direct website accessibility analysis + visual inspection
**Scope:** Navigation patterns, data presentation, color strategy, typography

---

## What Was Researched

### Bloomberg.com
- Primary navigation structure
- Tab patterns for data categorization
- Typography and spacing
- Dense table layouts
- Dark/light mode approach

### MarketWatch.com
- Horizontal navigation (4 primary sections)
- Tab groups (7 market overview tabs)
- Data table styling (13px font, 8-10px padding)
- Color usage (green/red for status only)
- Responsive behavior

---

## Key Findings

### 1. Navigation Architecture
**Pattern:** 4-6 primary horizontal items (top nav) + tabs for data filtering
- MarketWatch: Investing, Personal Finance, Retirement, Economy
- Not: deep nesting, dropdowns, or complex hierarchies
- Tabs appear within sections for data categorization (US/Europe/Asia)

**Actionable:** Fintel should use top nav for Portfolio/Research/Trading/Account, with tabs inside each section.

---

### 2. Data Presentation
**Density Strategy:** 13px font, 1.4 line-height, 8-10px vertical padding
- Results in ~26 rows visible per viewport
- Monospace font for numbers
- Right-aligned numeric columns
- No decorative whitespace

**Color: Green/Red Only**
- Green (#00A651) = positive change, up trends
- Red (#D2201A) = negative change, down trends
- Everything else = monochromatic (black/white/gray)
- No colors for categories or decoration

**Actionable:** Use 13px baseline, set up CSS variables for green/red.

---

### 3. Tab Pattern
**When to use tabs:**
- Related data that user filters (US/Europe/Asia markets)
- 3-8 options maximum per group
- One tab selected by default
- Tabs scroll horizontally on mobile

**When NOT to use tabs:**
- Different sections (those are navigation)
- More than 8 items (restructure into groups)

**Actionable:** Implement tab groups for market data, portfolio views, etc.

---

### 4. Responsive Approach
**Three breakpoints:**
- Desktop (1200px+): Full layout, all nav visible
- Tablet (768px-1199px): Adjusted columns, horizontal scrolling
- Mobile (375px-767px): Single column, hamburger menu, tabs scroll

**Actionable:** Test at 1200px, 768px, and 375px. Use hamburger menu on mobile.

---

### 5. Implementation Priority
**Level 1 (Essential):**
- Color system (CSS variables)
- Typography baseline (13px/14px)
- Table styling
- Navigation structure

**Level 2 (Core):**
- Tab patterns
- Data grid component
- Responsive navigation
- Density optimization

**Level 3 (Polish):**
- Dark mode (system preference)
- Advanced sorting/filtering
- Accessibility enhancements
- Animation polish

---

## Files Created

### 1. `DESIGN_PATTERNS_ANALYSIS.md` (Comprehensive)
- Full analysis with code examples
- 10 parts covering all aspects
- Deep dive into Bloomberg/MarketWatch patterns
- Implementation checklist
- React component patterns

**Use when:** You need deep understanding or referencing specific patterns

---

### 2. `DESIGN_COMPONENTS.md` (Code Library)
- 5 reusable components
- React + CSS code
- Copy-paste ready
- Examples: TabbedDataGrid, MetricCard, MainNavigation, HoldingsTable, DashboardLayout

**Use when:** Building components, need code examples

---

### 3. `DESIGN_QUICK_START.md` (Fast Reference)
- 80/20 rule: 5 things to do first
- Copy-paste HTML/CSS template
- Common pattern solutions
- Performance & accessibility checklists
- Before-ship verification

**Use when:** Starting implementation, need quick answers

---

### 4. `DESIGN_DECISIONS.md` (Decision Framework)
- Decision trees for navigation, tabs, density
- When to use sidebars vs. top nav
- Color strategy scenarios
- Responsive breakpoints
- Typography scale options
- Sorting/filtering decisions
- Implementation priority

**Use when:** Making design decisions, facing tradeoffs

---

### 5. `RESEARCH_SUMMARY.md` (This File)
- Overview of research
- Key findings summary
- File guide
- Quick reference links

---

## How to Use These Documents

### If you have 5 minutes:
1. Read `DESIGN_QUICK_START.md`
2. Copy the HTML/CSS template
3. Start building

### If you have 30 minutes:
1. Read `DESIGN_DECISIONS.md` for your specific decisions
2. Skim `DESIGN_COMPONENTS.md` for relevant components
3. Plan implementation

### If you need to understand everything:
1. Start with `DESIGN_PATTERNS_ANALYSIS.md` (comprehensive)
2. Reference `DESIGN_COMPONENTS.md` for code
3. Use `DESIGN_QUICK_START.md` as implementation guide
4. Refer to `DESIGN_DECISIONS.md` for choices

### For ongoing development:
1. Keep `DESIGN_QUICK_START.md` open
2. Reference specific components from `DESIGN_COMPONENTS.md`
3. Consult `DESIGN_DECISIONS.md` when adding features
4. Check `DESIGN_PATTERNS_ANALYSIS.md` for edge cases

---

## The Single Most Important Rule

**Everything visible on the page must serve the data.**

No decorative colors, rounded corners (unless accessible), large whitespace, gradients, custom fonts, or fancy animations.

Financial users are task-focused. Respect their time.

---

## Quick Reference: Colors

```css
--positive: #00a651;   /* Green for gains/up */
--negative: #d2201a;   /* Red for losses/down */
--text-primary: #000;
--text-secondary: #666;
--bg-primary: #fff;
--bg-secondary: #f5f5f5;
--border: #e0e0e0;
```

---

## Quick Reference: Typography

```css
body { font-size: 13px; line-height: 1.4; }
h2 { font-size: 16px; font-weight: 600; }
h3 { font-size: 14px; font-weight: 600; }
.small { font-size: 12px; }
.number { font-family: 'Monaco', 'Courier New', monospace; }
```

---

## Quick Reference: Spacing

```css
/* Padding */
button, input: 8px 12px;
table cell: 10px 12px;
section: 16px;

/* Margins */
between sections: 20px;
between cards: 12px;
never use: 24px, 32px, 40px (too much)
```

---

## What NOT to Do

Based on Bloomberg/MarketWatch analysis:

- Don't use color for categories (users expect green=good, red=bad)
- Don't use custom fonts (system sans-serif is faster)
- Don't nest navigation deeper than 2 levels
- Don't make tables with divs (use semantic `<table>`)
- Don't add dark mode toggle (let system preference decide)
- Don't use more than 7 tabs per group
- Don't use shadows or decorative effects
- Don't make padding/margins larger than 20px between sections
- Don't use icons in data tables (use Unicode: ↑ ↓)
- Don't force dark mode on all users

---

## Implementation Checklist

**Week 1:**
- [ ] Set up CSS variables (colors, typography)
- [ ] Create typography baseline (13px)
- [ ] Style tables (`<table>` with semantic markup)
- [ ] Build navigation structure

**Week 2:**
- [ ] Implement tab component (with ARIA roles)
- [ ] Build metric cards
- [ ] Create holdings table with sorting
- [ ] Test responsive at 768px breakpoint

**Week 3:**
- [ ] Add filtering controls
- [ ] Implement search if needed
- [ ] Accessibility audit
- [ ] Performance optimization

**Week 4:**
- [ ] Polish hover/focus states
- [ ] Dark mode (system preference, no toggle)
- [ ] Final testing (Safari, Chrome, Firefox, mobile)
- [ ] Ship

---

## Performance Targets

- Page load: <2 seconds
- CSS size: <20KB
- No custom fonts
- No JS animations on load
- Lighthouse score: 90+

---

## Accessibility Targets

- Color contrast: 4.5:1 minimum
- All buttons: 40x40px minimum touch target
- Keyboard navigation: Full support (Tab/Enter/Escape)
- Screen reader: Page reads correctly
- ARIA: `role="tab"`, `aria-selected`, `aria-controls` for interactive elements

---

## Next Steps

1. **Choose your structure** (top nav with 4-6 sections)
2. **Set color system** (CSS variables with green/red)
3. **Build baseline styles** (typography, tables, spacing)
4. **Create components** (tabs, navigation, data grid)
5. **Test responsively** (mobile, tablet, desktop)
6. **Audit accessibility** (contrast, keyboard, screen reader)
7. **Ship and iterate** (gather user feedback)

---

## Source Documentation

**Direct Analysis:**
- Bloomberg.com homepage (Jan 11, 2026)
- MarketWatch.com homepage (Jan 11, 2026)
- Accessibility snapshots of both sites
- Navigation structure via page inspector

**Confidence Level:** HIGH
- Direct website analysis, not third-party sources
- Patterns observed across multiple financial sites
- Consistent with financial UI best practices
- Proven patterns in production use

---

## Questions?

Refer to the specific document:

- **"How do I structure navigation?"** → `DESIGN_DECISIONS.md` (Navigation Decision Tree)
- **"What code do I use?"** → `DESIGN_COMPONENTS.md` (Copy-paste components)
- **"How do I start?"** → `DESIGN_QUICK_START.md` (5-minute guide)
- **"Why this pattern?"** → `DESIGN_PATTERNS_ANALYSIS.md` (Deep analysis)
- **"When should I use X vs. Y?"** → `DESIGN_DECISIONS.md` (Decision matrices)

---

## Final Thought

Professional financial dashboards succeed through **constraint and clarity**, not decoration.

Every pixel, every color, every space exists to serve the user's financial goals.

Build with this in mind, and your dashboard will join the ranks of Bloomberg and MarketWatch in clarity and efficiency.
