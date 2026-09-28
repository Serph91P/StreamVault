export async function expectGateFailure(run: () => Promise<unknown> | unknown, expectedMessage: RegExp): Promise<void> {
  let failure: unknown
  try {
    await run()
  } catch (error) {
    failure = error
  }
  if (!failure) throw new Error('negative fixture unexpectedly passed its gate')
  const message = failure instanceof Error ? failure.message : String(failure)
  if (!expectedMessage.test(message)) throw new Error(`negative fixture failed for the wrong reason: ${message}`)
}
