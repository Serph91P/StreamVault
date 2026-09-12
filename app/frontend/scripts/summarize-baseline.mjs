import { readFile } from 'node:fs/promises'

const [reportPath] = process.argv.slice(2)
if (!reportPath) throw new Error('Usage: node scripts/summarize-baseline.mjs <viewport-baseline.json>')

const report = JSON.parse(await readFile(reportPath, 'utf8'))
const observations = report.observations ?? []
const violationCounts = {}
for (const violation of observations.flatMap(observation => observation.violations ?? [])) {
  violationCounts[violation.kind] = (violationCounts[violation.kind] ?? 0) + 1
}
const violations = Object.fromEntries(Object.entries(violationCounts).sort(([left], [right]) => left.localeCompare(right)))

const summary = {
  schemaVersion: 1,
  observations: observations.length,
  distinctRoutes: [...new Set(observations.map(observation => observation.route))].length,
  collectionErrorObservations: observations.filter(observation => observation.collectionErrors?.length).length,
  overflowObservations: observations.filter(observation => typeof observation.documentOverflow === 'number' && observation.documentOverflow !== 0).length,
  violationCounts: violations,
  seriousOrCriticalAxeViolations: observations.reduce((total, observation) => total + (observation.seriousOrCriticalAxeViolations?.length ?? 0), 0),
}

console.log(JSON.stringify(summary, null, 2))
