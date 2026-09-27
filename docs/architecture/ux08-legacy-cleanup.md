# UX-08 Legacy-/CSS-Cleanup: Ergebnis und Ownership

Stand: 2026-09-24
Ticket: https://github.com/Serph91P/StreamVault/issues/828

## Ausgangslage

UX-08 wurde auf dem eingefrorenen UX-07-Kandidaten aufgebaut. Der Overlay-Eingang umfasst 113 manifestierte Pfade; alle 113 Pfade wurden vor der Arbeit byte- und SHA256-geprüft. Der Basis-HEAD ist `14bff396a2055e45d679cc1f900bdc17990e7cb3` auf `develop`.

Der UX-07-Kandidat enthält bereits den zuvor freigegebenen, nachgewiesenen Frontend-Cleanup. Eine erneute Löschung dieser Änderungen wäre keine Verbesserung, sondern würde den akzeptierten Vorgänger regressieren. Im UX-08-Arbeitsbaum wurde deshalb kein weiterer unzureichend belegter Dead-Code- oder Selector-Kandidat entfernt.

## Selector- und Style-Ownership

- `src/styles/_variables.scss` besitzt die kanonischen App-Tokens, Theme-Overrides und ausdrücklich markierten Kompatibilitätsaliasse.
- `src/styles/_glass-system.scss` besitzt ausschließlich Glass-Tokens, Glass-Mixins und Glass-Klassen.
- `src/styles/_components.scss` besitzt die verbleibenden globalen Legacy-Komponentenklassen während der Vue-Primitiven-Migration.
- `src/styles/main.scss` besitzt Importreihenfolge, Reset, Dokument-Basisregeln und globale Elementdefaults.
- `src/styles/_utilities.scss` besitzt Utility-Klassen. Die frühere `.glass-card`-Utility ist im Eingang bereits entfernt; sie kollidierte mit dem `GlassCard.vue`-Root.
- Vue-Komponenten besitzen ihre komponentenspezifischen Selektoren; neue globale Aliasse werden nicht eingeführt.

## Nachweisgrenze

Vor einer weiteren Löschung müssen statische Template-/Script-Verwendungen, dynamische Klassen, Theme- und Responsive-Pfade sowie die zugehörigen Tests geprüft werden. Ein leerer Grep oder ein Dateiname ist kein Löschbeleg. Die vorhandene `frontend-inventory.json` bleibt deshalb die Referenz für die nächste separat reviewbare Cleanup-Änderung.

## Compiler-Evaluation

`npm ci` installierte 712 Pakete ohne Vulnerabilities. Das Projekt verwendet weiterhin `sass` `^1.104.1`. `sass-embedded` wird in UX-08 nicht übernommen: Es liegt kein belastbarer nativer Windows-/macOS-Nachweis vor; Linux-Ausführung oder Plattform-Mocking wäre dafür unzureichend. Die Entscheidung ist reversibel und vermeidet eine nicht belegte Lockfile-/Installationsänderung.

## Reproduzierbarer Ausgangsstand

Mit `VITE_USE_MOCK_DATA=true npm run build` wurde der Overlay-Kandidat erfolgreich gebaut. Der Build erzeugte 87 Precache-Einträge; der HLS-Worker wurde als eigener Chunk ausgegeben. Die Build-Warnung zu großen Chunks bleibt als bestehender Befund erhalten und wird nicht durch erfundene Splitting- oder Warning-Overrides kaschiert.

## Gebundener Vorher-/Nachher-Vergleich

Die Messung wurde nach dem letzten `npm ci` und Mock-Build am finalen Kandidaten wiederholt. Referenz ist die identische UX-07-Run62-Fixture; Rohdaten liegen in `streamvault-ux08-evidence/npm_run_test_output-budgets.log`, der Build-/Precache-Nachweis in `vite_build.log` und `npm_run_test_precache-integrity.log`.

| Messgröße | UX-07-Referenz | UX-08 final | Delta |
|---|---:|---:|---:|
| Application JS | 1,191,723 B | 1,191,723 B | 0 B |
| Application JS gzip | 380,361 B | 380,361 B | 0 B |
| CSS | 812,802 B | 812,802 B | 0 B |
| CSS gzip | 123,572 B | 123,572 B | 0 B |
| HLS-Worker | 116,764 B / gzip 40,615 B | 116,764 B / gzip 40,615 B | 0 B |
| Precache | 87 Einträge | 87 Einträge | 0 |

URLs, Revisionen und der Loading-Graph wurden im Desktop/Mobile-Lauf erneut aufgezeichnet; die Messung bestätigt denselben HLS-Worker, dieselben 87 Precache-Einträge und unveränderte Initial-/Playback-Pfade. Die unveränderten UX-03-Budgets bleiben verbindlich.

## Gate-Evidenz Run65

Die vollständigen Rohlogs liegen unter `/opt/data/agent/kanban/workspaces/streamvault-ux08-evidence/`: `npm_ci.log`, `vite_build.log`, `playwright_desktop_mobile.log`, `foundation_browser.log` und `foundation_capture_integration.log` sowie die vorhandenen Unit-/Foundation-/Token-/Responsive-/Output-/Precache-/Budget-/Loading-Logs. `npm ci`, Mock-Build, Desktop/Mobile-Playwright und beide serialisierten Foundation-Browser-Gates endeten mit Exitcode 0; der Playwright-Lauf meldet 106 passed und 32 konfigurierte Skips. Das Inventar wurde nach dem Build erneut auf den eingefrorenen Manifest-Hash `2b1f09c4d9abe78df10c421d5afb165e17af3c416ef8c918498dbb466b7d723a` restauriert und geprüft.
