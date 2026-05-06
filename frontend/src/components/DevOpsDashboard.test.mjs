import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./DevOpsDashboard.jsx', import.meta.url), 'utf8')

test('DevOpsDashboard guards async fetch state commits after unmount', () => {
  const awaitIndex = source.indexOf('const results = await Promise.allSettled')
  const guardIndex = source.indexOf('if (!mountedRef.current)', awaitIndex)
  const firstStateCommitIndex = source.indexOf('setDashboard', awaitIndex)

  assert.ok(awaitIndex > -1, 'dashboard fetch should await Promise.allSettled')
  assert.ok(guardIndex > awaitIndex, 'mountedRef guard must appear after awaited fetch')
  assert.ok(guardIndex < firstStateCommitIndex, 'mountedRef guard must run before setState commits')
})
