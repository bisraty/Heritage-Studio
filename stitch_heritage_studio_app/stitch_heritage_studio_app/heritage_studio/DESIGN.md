---
name: Heritage Studio
colors:
  surface: '#181210'
  surface-dim: '#181210'
  surface-bright: '#3f3835'
  surface-container-lowest: '#130d0b'
  surface-container-low: '#201a18'
  surface-container: '#251e1c'
  surface-container-high: '#2f2826'
  surface-container-highest: '#3b3331'
  on-surface: '#ede0dc'
  on-surface-variant: '#d4c4b0'
  inverse-surface: '#ede0dc'
  inverse-on-surface: '#362f2c'
  outline: '#9d8f7c'
  outline-variant: '#504535'
  surface-tint: '#fabc4d'
  primary: '#ffc665'
  on-primary: '#432c00'
  primary-container: '#e5a93c'
  on-primary-container: '#5e4000'
  inverse-primary: '#7e5700'
  secondary: '#efc05f'
  on-secondary: '#402d00'
  secondary-container: '#846000'
  on-secondary-container: '#ffe0aa'
  tertiary: '#ffc476'
  on-tertiary: '#462b00'
  tertiary-container: '#eda539'
  on-tertiary-container: '#623e00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdead'
  primary-fixed-dim: '#fabc4d'
  on-primary-fixed: '#281900'
  on-primary-fixed-variant: '#604100'
  secondary-fixed: '#ffdea3'
  secondary-fixed-dim: '#efc05f'
  on-secondary-fixed: '#261900'
  on-secondary-fixed-variant: '#5d4200'
  tertiary-fixed: '#ffddb5'
  tertiary-fixed-dim: '#ffb956'
  on-tertiary-fixed: '#2a1800'
  on-tertiary-fixed-variant: '#633f00'
  background: '#181210'
  on-background: '#ede0dc'
  surface-variant: '#3b3331'
typography:
  headline-xl:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Playfair Display
    fontSize: 34px
    fontWeight: '600'
    lineHeight: 42px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
    letterSpacing: '0'
  title-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: '0'
  title-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 17px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: '0'
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: '0'
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: '0'
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.03em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.06em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.25rem
  space-2xl: 3.5rem
---

## Brand & Style

This design system embodies the warmth, reverence, and craft of archival filmmaking brought into the modern tactile screen. The brand personality is intimate, poetic, authoritative, and deeply nostalgic without feeling dated. It honors real human memory by borrowing cues from vintage film reels, velvet screening rooms, and warm gallery lighting.

The visual direction merges **Cinematic Warmth** with **Modern Tactile Minimalism**:
- **Atmospheric & Somber**: Grounded in deep charcoal-umber tones rather than sterile cold blacks, evoking an intimate, dimly lit editing bay.
- **Luminous Highlights**: Soft golden glow reminiscent of late-afternoon tungsten light and nitrate film projection bulbs.
- **Editorial Archival Sensibility**: High-contrast, elegant serif typography that evokes art house cinema titles, framed within crisp, low-glare interfaces.
- **Tactile Softness**: Subtle semi-translucent overlays and delicate warm hair-line borders that feel like deckled archival paper and framed film cels.

## Colors

The palette is engineered for a rich dark mode experience that retains natural warmth, readability, and accessible contrast:

