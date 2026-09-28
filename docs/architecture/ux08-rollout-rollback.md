# UX-08 Rollout und Rollback

Ticket: https://github.com/Serph91P/StreamVault/issues/828
Basis: `develop` @ `14bff396a2055e45d679cc1f900bdc17990e7cb3`

## Rollout-Voraussetzungen

1. Unabhängige Review des vollständigen UX-08-Deltas einschließlich untracked Dateien.
2. Alle verpflichtenden Frontend-Gates müssen im identischen Setup grün sein: Typprüfung, Lint, Unit-, Foundation-, Token-, Responsive-, Build-Output-, Precache-, Budget-, Loading- und Desktop/Mobile-Playwright-Gates.
3. CSS-/JS-/gzip-/Precache- und Loading-Messungen müssen an derselben Fixture vergleichbar sein. HLS-Worker und Precache werden separat betrachtet.
4. Die zwei bekannten serious Axe-`incomplete`-Befunde (`h1` und `.active.filter-tab > .tab-badge`) bleiben ausdrücklich Restbefunde und sind keine Accessibility-Freigabe.
5. Native Windows-/macOS-Evidenz für `sass-embedded` liegt nicht vor; daher bleibt `sass` aktiv. Es gibt keinen Compiler-Rollout.

UX-08 führt in dieser Phase keinen Deploy, Provider-Canary oder Produktionszugriff aus.

## Beobachtung nach Freigabe

Verglichen werden mindestens: initialer JS/CSS-Emit, gzip-Größen, HLS-Worker, Anzahl und URLs der Precache-Einträge, Loading-Graph sowie die bestehenden Budgets. Zusätzlich werden Navigation, Login, Onboarding, Settings und responsive Shell auf unveränderte Glass-/Token-Ownership geprüft.

## Rollback

Bei einer Regression wird der vollständige UX-08-Delta-Satz als Einheit zurückgenommen; einzelne Produktdateien werden nicht selektiv aus dem akzeptierten UX-07-Overlay herauskopiert. Danach wird der letzte akzeptierte UX-07-Kandidat wiederhergestellt und dieselben Gates erneut ausgeführt. Ein Rollback gilt erst als abgeschlossen, wenn die Vergleichsfixture, Precache-Integrität, Budgets und die Readiness-Negativkontrollen wieder den akzeptierten Ergebnissen entsprechen.

## Tatsächlicher Run65-Nachweis

Auf dem finalen Kandidaten wurden `npm ci`, `VITE_USE_MOCK_DATA=true npm run build`, `./node_modules/.bin/playwright test --project=desktop --project=mobile`, `npm run test:foundation-browser` und anschließend serialisiert `npm run test:foundation-capture-integration` ausgeführt. Alle fünf Läufe endeten mit Exitcode 0; Playwright meldete 106 bestandene Tests und 32 konfigurierte Skips. Die Rohlogs sind unter `/opt/data/agent/kanban/workspaces/streamvault-ux08-evidence/` dauerhaft abgelegt. Vor der Übergabe wurde `docs/architecture/frontend-inventory.json` nach dem Build aus dem eingefrorenen Overlay restauriert und mit SHA256 `2b1f09c4d9abe78df10c421d5afb165e17af3c416ef8c918498dbb466b7d723a` geprüft; damit bleibt das UX-07-Overlay 113/113 bytegleich.

Rollback-Trigger sind insbesondere neue Funktion-/Navigation-Regressionen, zusätzliche serious/critical Axe-Verstöße, Budgetüberschreitungen, veränderte Precache-Revisionen ohne erklärten Grund, HLS-Worker-Verschlechterung oder fehlende Plattform-/Installationsbelege für einen Compilerwechsel.
