import test from 'node:test'
import assert from 'node:assert/strict'

import { buildDevopsDashboardViewModel } from './devopsDashboard.js'

test('buildDevopsDashboardViewModel returns empty-state metadata for an empty DevOps catalog', () => {
  const viewModel = buildDevopsDashboardViewModel({
    dashboard: {
      services: { total: 0, active: 0 },
      ci_runs: { total: 0, failed: 0, running: 0 },
      db_status: { total: 0, attention: 0 },
      deployment_targets: { total: 0, ready: 0 },
    },
    services: [],
    ciRuns: [],
    dbStatuses: [],
    deploymentTargets: [],
  })

  assert.equal(viewModel.overallTone, 'empty')
  assert.deepEqual(
    viewModel.summaryCards.map((card) => card.id),
    ['services', 'ci', 'database', 'targets']
  )
  assert.equal(viewModel.summaryCards.find((card) => card.id === 'services').value, 0)
  assert.equal(viewModel.sections.services.state, 'empty')
  assert.equal(viewModel.sections.services.message, 'No DevOps services registered yet')
  assert.equal(viewModel.sections.ciRuns.state, 'empty')
  assert.equal(viewModel.sections.database.state, 'empty')
  assert.equal(viewModel.sections.deploymentTargets.state, 'empty')
})

test('buildDevopsDashboardViewModel derives attention counts and sorted CI rows from read-only API payloads', () => {
  const ciRuns = [
    {
      run_id: 'run-old-success',
      service_id: 'svc-api',
      status: 'success',
      stage: 'deploy',
      started_at: '2026-05-06T01:00:00Z',
      allowed_actions: [],
    },
    {
      run_id: 'run-new-failed',
      service_id: 'svc-api',
      status: 'failed',
      stage: 'test',
      started_at: '2026-05-06T03:00:00Z',
      failure_summary: 'unit tests failed',
      allowed_actions: ['retry'],
    },
    {
      run_id: 'run-mid-running',
      service_id: 'svc-worker',
      status: 'running',
      stage: 'build',
      started_at: '2026-05-06T02:00:00Z',
      allowed_actions: ['cancel'],
    },
  ]

  const viewModel = buildDevopsDashboardViewModel({
    dashboard: {},
    services: [
      {
        service_id: 'svc-api',
        name: 'API',
        lifecycle_status: 'active',
        health_status: 'healthy',
        repo_provider: 'github',
      },
      {
        service_id: 'svc-worker',
        name: 'Worker',
        lifecycle_status: 'paused',
        health_status: 'degraded',
        repo_provider: 'gitlab',
      },
    ],
    ciRuns,
    dbStatuses: [
      {
        db_status_id: 'db-prod',
        environment_id: 'env-prod',
        engine: 'postgres',
        database_role: 'primary',
        connection_health: 'down',
        migration_status: 'pending',
        backup_status: 'stale',
      },
      {
        db_status_id: 'db-cache',
        environment_id: 'env-prod',
        engine: 'redis',
        database_role: 'cache',
        connection_health: 'healthy',
        migration_status: 'not_applicable',
        backup_status: 'ready',
      },
    ],
    deploymentTargets: [
      { target_id: 'target-a', environment_id: 'env-prod', target_kind: 'host', target_status: 'ready' },
      { target_id: 'target-b', environment_id: 'env-prod', target_kind: 'host', target_status: 'unreachable' },
    ],
  })

  assert.equal(viewModel.overallTone, 'critical')
  assert.match(viewModel.summaryCards.find((card) => card.id === 'services').hint, /1 active \/ 2 total/)
  assert.match(viewModel.summaryCards.find((card) => card.id === 'ci').hint, /1 failed/)
  assert.match(viewModel.summaryCards.find((card) => card.id === 'database').hint, /1 attention/)
  assert.match(viewModel.summaryCards.find((card) => card.id === 'targets').hint, /1 unreachable/)
  assert.deepEqual(
    viewModel.sections.ciRuns.items.map((run) => run.id),
    ['run-new-failed', 'run-mid-running', 'run-old-success']
  )
  assert.deepEqual(
    ciRuns.map((run) => run.run_id),
    ['run-old-success', 'run-new-failed', 'run-mid-running'],
    'source API arrays must not be mutated by sorting'
  )
  assert.equal(viewModel.sections.services.items.find((item) => item.id === 'svc-worker').tone, 'warning')
  assert.equal(viewModel.sections.database.items.find((item) => item.id === 'db-prod').tone, 'critical')
})
