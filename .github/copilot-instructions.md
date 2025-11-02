# Copilot Instructions for StreamVault

## Commit Message Convention

**IMPORTANT**: This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic semantic versioning.

### Commit Message Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Commit Types and Version Impact

When generating commit messages, **ALWAYS** use these prefixes:

#### Minor Version Bump (1.0.x → 1.1.0) - Use for:
- `feat:` - New features
- `feature:` - New features (alternative)
- `add:` - Adding new functionality
- `refactor:` - Code refactoring/restructuring
- `perf:` - Performance improvements

#### Patch Version Bump (1.0.0 → 1.0.1) - Use for:
- `fix:` - Bug fixes
- `bugfix:` - Bug fixes (alternative)
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks, dependency updates
- `style:` - Code formatting, no logic changes
- `test:` - Adding or updating tests
- `ci:` - CI/CD pipeline changes

#### Major Version Bump (1.x.x → 2.0.0) - Use for:
- `BREAKING CHANGE:` in commit body
- `<type>!:` - Any type with ! suffix (e.g., `feat!:`)

### Examples for Common Scenarios

#### Adding a new feature:
```
feat: add automatic YouTube recording support

- Implemented YouTube API integration
- Added quality selection for YouTube streams
- Updated UI with YouTube platform option
```

#### Improving code quality:
```
refactor: optimize database queries and fix memory leaks

- Fixed 31 bare except blocks with specific exception handling
- Optimized 18 N+1 queries using joinedload()
- Replaced unbounded dicts with TTLCache to prevent memory leaks
- Centralized 30+ magic numbers in configuration

New Dependencies: cachetools==5.5.0
```

#### Fixing a bug:
```
fix: resolve memory leak in notification manager

The notification debounce dictionary was growing unboundedly.
Replaced with TTLCache with 5-minute expiration.
```

#### Updating dependencies:
```
chore: update Python dependencies

- Updated FastAPI to 0.110.0
- Updated SQLAlchemy to 2.0.27
- Updated all security patches
```

#### Breaking changes:
```
feat!: migrate to PostgreSQL 16

BREAKING CHANGE: Minimum PostgreSQL version is now 16.0
Users must upgrade their database before updating StreamVault.

Migration guide: docs/upgrade-pg16.md
```

### Scopes (Optional but Recommended)

Use scopes to indicate which part of the codebase is affected:

```
feat(api): add new recording endpoints
fix(ui): resolve dashboard loading issue
perf(db): add database indexes for streams table
docs(docker): update compose examples
chore(deps): update Python dependencies
```

### Rules for Copilot

1. **ALWAYS** analyze the changes first to determine the correct type
2. **PREFER** `refactor:` over `fix:` for code quality improvements
3. **USE** `feat:` for any new functionality, not just user-facing features
4. **USE** multiline commits for complex changes (body + footer)
5. **MENTION** breaking changes explicitly with `BREAKING CHANGE:`
6. **LIST** new dependencies in the commit body
7. **REFERENCE** issue numbers with `Fixes #123` or `Closes #456`

### Common Patterns in StreamVault

#### Code Quality Improvements → `refactor:`
```
refactor: improve exception handling in recording service

- Replaced bare except with specific exception types
- Added proper error logging with context
- Improved error recovery logic
```

#### Database Optimizations → `perf:`
```
perf: optimize stream queries with eager loading

- Added joinedload() for Stream.streamer relationships
- Reduced N+1 queries from 30 to 1
- 50-70% faster API response times
```

#### Docker/Infrastructure → `chore:` or `ci:`
```
chore(docker): optimize image build process

- Multi-stage build reduces image size by 40%
- Fixed Windows CRLF line ending issues
- Improved layer caching
```

#### Bug Fixes → `fix:`
```
fix: resolve recording status persistence issue

Recording states were not properly restored after restart.
Added state persistence service with graceful recovery.

Fixes #234
```

### What NOT to do

❌ **Bad:**
```
update stuff
changes
wip
fixed things
```

✅ **Good:**
```
feat: add thumbnail generation service
fix: resolve memory leak in event handler
refactor: extract configuration constants
chore: update Docker base image
```

## Code Style Preferences

