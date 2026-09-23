export type BaselineCollectionStage = 'viewport' | 'navigation' | 'readiness' | 'keyboard' | 'accessibility-tree' | 'axe' | 'screenshot'

export function formatBaselineStageFailure(stage: BaselineCollectionStage, error: unknown): string {
  return `${stage}: ${error instanceof Error ? error.message : String(error)}`
}
