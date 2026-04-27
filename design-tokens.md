# Design Tokens — AI Factory Dashboard

Single source of truth untuk semua nilai visual. Wajib digunakan via CSS Variables atau Tailwind config — **jangan hardcode**.

## Colors

### Background Layers
```css
--bg-base:      #0a0b0e;  /* Main app background */
--bg-panel:     #111318;  /* Sidebar, topbar, card */
--bg-card:      #181b22;  /* Card with subtle elevation */
--bg-card-2:    #1c1f28;  /* Card on hover */
--bg-hover:     #1e2229;  /* Interactive hover state */
--bg-active:    #1a2035;  /* Active nav item */
```

### Borders
```css
--border:       #252830;  /* Default border */
--border-light: #2e3340;  /* Hover/focus border */
```

### Text Hierarchy
```css
--text-primary:   #eef0f5;  /* Headings, important values */
--text-secondary: #a8aec0;  /* Body text, descriptions */
--text-tertiary:  #7a8099;  /* Meta info, labels */
--text-muted:     #454d66;  /* Hints, placeholders */
```

### Accent Colors
```css
--accent-green:  #00e5a0;  /* Success, primary brand */
--accent-red:    #ff4d6d;  /* Errors, rage tag, urgent */
--accent-amber:  #ffb347;  /* Pending, warning, primary KPI */
--accent-blue:   #4d9fff;  /* Info, processing, fail tag */
--accent-purple: #a78bfa;  /* Videos KPI, clutch tag */
--accent-pink:   #ff6ec7;  /* Misc accent, channel avatar */
```

### Gradients
```css
--gradient-primary: linear-gradient(135deg, #ffb347 0%, #ff6b35 100%);
--gradient-green:   linear-gradient(135deg, #00e5a0 0%, #00b894 100%);
--gradient-channel: linear-gradient(135deg, #ff4d6d, #ff6ec7);
--gradient-user:    linear-gradient(135deg, #a78bfa, #4d9fff);
```

## Spacing

Gunakan kelipatan 4px:
- `4px`, `8px`, `12px`, `14px`, `16px`, `18px`, `22px`, `24px`, `26px`, `32px`

**Padding cards:** 18px (default), 22px (hero)
**Gap grid:** 14px (bento), 8px (lists)
**Padding container:** 24px

## Border Radius

```css
--radius-sm:  6px;   /* small buttons, badges */
--radius-md:  10px;  /* nav items, list items */
--radius-lg:  14px;  /* cards */
--radius-xl:  20px;  /* hero, large containers */
```

## Typography

### Font Families
```css
--font-display: 'Syne', sans-serif;       /* Headlines, UI text */
--font-mono:    'DM Mono', monospace;     /* Numbers, code, labels */
```

### Font Sizes
| Use Case | Size | Weight | Family |
|---|---|---|---|
| Big primary KPI | 64px | 800 | mono |
| Big stat value | 28px | 700 | mono |
| Hero title | 24px | 700 | display |
| Card stat | 16px | 700 | mono |
| Section title (uppercase) | 11px | 600 | mono |
| Body | 12.5-13px | 400-500 | display |
| Meta label | 10-11px | 500-600 | mono |
| Tag/badge | 9-10px | 600 | mono |

### Letter Spacing
- Uppercase labels: `0.1em` (`tracking-wider`)
- Brand name: `0.04em`
- Big KPI value: `-0.02em` (tighter)

## Shadows

```css
/* Card hover */
box-shadow: 0 4px 20px rgba(0,0,0,.4);

/* Primary button */
box-shadow: 0 4px 14px rgba(255,179,71,.25);

/* Brand icon glow */
box-shadow: 0 0 20px rgba(0,229,160,.3);

/* Avatar ring */
box-shadow: 0 0 0 2px var(--bg-panel), 0 0 0 3px var(--border);
```

## Animations

### Duration
- Fast (hover): `120-150ms`
- Default (transitions): `200-300ms`
- Stagger delay (cards on mount): `40ms` per index
- Number counter: `800ms`
- Pulse cycle: `1400-2000ms`

### Easing
- Default: `ease`
- Smooth entrance: `cubic-bezier(0.16, 1, 0.3, 1)`
- Bouncy: `cubic-bezier(0.34, 1.56, 0.64, 1)`

### Keyframes Library

```css
@keyframes cardIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes itemIn {
  from { opacity: 0; transform: translateX(-4px); }
  to   { opacity: 1; transform: translateX(0); }
}

@keyframes countUp {
  from { opacity: 0; transform: translateY(20px) scale(.8); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes live-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: .5; }
}

@keyframes stage-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(77,159,255,.5); }
  50%      { box-shadow: 0 0 0 8px rgba(77,159,255,0); }
}

@keyframes progress-shimmer {
  0%, 100% { width: 50%; }
  50%      { width: 55%; }
}

@keyframes growBar {
  from { width: 0; }
}
```

## Z-Index Scale

```css
--z-dropdown:  10;
--z-sticky:    20;
--z-modal:     50;
--z-toast:     60;
--z-tooltip:   70;
```

## Tailwind Config Mapping (jika pakai Tailwind)

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#0a0b0e',
          panel: '#111318',
          card: '#181b22',
          'card-2': '#1c1f28',
          hover: '#1e2229',
          active: '#1a2035',
        },
        border: {
          DEFAULT: '#252830',
          light: '#2e3340',
        },
        text: {
          primary: '#eef0f5',
          secondary: '#a8aec0',
          tertiary: '#7a8099',
          muted: '#454d66',
        },
        accent: {
          green: '#00e5a0',
          red: '#ff4d6d',
          amber: '#ffb347',
          blue: '#4d9fff',
          purple: '#a78bfa',
          pink: '#ff6ec7',
        },
      },
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        mono: ['DM Mono', 'monospace'],
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '14px',
        xl: '20px',
      },
    },
  },
}
```