- Use type hints for all function parameters and return types
- Prefer `joinedload()` for relationships to avoid N+1 queries
- Use specific exception types, never bare `except:`
- Put magic numbers in `app/config/constants.py`
- Use `TTLCache` for caches that could grow unboundedly
- Add comprehensive docstrings for public APIs
- Follow Python PEP 8 style guide

## Architecture Patterns

- Services in `app/services/` should be stateless where possible
- Use dependency injection for database sessions
- WebSocket updates for real-time UI changes
- Background tasks use queue system in `app/services/queues/`
- All database queries should use eager loading for relationships
- Use structured logging with context

## Testing

- Write unit tests for business logic
- Integration tests for API endpoints
- Use fixtures for database setup
- Mock external APIs (Twitch, etc.)

## Frontend Design System & UI Guidelines

### Mobile-First Approach

**IMPORTANT**: StreamVault is a PWA (Progressive Web App). Always design and develop mobile-first:

1. **Start with mobile breakpoints** (320px-640px)
2. **Progressively enhance** for tablets (768px-1023px) and desktop (1024px+)
3. **Touch-friendly targets**: Minimum 44x44px for interactive elements
4. **Thumb-reachable navigation**: Bottom navigation for primary mobile actions
5. **Avoid horizontal scroll**: Use `overflow-x: hidden` on container elements

### Reusable Component Styles

#### Buttons (`.btn` in `_components.scss`)

**NEVER** override button styles in component-specific `<style>` blocks. Use global classes:

```html
<!-- ✅ CORRECT: Use global classes -->
<button class="btn btn-primary">Save</button>
<button class="btn btn-danger">Delete</button>
<button class="btn btn-success">Start</button>
<button class="btn btn-secondary">Cancel</button>

<!-- ❌ WRONG: Don't add inline button styles -->
<style>
.my-button {
  border-radius: 8px; /* Already in .btn */
  padding: 8px 16px; /* Already in .btn */
}
</style>
```

