import test from 'node:test'
import assert from 'node:assert/strict'

import { DEVOPS_READ_ENDPOINTS, createDevopsApiClient } from './devopsApi.js'

test('createDevopsApiClient calls the read-only /devops endpoints with compact query params', async () => {
  const calls = []
  const httpClient = {
    get: async (url, config = {}) => {
      calls.push({ method: 'get', url, config })
      return { data: { ok: true, url, params: config.params || {} } }
    },
  }

  const client = createDevopsApiClient(httpClient)
  await client.getDashboard()
  await client.listServices()
  await client.getServiceSummary('svc/api')
  await client.listEnvironments({ service_id: 'svc-api', environment: 'prod', ignored: undefined, empty: '' })
  await client.listDeploymentTargets({ environment_id: 'env-prod' })
  await client.listCiRuns({ service_id: 'svc-api', status: 'failed', limit: 25 })
  await client.listDbStatus({ environment_id: 'env-prod' })

  assert.deepEqual(
    calls.map((call) => call.url),
    [
      '/devops/dashboard',
      '/devops/services',
      '/devops/services/svc%2Fapi/summary',
      '/devops/environments',
      '/devops/deployment-targets',
      '/devops/ci-runs',
      '/devops/db-status',
    ]
  )
  assert.deepEqual(calls[3].config.params, { service_id: 'svc-api', environment: 'prod' })
  assert.deepEqual(calls[5].config.params, { service_id: 'svc-api', status: 'failed', limit: 25 })

  assert.throws(() => client.getServiceSummary(''), /serviceId is required/)
  assert.equal(client.createService, undefined, 'Set 3 client must not expose mutating create actions')
  assert.equal(client.recordDbCheck, undefined, 'Set 3 client must stay read-only')
})

test('DEVOPS_READ_ENDPOINTS documents only GET endpoints from the Set 2 contract', () => {
  assert.deepEqual(Object.keys(DEVOPS_READ_ENDPOINTS).sort(), [
    'ciRuns',
    'dashboard',
    'dbStatus',
    'deploymentTargets',
    'environments',
    'serviceSummary',
    'services',
  ])
  assert.ok(Object.values(DEVOPS_READ_ENDPOINTS).every((path) => path.startsWith('/devops/')))
  assert.ok(Object.values(DEVOPS_READ_ENDPOINTS).every((path) => !path.includes(':preview')))
})
