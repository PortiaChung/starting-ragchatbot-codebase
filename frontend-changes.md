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