- **Primary (#E5A93C)**: Golden Tungsten. Used for key call-to-actions, active state outlines, highlighted timelines, and progress indicators.
- **Secondary (#F3C362)**: Gilded Amber. Reserved for hover states, subtle ambient glows, and badge highlights.
- **Tertiary (#D49024)**: Burnished Ochre. Applied to secondary interactive surfaces, active borders, and focus rings.
- **Neutral Canvas (#1A1412)**: Deep Umber Base. A rich, warm black that mitigates eye fatigue while establishing cinematic depth.
- **Neutral Elevated (#241B18)**: Lifted Umber. Applied to cards, bottom sheets, navigation bars, and modals.
- **Text & High Contrast Accents**:
  - `Text Primary`: Off-White Vellum (`#F9F5F0`) delivering >11:1 contrast against `#1A1412` for WCAG AAA legibility.
  - `Text Secondary`: Warm Parchment (`#EDE4D8`) for supporting descriptions and secondary headers.
  - `Text Muted`: Dust Cream (`#C4B5A5`) for metadata, timestamps, and placeholder labels.
  - `Borders & Overlays`: Muted Amber Stroke (`rgba(229, 169, 60, 0.16)`) and Dark Umber Divider (`rgba(249, 245, 240, 0.08)`).

## Typography

The typographic tension pairs the classical, evocative flourishes of **Playfair Display** with the ergonomic, highly legible architecture of **Plus Jakarta Sans**.

- **Editorial Serifs (`Playfair Display`)**: Used deliberately for narrative moments—film titles, emotional milestones, stage headers, and project naming. It anchors the user in storytelling.
- **Modern Sans (`Plus Jakarta Sans`)**: Neutral, open aperture, high x-height sans-serif configured for timeline scrubbers, metadata displays, tooltips, body instructions, and settings controls.
- **Mobile Readability Rule**: Serifs under 20px default back to `Plus Jakarta Sans` medium or semibold to guarantee crisp scanning on mobile displays and prevent thin serifs from dissolving against dark canvases.

## Layout & Spacing

The design system utilizes a mobile-first fluid grid optimized for thumb interactions and widescreen editing suites:

- **Mobile (< 768px)**: 4-column layout with `margin: 1rem` (16px) and `gutter: 1rem` (16px). Key controls are positioned in bottom navigation docks, floating action sheets, and thumb-friendly bottom-anchored sheets.
- **Tablet (768px – 1024px)**: 8-column layout with `margin: 1.5rem` (24px). Accommodates dual-pane views (photo bin on the left, film preview and script on the right).
- **Desktop (≥ 1025px)**: 12-column layout capped at a maximum width of `1380px` centered with `margin: 2.5rem` (40px) and `gutter-desktop: 1.5rem` (24px). Three-pane studio interface (Assets, Video Canvas, Narrative Timeline).
- **Spacing Rhythm**: Built on an 8pt base grid with a 4pt subgrid (`space-xs: 4px`, `space-sm: 8px`, `space-md: 16px`, `space-lg: 24px`, `space-xl: 36px`, `space-2xl: 56px`).

## Elevation & Depth

Rather than conventional drop shadows that can muddy dark backgrounds, visual hierarchy relies on **Tonal Layering**, **Warm Ambient Illumination**, and **Hairline Amber Borders**:

- **Level 0 (Base Canvas)**: `#1A1412` flat backdrop.
- **Level 1 (Cards & Media Panels)**: Surface color `#241B18`, bounded by a delicate `1px solid rgba(229, 169, 60, 0.12)`.
- **Level 2 (Modals, Overlays, and Drawers)**: Surface `#2D221E`, `1px solid rgba(243, 195, 98, 0.22)`, accompanied by a warm diffused shadow: `0 16px 36px -8px rgba(10, 7, 6, 0.75), 0 0 24px -4px rgba(229, 169, 60, 0.08)`.
- **Level 3 (Interactive Glowing Elements & Floating Playheads)**: `box-shadow: 0 4px 20px rgba(229, 169, 60, 0.35)` to convey luminescence and focus.
- **Cinematic Overlays**: Vignette radial gradients (`radial-gradient(circle at center, transparent 40%, rgba(26, 20, 18, 0.6) 100%)`) applied subtly across background video previews and hero media containers.

## Shapes

The interface embraces a tailored **Rounded** aesthetic (`roundedness: 2`):

- **Default UI Components (Buttons, Input Fields, Checkboxes)**: `0.5rem` (8px) radius. Balanced, polished, and structured.
- **Cards, Preview Containers, and Dialogs (`rounded-lg`)**: `1rem` (16px) radius, framing media reminiscent of mounted film slides and photo mounts.
- **Sheets, Drawers, and Large Panels (`rounded-xl`)**: `1.5rem` (24px) radius.
- **Chips, Badges, Scrubber Handles, and Pills**: Fully rounded pill shapes (`9999px`) to contrast cleanly with structured rectangular media viewports.

## Components

### Buttons & Interactive Touch Targets
- **Sizing & Accessibility**: All primary interactive elements meet or exceed a **minimum 48×48px tap target** on touch viewports.
- **Primary Button**: Solid Tungsten Gold (`#E5A93C`) fill with dark umber text (`#1A1412`, weight 600). Hover transitions to `#F3C362` with a `0 0 16px rgba(229, 169, 60, 0.4)` glow.
- **Secondary Button**: Outlined button with `1px solid rgba(229, 169, 60, 0.35)`, transparent background, and `#F9F5F0` text. Hover adds `rgba(229, 169, 60, 0.08)` fill.
- **Focus States**: High-contrast double-ring focus indicator (`2px solid #F3C362` offset by `2px solid #1A1412`), ensuring strict WCAG 2.2 AA non-text contrast compliance.

### Cinematic Cards & Story Frames
- **Container**: Elevated surface (`#241B18`) with `12px` or `16px` border-radius.
- **Border**: `1px solid rgba(229, 169, 60, 0.14)`. Hover lifts border to `rgba(243, 195, 98, 0.4)` and gently scales the inner photo or video thumbnail (1.02 scale over 300ms ease-out).
- **Aspect Ratios**: Native film ratios (`16:9`, `4:3`, `1:1`, and mobile reel `9:16`) framed with subtle inner vignette shadows.

### Chips, Pills & Status Badges
- **Pill Badges**: `9999px` border radius, padding `4px 12px`.
- **Styling**: `rgba(229, 169, 60, 0.12)` background, `1px solid rgba(229, 169, 60, 0.25)` border, text in `#F3C362` (`label-sm`).
- **Interactive Filter Chips**: Tap to toggle. Selected state fills with `#E5A93C` text in `#1A1412`.

### Inputs & Form Fields
- **Container**: `#1E1715` background with `1px solid rgba(249, 245, 240, 0.16)` border. Height 48px to 52px.
- **Typography**: Text `#F9F5F0`, placeholder `#C4B5A5`.
- **Focus State**: Border transitions to `#E5A93C` with an ambient glow (`box-shadow: 0 0 0 3px rgba(229, 169, 60, 0.2)`).

### Checkboxes & Radio Buttons
- **Touch Target**: Sized at 48×48px hit areas with a 20×20px visual control centered inside.
- **State**: Checked state renders `#E5A93C` fill with `#1A1412` checkmark icon or radio dot. Unchecked state uses `#241B18` fill with a `1.5px solid rgba(249, 245, 240, 0.3)` border.

### Timeline & Scrubber (Domain-Specific)
- **Track**: `4px` tall bar with `#241B18` background and `rgba(249, 245, 240, 0.1)` border.
- **Active Progress**: Warm gold fill `#E5A93C` with a soft `rgba(229, 169, 60, 0.5)` trailing aura.
- **Playhead Needle**: Crisp vertical bar with a teardrop or rounded thumb indicator (48px touch target, 16px visual width) styled in `#F9F5F0` with a subtle golden halo.