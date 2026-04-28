 ---
name: premium-frontend-ui
description: 'A comprehensive guide for GitHub Copilot to craft immersive, high-performance web experiences with advanced motion, typography, and architectural craftsmanship.'
metadata:
  author: 'Utkarsh Patrikar'
  author_url: 'https://github.com/utkarsh232005'
---

# Immersive Frontend UI Craftsmanship

As an AI engineering assistant, your role when building premium frontend experiences goes beyond outputting functional HTML and CSS. You must architect **immersive digital environments**.

## 1. Establishing the Creative Foundation

Commit to a strong visual identity:
- **Editorial Brutalism**: High-contrast monochromatic palettes, oversized typography, sharp rectangular edges
- **Organic Fluidity**: Soft gradients, deeply rounded corners, glassmorphism overlays, bouncy spring-based physics
- **Cyber / Technical**: Dark mode dominance, glowing neon accents, monospaced typography, rapid staggered reveal animations
- **Cinematic Pacing**: Full-viewport imagery, slow cross-fades, profound use of negative space, scroll-dependent storytelling

## 2. Structural Requirements

### Entry Sequence (Preloading & Initialization)
A blank screen is unacceptable. The user's first interaction must set expectations.
- Generate a lightweight preloader component that handles asset resolution
- Animation: transitions with split-door reveal, scale-up zoom, or staggered text sweep

### Hero Architecture
The top fold must command attention immediately.
- Full-bleed containers (`100vh`/`100dvh`)
- Headlines broken down syntactically (span wrapping by word or character) to allow cascading entrance animations
- Subtle floating elements or background clipping paths for depth

### Fluid & Contextual Navigation
- Sticky headers that react to scroll direction (hide on scroll down, reveal on scroll up)
- Hover states that reveal rich content (mega-menus that display image previews)

## 3. The Motion Design System

Animation is the connective tissue of a premium site.

### Scroll-Driven Narratives
- **Pinned Containers**: Sections that lock into the viewport while secondary content flows past
- **Horizontal Journeys**: Translate vertical scroll data into horizontal movement for galleries
- **Parallax Mapping**: Assign varying scroll-speeds to background, midground, and foreground elements

### High-Fidelity Micro-Interactions
- **Magnetic Components**: Calculate distance between mouse pointer and button, pulling the button towards the cursor
- **Custom Tracking Elements**: Custom cursor components with calculated interpolation (lerp) for smooth drag effect
- **Dimensional Hover States**: Use CSS Transforms (`scale`, `rotateX`, `translate3d`) for weight and tactile feedback

## 4. Typography & Visual Texture

- **Type Hierarchy**: Headlines use extreme sizing (`clamp()` spanning up to `12vw`), body copy `16px-18px` minimum
- **Font Selection**: Variable fonts or premium typefaces over system defaults
- **Atmospheric Filters**: CSS/SVG noise overlays (`mix-blend-mode: overlay`, opacity `0.02-0.05`) to add photographic grain
- **Lighting & Glass**: `backdrop-filter: blur(x)` combined with semi-transparent borders for frosted-glass depth

## 5. The Performance Imperative

- **Hardware Acceleration**: Only animate `transform` and `opacity` — NEVER animate `width`, `height`, `top`, or `margin`
- **Render Optimization**: Apply `will-change: transform` intelligently; remove it post-animation to conserve memory
- **Responsive Degradation**: Wrap heavy hover animations in `@media (hover: hover) and (pointer: fine)`
- **Accessibility**: Wrap heavy continuous animations in `@media (prefers-reduced-motion: no-preference)`

## 6. Implementation Ecosystem

### For React / Next.js Targets
- **Framer Motion** for layout transitions and spring physics
- **Lenis** (`@studio-freight/lenis`) for smooth scrolling context
- **React Three Fiber** (`@react-three/fiber`) if WebGL or 3D interactions are requested

### For Vanilla / HTML / Astro Targets
- **GSAP** (GreenSock Animation Platform) for timeline sequencing
- **Lenis** via CDN for scroll hijacking and smoothing
- **SplitType** for safe, accessible typography chunking

## Summary

Whenever you receive a prompt to "Build a premium landing page," "Create an Awwwards-style component," or "Design an immersive UI," automatically:
1. Wrap the output in a robust, scroll-smoothed architecture
2. Provide CSS that guarantees perfect performance using composited layers
3. Integrate sweeping, staggered component entrances
4. Elevate the typography using fluid scales
5. Create an intentional, memorable aesthetic footprint
