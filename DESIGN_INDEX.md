# Fintel Design System Index
## Quick Navigation & Reference

---

## Start Here

**New to the design system?** Start with the **5-minute quick start**:
- Read: `DESIGN_QUICK_START.md`
- Copy: HTML/CSS template
- Build: Your first component

**Have 30 minutes?** Get decision clarity:
- Read: `DESIGN_DECISIONS.md`
- Choose: Navigation structure, colors, density
- Plan: Your implementation

**Need everything?** Deep dive:
- Read: `DESIGN_PATTERNS_ANALYSIS.md` (comprehensive)
- Reference: `DESIGN_COMPONENTS.md` (code)
- Check: `DESIGN_DECISIONS.md` (choices)
- Use: `DESIGN_QUICK_START.md` (build)

---

## File Guide

### DESIGN_PATTERNS_ANALYSIS.md
**What:** Comprehensive research findings with code examples
**Length:** ~8000 words, 10 sections
**Best for:** Understanding the WHY behind patterns

**Sections:**
1. Navigation patterns (MarketWatch structure)
2. Tab patterns for data categorization
3. Dark mode & color implementation
4. Dense data presentation & typography
5. Section organization patterns
6. Sidebar vs. top nav decision matrix
7. Actionable patterns for your dashboard
8. Implementation checklist
9. Code pattern examples (HTML/CSS)
10. Key takeaways

**When to read:**
- Understanding Bloomberg/MarketWatch patterns
- Need to explain design decisions to stakeholders
- Deep-diving on typography, color, or spacing
- Onboarding new team members

---

### DESIGN_COMPONENTS.md
**What:** 5 ready-to-use React components with complete code
**Length:** ~3000 words, 30+ code examples
**Best for:** Copy-paste implementation

**Components:**
1. TabbedDataGrid (market data with US/Europe/Asia tabs)
2. MetricCard (compact KPI displays)
3. MainNavigation (responsive sticky header)
4. HoldingsTable (full-featured with sorting)
5. DashboardLayout (responsive grid layout)

**Each component includes:**
- React JSX code
- Complete CSS styling
- Usage examples
- Props documentation

**When to use:**
- Building portfolio dashboard
- Need working code, not theory
- Adapting for your specific data
- Understanding component structure

---

### DESIGN_QUICK_START.md
**What:** 80/20 rules and immediate action items
**Length:** ~2000 words, highly scannable
**Best for:** Getting started fast

**Contents:**
- 5 things to do first (with code)
- Copy-paste HTML/CSS template
- Common pattern solutions
- Mobile breakpoints
- Performance checklist
- Accessibility checklist
- Before-launch verification

**When to use:**
- Starting implementation
- Need quick answers (5 minutes)
- Verifying you're on track
- Pre-launch checklist

---

### DESIGN_DECISIONS.md
**What:** Decision framework for design choices
**Length:** ~4000 words, decision matrices
**Best for:** Making structural decisions

**Decision Trees:**
1. Navigation structure (how many items? sidebar or top nav?)
2. Tabs vs. navigation (when to use each)
3. Data density (choosing font size based on row count)
4. Color strategy (status-focused vs. category-focused)
5. Layout patterns (desktop, tablet, mobile)
6. Mobile breakpoints (768px, 1024px thresholds)
7. Typography scale (minimal vs. generous)
8. State indicators (icons, color, text combinations)
9. Cards vs. tables (when to use each)
10. Form styling (inline vs. generous)
11. Dark mode strategy
12. Performance decisions (CSS files vs. CSS-in-JS)

**When to use:**
- Deciding between options
- Facing tradeoffs
- Onboarding to decision logic
- Future-proofing choices

---

### RESEARCH_SUMMARY.md
**What:** High-level summary of research findings
**Length:** ~1500 words, scannable
**Best for:** Overview and file guide

**Contents:**
- What was researched (Bloomberg, MarketWatch)
- Key findings (5 main insights)
- Files created and how to use them
- Quick reference (colors, typography, spacing)
- Implementation checklist
- Performance and accessibility targets
- Next steps

**When to use:**
- Getting overview before deep dive
- Understanding research methodology
- Presenting to stakeholders
- Remembering the main principles

---

