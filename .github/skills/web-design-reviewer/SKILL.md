 ---
name: web-design-reviewer
description: 'This skill enables visual inspection of websites running locally or remotely to identify and fix design issues. Triggers on requests like "review website design", "check the UI", "fix the layout", "find design problems". Detects issues with responsive design, accessibility, visual consistency, and layout breakage, then performs fixes at the source code level.'
---

# Web Design Reviewer

This skill enables visual inspection and validation of website design quality, identifying and fixing issues at the source code level.

## Scope of Application

- Static sites (HTML/CSS/JS)
- SPA frameworks such as React / Vue / Angular / Svelte
- Full-stack frameworks such as Next.js / Nuxt / SvelteKit
- Any other web application

## Prerequisites

1. **Target website must be running** — Local development server (e.g., `http://localhost:3000`)
2. **Browser automation must be available** — Screenshot capture, page navigation, DOM information retrieval
3. **Access to source code (when making fixes)** — Project must exist within the workspace

## Workflow Overview

```
Step 1: Information Gathering → Step 2: Visual Inspection → Step 3: Issue Fixing → Step 4: Re-verification
```

## Step 1: Information Gathering

### Automatic Project Detection

```
Detection targets:
├── package.json    → Framework and dependencies
├── tsconfig.json   → TypeScript usage
├── tailwind.config → Tailwind CSS
├── next.config     → Next.js
└── src/ or app/    → Source directory
```

### Styling Method Detection

| Method | Detection | Edit Target |
|--------|-----------|-------------|
| Pure CSS | `*.css` files | Global CSS or component CSS |
| SCSS/Sass | `*.scss`, `*.sass` | SCSS files |
| Tailwind CSS | `tailwind.config.*` | className in components |
| styled-components | `styled.` in code | JS/TS files |

## Step 2: Visual Inspection

### Viewport Testing (Responsive)

| Name | Width | Representative Device |
|------|-------|----------------------|
| Mobile | 375px | iPhone SE/12 mini |
| Tablet | 768px | iPad |
| Desktop | 1280px | Standard PC |
| Wide | 1920px | Large display |

### Inspection Checklist

**Layout Issues**
- Element Overflow — Content overflows from parent element or viewport (High)
- Element Overlap — Unintended overlapping of elements (High)
- Alignment Issues — Grid or flex alignment problems (Medium)

**Responsive Issues**
- Non-mobile Friendly — Layout breaks on small screens (High)
- Breakpoint Issues — Unnatural transitions when screen size changes (Medium)
- Touch Targets — Buttons too small on mobile (Medium)

**Accessibility Issues**
- Insufficient Contrast — Low contrast ratio between text and background (High)
- No Focus State — Cannot determine state during keyboard navigation (High)
- Missing alt Text — No alternative text for images (Medium)

**Visual Consistency**
- Font Inconsistency — Mixed font families (Medium)
- Color Inconsistency — Non-unified brand colors (Medium)

## Step 3: Issue Fixing

### Fix Principles

1. **Minimal Changes**: Only make the minimum changes necessary to resolve the issue
2. **Respect Existing Patterns**: Follow existing code style in the project
3. **Avoid Breaking Changes**: Be careful not to affect other areas

### Issue Prioritization

- **P1**: Fix Immediately (Layout issues affecting functionality)
- **P2**: Fix Next (Visual issues degrading UX)
- **P3**: Fix If Possible (Minor visual inconsistencies)

## Step 4: Re-verification

1. Reload browser (or wait for development server HMR)
2. Capture screenshots of fixed areas
3. Compare before and after
4. Verify that fixes haven't affected other areas

**Iteration Limit**: If more than 3 fix attempts are needed for a specific issue, consult the user.

## Best Practices

### DO
- ✅ Always save screenshots before making fixes
- ✅ Fix one issue at a time and verify each
- ✅ Follow the project's existing code style
- ✅ Confirm with user before major changes

### DON'T
- ❌ Large-scale refactoring without confirmation
- ❌ Ignoring design systems or brand guidelines
- ❌ Fixing multiple issues at once (difficult to verify)
