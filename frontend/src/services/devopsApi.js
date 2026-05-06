import axios from 'axios'

export const DEVOPS_READ_ENDPOINTS = Object.freeze({
  dashboard: '/devops/dashboard',
  services: '/devops/services',
  serviceSummary: '/devops/services',
  environments: '/devops/environments',
  deploymentTargets: '/devops/deployment-targets',
  ciRuns: '/devops/ci-runs',
  dbStatus: '/devops/db-status',
})

const defaultHttpClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
})

function compactParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
  )
}

/**
 * Read-only frontend client for the Set 2 `/api/devops/*` contract.
 *
 * Set 3 intentionally exposes GET/list/dashboard methods only. Provider-side
 * execution and catalog mutations stay behind later approval-gated Sets.
 */
export function createDevopsApiClient(httpClient = defaultHttpClient) {
  return {
    getDashboard() {
      return httpClient.get(DEVOPS_READ_ENDPOINTS.dashboard)
    },
    listServices() {
      return httpClient.get(DEVOPS_READ_ENDPOINTS.services)
    },
    getServiceSummary(serviceId) {
      if (!serviceId) {
        throw new Error('serviceId is required')
      }
      return httpClient.get(`${DEVOPS_READ_ENDPOINTS.serviceSummary}/${encodeURIComponent(serviceId)}/summary`)
    },
    listEnvironments(params = {}) {
      return httpClient.get(DEVOPS_READ_ENDPOINTS.environments, {
        params: compactParams(params),
      })
    },
    listDeploymentTargets(params = {}) {
      return httpClient.get(DEVOPS_READ_ENDPOINTS.deploymentTargets, {
        params: compactParams(params),
      })
    },
    listCiRuns(params = {}) {
      return httpClient.get(DEVOPS_READ_ENDPOINTS.ciRuns, {
        params: compactParams(params),
      })
    },
    listDbStatus(params = {}) {
      return httpClient.get(DEVOPS_READ_ENDPOINTS.dbStatus, {
        params: compactParams(params),
      })
    },
  }
}

export const devopsApi = createDevopsApiClient()