## By Use Case

### "I'm building the main dashboard"
1. Read: `DESIGN_QUICK_START.md` (5 min)
2. Code: Copy the template
3. Component: Use `TabbedDataGrid` + `MetricCard` from `DESIGN_COMPONENTS.md`
4. Styling: Reference color/typography in `DESIGN_PATTERNS_ANALYSIS.md` Part 3 & 4

### "I need to decide on navigation"
1. Read: `DESIGN_DECISIONS.md` → Navigation Structure Decision Tree
2. Confirm: Cross-check with `DESIGN_PATTERNS_ANALYSIS.md` Part 1
3. Code: Use `MainNavigation` component from `DESIGN_COMPONENTS.md`

### "I'm adding a new data view"
1. Read: `DESIGN_DECISIONS.md` → Tabs vs. Navigation
2. Code: Use `TabbedDataGrid` component from `DESIGN_COMPONENTS.md`
3. Styling: Match colors/typography from quick-start

### "I need to explain this to stakeholders"
1. Share: `RESEARCH_SUMMARY.md` (overview)
2. Detail: `DESIGN_PATTERNS_ANALYSIS.md` Parts 1-3 (why these patterns)
3. Show: Screenshots from `DESIGN_COMPONENTS.md`

### "I'm bringing on a new developer"
1. Start: `DESIGN_QUICK_START.md` (5 minutes)
2. Dive: `DESIGN_PATTERNS_ANALYSIS.md` (30 minutes)
3. Reference: `DESIGN_COMPONENTS.md` (for code)
4. Bookmark: `DESIGN_DECISIONS.md` (for future choices)

### "We need dark mode"
1. Read: `DESIGN_DECISIONS.md` → Dark Mode Decision
2. Implement: System preference approach (CSS `@media prefers-color-scheme`)
3. Reference: Color palette in `DESIGN_QUICK_START.md`

### "Performance is slow"
1. Check: Performance section in `DESIGN_QUICK_START.md`
2. Reference: Part 4 of `DESIGN_PATTERNS_ANALYSIS.md` (typography)
3. Code: Plain CSS from `DESIGN_COMPONENTS.md` (not CSS-in-JS)

### "Accessibility audit found issues"
1. Read: Accessibility checklist in `DESIGN_QUICK_START.md`
2. Reference: `DESIGN_PATTERNS_ANALYSIS.md` Part 9 (code examples)
3. Component: Use semantic HTML from `DESIGN_COMPONENTS.md`

---

## The Design Principles (In Order)

1. **Everything serves the data**
   - No decorative colors, whitespace, or effects
   - Every pixel has a purpose

2. **Use color for information, not decoration**
   - Green = positive
   - Red = negative
   - Everything else = neutral

3. **Density through typography, not whitespace**
   - 13px font, 1.4 line-height, 8-10px padding
   - No unnecessary margins

4. **Navigation should be simple**
   - 4-6 primary sections max
   - Use tabs for data filtering, not navigation

5. **Semantic HTML over custom divs**
   - Use `<table>` for tables
   - Use `<tablist>` for tabs
   - Proper heading hierarchy

6. **Responsive by constraint, not complexity**
   - Three breakpoints: desktop, tablet, mobile
   - Single column on mobile
   - Horizontal scroll for tables and tabs

7. **Performance through simplicity**
   - Plain CSS (no CSS-in-JS)
   - System fonts (no custom fonts)
   - Unicode symbols (no SVG icons)

8. **Accessibility by design**
   - 4.5:1 contrast minimum
   - 40x40px click targets
   - Full keyboard navigation

---

## Color Reference

```css
--positive: #00a651;      /* Green for up/gain */
--negative: #d2201a;      /* Red for down/loss */
--text-primary: #000;     /* Main text */
--text-secondary: #666;   /* Secondary text */
--bg-primary: #fff;       /* Main background */
--bg-secondary: #f5f5f5;  /* Secondary background */
--border: #e0e0e0;        /* Borders */
```

---

## Typography Reference

```css
/* Sizes */
h1: 24px
h2: 16px
h3: 14px
body: 13px
small: 12px

/* Line-height */
all: 1.4

/* Font-weight */
normal: 400
headings: 600

/* Font-family */
body: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif
numbers: 'Monaco', 'Courier New', monospace
```

