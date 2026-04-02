# Frontend Changes

## Code Quality Tooling

### What was added

#### `frontend/package.json`
Introduces a minimal npm project for the frontend with Prettier as the sole dev dependency.
Two scripts are defined:
- `format` — rewrites all `.js`, `.css`, and `.html` files in-place to match Prettier's style.
- `format:check` — exits non-zero if any file differs from Prettier's output (useful in CI).

#### `frontend/.prettierrc`
Prettier configuration that codifies the style already present in the codebase:
- 4-space indentation, no tabs
- 100-character print width
- Single quotes for JS strings
- Semicolons required
- ES5 trailing commas
- LF line endings

#### `scripts/check-frontend.sh`
A shell script at the repo root that wraps the Prettier workflow:
- `./scripts/check-frontend.sh` — checks formatting and exits with an error if anything is out of style.
- `./scripts/check-frontend.sh --fix` — auto-formats all frontend files.
- Auto-installs `node_modules` on first run if needed.

### Formatting fixes applied to existing files

#### `frontend/script.js`
- Removed stray double-blank lines (between `setupEventListeners()` block and `// Chat Functions` section).
- Ensured consistent single-blank-line separation between logical sections.

### How to use

```bash
# Install Prettier once
cd frontend && npm install

# Check formatting (CI-safe, no writes)
./scripts/check-frontend.sh

# Auto-fix all frontend files
./scripts/check-frontend.sh --fix

# Or run directly from the frontend directory
cd frontend
npm run format:check   # check only
npm run format         # auto-fix
```

## Features Implemented

### 1. Theme Toggle Button (Dark/Light Mode)

**Files modified:** `frontend/index.html`, `frontend/style.css`, `frontend/script.js`

#### HTML (`index.html`)
- Added a `<button id="themeToggle">` element fixed to the top-right of the viewport (outside `.container`, so it always floats above the layout).
- Button contains two inline SVGs: a **sun icon** (shown in light mode) and a **moon icon** (shown in dark mode).
- Includes `aria-label` and `title` attributes for accessibility.
- Both SVG icons have `aria-hidden="true"` since the button's `aria-label` describes the action.

#### CSS (`style.css`)
- **Dark mode variables** (`:root`): added `--theme-toggle-bg`, `--theme-toggle-hover`, `--theme-toggle-border` to match the existing dark surface palette.
- **Light mode variables** (`[data-theme="light"]`): overrides all color tokens for a clean light variant:
  - `--background: #f8fafc` (off-white page background)
  - `--surface: #ffffff` (white cards/sidebar)
  - `--surface-hover: #f1f5f9`
  - `--text-primary: #0f172a` (near-black, high contrast)
  - `--text-secondary: #64748b`
  - `--border-color: #e2e8f0`
  - `--focus-ring: rgba(37, 99, 235, 0.15)`
  - `--welcome-bg: #eff6ff`, `--welcome-border: #93c5fd`
  - Lighter shadow values for the lighter background
- **Toggle button styles** (`.theme-toggle`): fixed position, circular (42×42 px), border + background from CSS vars, `transform: scale()` on hover/active for tactile feedback, focus ring using `--focus-ring`.
- **Icon switching**: `.icon-sun` hidden by default (dark mode); `.icon-moon` shown. `[data-theme="light"]` reverses this.
- **Smooth transitions**: `background-color`, `color`, and `border-color` transitioned at `0.3s ease` on body, sidebar, chat container, inputs, buttons, and message elements.
- **Light mode hardcoded-color overrides**: source pill links (`#1d4ed8` instead of `#93c5fd`), `code` blocks, `pre` blocks, and welcome message shadow adjusted for light backgrounds.

#### JavaScript (`script.js`)
- Added `initThemeToggle()` called inside the `DOMContentLoaded` handler.
- On load: reads `localStorage.getItem('theme')`; if `'light'`, sets `data-theme="light"` on `document.documentElement` so the preference survives page refreshes.
- On button click: checks current theme, toggles `data-theme` attribute on `<html>`, and persists the new value to `localStorage`.

#### Accessibility
- Button is keyboard-navigable (standard `<button>` element, reachable via Tab).
- Focus ring visible via `box-shadow: 0 0 0 3px var(--focus-ring)`.
- `aria-label="Toggle light/dark mode"` announces intent to screen readers.
- Color contrast in light mode: `--text-primary` (`#0f172a`) on `--background` (`#f8fafc`) exceeds WCAG AA ratio.