**Available button variants:**
- `.btn-primary` - Primary actions (Vue green #42b883)
- `.btn-secondary` - Secondary actions (accent purple)
- `.btn-success` - Positive actions (green #2ed573)
- `.btn-danger` / `.btn-delete` - Destructive actions (red #ff4757)
- `.btn-warning` - Warning actions (orange #ffa502)
- `.btn-info` - Informational actions (blue #70a1ff)

All buttons have consistent:
- `border-radius: 8px` (from `$border-radius` variable)
- Hover effects (translateY, box-shadow)
- Disabled states (opacity: 0.7)
- Ripple effect via mixin

#### Status Borders (`.status-border` in `_components.scss`)

Use for left-accent indicators on cards, notifications, settings sections:

```html
<!-- ✅ CORRECT: Use global status-border classes -->
<div class="notification status-border status-border-success">Success!</div>
<div class="settings-section status-border status-border-primary">...</div>
<div class="alert status-border status-border-error">Error occurred</div>

<!-- ❌ WRONG: Don't add inline border-left styles -->
<style>
.my-card {
  border-left: 3px solid #42b883; /* Use .status-border-primary instead */
}
</style>
```

**Available status border variants:**
- `.status-border-primary` - Primary accent (Vue green)
- `.status-border-success` - Success states (green)
- `.status-border-warning` - Warning states (orange)
- `.status-border-danger` / `.status-border-error` - Error states (red)
- `.status-border-info` - Information (blue)
- `.status-border-secondary` - Neutral (gray)

#### Modals & Overlays

**Consistent modal behavior:**

```html
<!-- ✅ CORRECT: Backdrop click to close -->
<div class="modal-overlay" @click.self="closeModal">
  <div class="modal">
    <!-- Modal content -->
  </div>
</div>

<style>
.modal-overlay {
  position: fixed; /* Not absolute - stays in viewport */
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px); /* Visual separation */
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
  overflow-y: auto; /* Allow scroll if modal is tall */
}

.modal {
  margin: auto; /* Centers modal even when scrolled */
  animation: slideUp 0.3s ease-out; /* Smooth appearance */
}
</style>
```

**Modal rules:**
1. `position: fixed` - not absolute (stays in viewport when scrolled)
2. `@click.self` on overlay - close on backdrop click
3. `backdrop-filter: blur(4px)` - visual separation from background
4. `overflow-y: auto` on overlay - allow scroll for tall modals
5. `margin: auto` on modal - centers regardless of scroll position

#### Tables → Mobile Cards

**NEVER** use wide tables without mobile-responsive card fallback:

```scss
/* ✅ CORRECT: Responsive table pattern */
.data-table {
  @media (max-width: 480px) {
    table, thead, tbody, th, td, tr {
      display: block;
    }
    
    thead tr {
      position: absolute;
      top: -9999px;
      left: -9999px;
    }
    
    tr {
      margin-bottom: 16px;
      border: 1px solid var(--border-color);
      border-radius: 8px;
    }
    
    td {
      position: relative;
      padding-left: 110px; /* Space for data labels */
      
      &:before {
        content: attr(data-label);
        position: absolute;
        left: 12px;
        font-weight: 600;
        color: var(--text-secondary);
      }
    }
  }
}
```

```html
<!-- ✅ CORRECT: Add data-label for mobile cards -->
<td data-label="Streamer">{{ streamer.name }}</td>
<td data-label="Status">{{ streamer.status }}</td>
```

#### Grid Layouts - Desktop Optimization

**Use responsive grid with proper breakpoints:**

```scss
/* ✅ CORRECT: Progressive enhancement for desktop */
.content-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  
  @media (min-width: 768px) {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }
  
  @media (min-width: 1024px) {
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: 24px;
  }
  
  @media (min-width: 1440px) {
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 28px;
  }
}

/* ❌ WRONG: Fixed 2-column on all screens */
.bad-grid {
  grid-template-columns: repeat(2, 1fr); /* Wastes desktop space */
}
```

### SCSS Variables & Mixins

**ALWAYS use variables from `_variables.scss`:**

```scss
/* ✅ CORRECT: Use variables */
.component {
  background: v.$background-card;
  color: v.$text-primary;
  border-radius: v.$border-radius;
  padding: v.$spacing-md v.$spacing-lg;
  box-shadow: v.$shadow-md;
}

/* ❌ WRONG: Hard-coded values */
.bad-component {
  background: #1f1f23; /* Use v.$background-card */
  color: #f1f1f3; /* Use v.$text-primary */
  border-radius: 8px; /* Use v.$border-radius */
  padding: 16px 24px; /* Use v.$spacing-md v.$spacing-lg */
}
```

**Available design tokens:**
- Colors: `$primary-color`, `$success-color`, `$danger-color`, `$warning-color`, `$info-color`
- Backgrounds: `$background-dark`, `$background-darker`, `$background-card`
- Text: `$text-primary`, `$text-secondary`
- Spacing: `$spacing-xs`, `$spacing-sm`, `$spacing-md`, `$spacing-lg`, `$spacing-xl`, `$spacing-xxl`
- Shadows: `$shadow-sm`, `$shadow-md`, `$shadow-lg`
- Border radius: `$border-radius-sm`, `$border-radius`, `$border-radius-lg`, `$border-radius-xl`
- Transitions: `$transition-fast`, `$transition-base`, `$transition-slow`
- Vue animations: `$vue-ease`, `$vue-ease-out`, `$vue-ease-in`

### Consistency Rules

1. **No inline styles in `<style scoped>` that duplicate global styles**
2. **Use existing utility classes before creating new ones**
3. **Check `_components.scss`, `_layout.scss`, `_variables.scss` first**
4. **Mobile breakpoint: 480px (cards), 768px (tablet), 1024px (desktop)**
5. **All interactive elements: min-height 44px on mobile**
6. **Use `@media (min-width: X)` for mobile-first progressive enhancement**

### Component Development Checklist

Before creating a new component, ask:

- [ ] Can I use existing `.btn` classes instead of custom button styles?
- [ ] Can I use `.status-border-*` for accent indicators?
- [ ] Does this table have mobile card layout (`data-label` attributes)?
- [ ] Are modals using `position: fixed` with backdrop blur?
- [ ] Is the grid responsive with proper `minmax()` breakpoints?
- [ ] Am I using SCSS variables instead of hard-coded colors/spacing?
- [ ] Did I test on mobile viewport (320px-640px)?
- [ ] Are touch targets at least 44x44px?

---

**Remember**: The commit type determines the version bump! Choose wisely:
- New functionality? → `feat:` → Minor bump (1.0 → 1.1)
- Code improvement? → `refactor:` → Minor bump (1.0 → 1.1)
- Bug fix? → `fix:` → Patch bump (1.0.0 → 1.0.1)