---

## Spacing Reference

```css
/* Padding */
button: 8px 12px
table cell: 10px 12px
section: 16px

/* Margin */
between sections: 20px
between cards: 12px
never use: 24px, 32px, 40px

/* Breakpoints */
desktop: 1200px+
tablet: 768px-1199px
mobile: 375px-767px
```

---

## Common Questions

**Q: How many tabs should I have?**
A: 3-8 per group max. If more, group them.
Read: `DESIGN_DECISIONS.md` → Tabs vs. Navigation

**Q: Should I use a sidebar?**
A: Only if 8+ primary sections. Otherwise, top nav.
Read: `DESIGN_PATTERNS_ANALYSIS.md` → Part 6

**Q: What font size for my data?**
A: 13px for dense, 14px for readable, 16px for mobile-first.
Read: `DESIGN_DECISIONS.md` → Typography Scale

**Q: Can I use other colors?**
A: Only green and red for status. Everything else is neutral.
Read: `DESIGN_PATTERNS_ANALYSIS.md` → Part 3

**Q: Dark mode support?**
A: Use system preference, no manual toggle.
Read: `DESIGN_DECISIONS.md` → Dark Mode Decision

**Q: How do I make it fast?**
A: Plain CSS, system fonts, no JS animations.
Read: `DESIGN_QUICK_START.md` → Performance Checklist

**Q: Is this mobile-friendly?**
A: Yes. Hamburger menu at 768px, single column, tabs scroll.
Read: `DESIGN_DECISIONS.md` → Mobile Breakpoints

**Q: Can I use Tailwind/Bootstrap?**
A: No. Use plain CSS, faster and simpler.
Read: `DESIGN_DECISIONS.md` → Performance Decision

---

## Implementation Timeline

**Day 1:**
- Read: `DESIGN_QUICK_START.md`
- Copy: HTML/CSS template
- Set: Color system (CSS variables)

**Day 2-3:**
- Build: Typography baseline
- Create: Table styling
- Implement: Navigation structure

**Day 4-5:**
- Build: Tab component
- Build: Data grid component
- Test: Responsive at breakpoints

**Day 6-7:**
- Accessibility audit
- Performance optimization
- Finalize and launch

---

## Team Onboarding

**Step 1 (5 min):** Read `DESIGN_QUICK_START.md`
**Step 2 (30 min):** Read `DESIGN_PATTERNS_ANALYSIS.md`
**Step 3 (30 min):** Review `DESIGN_COMPONENTS.md`
**Step 4 (ongoing):** Reference `DESIGN_DECISIONS.md` for choices

**Then:**
- Build first component using template
- Ask questions
- Reference documents as needed

---

## Keeping This Alive

**Update DESIGN_DECISIONS.md when:**
- Adding new component types
- Changing color system
- Adjusting typography
- New responsive breakpoints

**Update DESIGN_COMPONENTS.md when:**
- Creating new reusable component
- Improving existing component code
- Adding new patterns

**Update DESIGN_QUICK_START.md when:**
- Simplifying a process
- Finding faster approach
- New common questions

**Keep DESIGN_PATTERNS_ANALYSIS.md as reference only** (don't update unless research changes)

---

## Source & Confidence

**Research Source:** Direct analysis of Bloomberg.com and MarketWatch.com (Jan 11, 2026)
**Confidence:** HIGH - Direct observation of production financial dashboards
**Applicability:** Financial data dashboards with many tabs/sections
**Limitations:** Based on US-centric sites; may differ for international audiences

---

## Final Note

This design system is built on **constraint and clarity**. The patterns succeed because they prioritize user tasks over aesthetics.

Every decision is documented. Every code example is tested. Every principle has evidence.

Build with confidence.

---

## Quick Links

- `DESIGN_PATTERNS_ANALYSIS.md` - Deep research
- `DESIGN_COMPONENTS.md` - Copy-paste code
- `DESIGN_QUICK_START.md` - Fast start
- `DESIGN_DECISIONS.md` - Decision framework
- `RESEARCH_SUMMARY.md` - Overview
- `DESIGN_INDEX.md` - This file
