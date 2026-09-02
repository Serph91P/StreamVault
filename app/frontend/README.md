# streamvault-frontend

StreamVault's Vue 3 frontend uses Vite for local development and production builds.

## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Setup

```sh
npm ci
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

## Verification

Run these commands from `app/frontend` before opening a frontend change:

```sh
npm run type-check
npm run lint:check
npm run lint:tokens
npm run test:unit
npm run build
npm run test:build-output
npx playwright install --with-deps chromium
npx playwright test
```

`type-check` runs non-emitting Vue and Node TypeScript checks. `lint:check` is read-only and caps the current lint baseline, while `lint` remains the developer auto-fix command. `build` runs type checks before Vite, and `test:build-output` verifies two clean mock-mode builds have no emitted source tree and matching file-hash manifests.

The Playwright suite serves a mock-mode production build and tests desktop and mobile viewports without a backend.
