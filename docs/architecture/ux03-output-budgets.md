# UX-03 blocking frontend output budgets

Baseline was measured before UX-03 source changes from `develop@14bff396a2055e45d679cc1f900bdc17990e7cb3` after `npm ci` and a mock-data production build. Candidate measurement uses the identical Node script and build mode. Raw and Node zlib gzip byte categories are deliberate; Vite's rounded console values are not used as assertions.

| Category | Baseline | Blocking maximum | UX-03 candidate |
| --- | ---: | ---: | ---: |
| JavaScript raw | 1,192,437 | 1,196,533 | 1,192,502 |
| JavaScript gzip | 376,335 | 380,431 | 376,370 |
| CSS raw | 812,601 | 828,985 | 820,150 |
| CSS gzip | 119,525 | 123,621 | 120,804 |
| Total build bytes | 2,729,765 | 2,754,341 | 2,737,379 |
| Precache entries | 91 | 91 | 91 |
| Largest JS file | 590,144 | 594,240 | 590,144 |
| Largest CSS file | 294,607 | 310,991 | 301,290 |

The margins were fixed from the untouched baseline before candidate measurement: 4 KiB for JS/gzip/largest JS, 16 KiB for CSS/largest CSS, and 24 KiB total; precache may not grow. They accommodate only this bounded generated foundation and do not waive the existing 590 KiB HLS-bearing chunk or Sass/PWA cleanup. Those measured debts remain for UX-06/UX-08.

`npm run test:output-budgets` is blocking. Synthetic fixture tests prove that CSS and precache regressions exit non-zero. `npm run test:build-output` independently performs two clean builds, rejects `dist/src`, and compares complete SHA-256 manifests.

Evidence JSON is delivered as `baseline-build.json` and `candidate-build.json` with Node v22.23.2, Vite 8.3.0 and the measurement method recorded in each file.
