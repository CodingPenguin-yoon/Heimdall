const HEALTHY_VALUES = new Set(['healthy', 'ready', 'success', 'up_to_date'])
const WARNING_VALUES = new Set(['degraded', 'unknown', 'pending', 'stale', 'needs_test', 'draining'])
const CRITICAL_VALUES = new Set(['down', 'failed', 'blocked', 'unreachable'])
const RUNNING_VALUES = new Set(['queued', 'running', 'manual'])

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function normalize(value) {
  return String(value || '').toLowerCase()
}

function numberFromDashboard(section, key, fallback = 0) {
  const value = section && Object.prototype.hasOwnProperty.call(section, key) ? Number(section[key]) : fallback
  return Number.isFinite(value) && value >= 0 ? value : fallback
}

function sumDashboardValues(section) {
  if (!section || typeof section !== 'object') return 0
  return Object.values(section).reduce((total, value) => {
    const numeric = Number(value)
    return Number.isFinite(numeric) && numeric > 0 ? total + numeric : total
  }, 0)
}

function toneFromValues(...values) {
  const normalized = values.map(normalize)
  if (normalized.some((value) => CRITICAL_VALUES.has(value))) return 'critical'
  if (normalized.some((value) => WARNING_VALUES.has(value))) return 'warning'
  if (normalized.some((value) => HEALTHY_VALUES.has(value))) return 'healthy'
  return 'unknown'
}

function collectionState(items) {
  return items.length > 0 ? 'ready' : 'empty'
}

function latestTime(value) {
  const dateText = value?.started_at || value?.finished_at || value?.last_checked_at || value?.last_deployed_at || ''
  const timestamp = new Date(dateText).getTime()
  return Number.isFinite(timestamp) ? timestamp : 0
}

function sortByNewest(items) {
  return [...items].sort((left, right) => latestTime(right) - latestTime(left))
}

function countServicesBy(services, predicate) {
  return services.filter(predicate).length
}

function isDbAttention(row) {
  return (
    toneFromValues(row?.connection_health) !== 'healthy' ||
    ['pending', 'failed'].includes(normalize(row?.migration_status)) ||
    ['stale', 'failed', 'not_configured'].includes(normalize(row?.backup_status)) ||
    ['needs_test', 'blocked'].includes(normalize(row?.restore_readiness))
  )
}

function isDbCritical(row) {
  return (
    ['down'].includes(normalize(row?.connection_health)) ||
    ['failed'].includes(normalize(row?.migration_status)) ||
    ['failed'].includes(normalize(row?.backup_status)) ||
    ['blocked'].includes(normalize(row?.restore_readiness))
  )
}

function buildServiceItems(services) {
  return services.map((service) => ({
    id: service.service_id || service.name || 'unknown-service',
    title: service.name || service.service_id || 'Unnamed service',
    subtitle: service.owner_team || service.repo_provider || service.runtime || 'No owner/runtime metadata',
    status: service.health_status || 'unknown',
    tone: toneFromValues(service.health_status, service.lifecycle_status === 'paused' ? 'degraded' : null),
    detail: service.lifecycle_status || 'unknown lifecycle',
  }))
}

function buildCiItems(ciRuns) {
  return sortByNewest(ciRuns).map((run) => ({
    id: run.run_id || 'unknown-run',
    title: run.stage || run.run_id || 'CI/CD run',
    subtitle: run.service_id || 'Unknown service',
    status: run.status || 'unknown',
    tone: RUNNING_VALUES.has(normalize(run.status)) ? 'warning' : toneFromValues(run.status),
    detail: run.failure_summary || run.branch || run.commit_sha || 'No details',
  }))
}

function buildDbItems(dbStatuses) {
  return dbStatuses.map((row) => ({
    id: row.db_status_id || row.host_ref || 'unknown-database',
    title: `${row.engine || 'database'} / ${row.database_role || 'role'}`,
    subtitle: row.environment_id || row.host_ref || 'Unknown environment',
    status: row.connection_health || 'unknown',
    tone: isDbCritical(row) ? 'critical' : isDbAttention(row) ? 'warning' : 'healthy',
    detail: `migration: ${row.migration_status || 'unknown'} · backup: ${row.backup_status || 'unknown'}`,
  }))
}

function buildTargetItems(deploymentTargets) {
  return deploymentTargets.map((target) => ({
    id: target.target_id || target.host || 'unknown-target',
    title: target.host || target.target_id || 'Deployment target',
    subtitle: target.environment_id || target.provider || 'Unknown environment',
    status: target.target_status || 'unknown',
    tone: toneFromValues(target.target_status),
    detail: `${target.target_kind || 'target'}${target.port ? `:${target.port}` : ''}`,
  }))
}

function makeSection(items, message) {
  return {
    state: collectionState(items),
    message: items.length ? `${items.length} item${items.length === 1 ? '' : 's'}` : message,
    items,
  }
}

export function buildDevopsDashboardViewModel({
  dashboard = {},
  services = [],
  ciRuns = [],
  dbStatuses = [],
  deploymentTargets = [],
} = {}) {
  const serviceRows = asArray(services)
  const runRows = asArray(ciRuns)
  const dbRows = asArray(dbStatuses)
  const targetRows = asArray(deploymentTargets)

  const serviceDashboard = dashboard.services || {}
  const ciDashboard = dashboard.ci_runs || {}
  const dbDashboard = dashboard.db_status || {}
  const targetDashboard = dashboard.deployment_targets || {}

  const serviceTotal = numberFromDashboard(serviceDashboard, 'total', serviceRows.length)
  const activeServices = numberFromDashboard(
    serviceDashboard,
    'active',
    countServicesBy(serviceRows, (service) => normalize(service.lifecycle_status) === 'active')
  )
  const degradedServices = numberFromDashboard(
    serviceDashboard,
    'degraded',
    countServicesBy(serviceRows, (service) => normalize(service.health_status) === 'degraded')
  )
  const downServices = numberFromDashboard(
    serviceDashboard,
    'down',
    countServicesBy(serviceRows, (service) => normalize(service.health_status) === 'down')
  )

  const ciTotal = numberFromDashboard(ciDashboard, 'total', sumDashboardValues(ciDashboard) || runRows.length)
  const failedRuns = numberFromDashboard(
    ciDashboard,
    'failed',
    runRows.filter((run) => normalize(run.status) === 'failed').length
  )
  const runningRuns = numberFromDashboard(
    ciDashboard,
    'running',
    runRows.filter((run) => RUNNING_VALUES.has(normalize(run.status))).length
  )

  const dbAttention = dbRows.filter(isDbAttention).length
  const dbCritical = dbRows.filter(isDbCritical).length
  const pendingMigrations = numberFromDashboard(
    dbDashboard,
    'pending_migrations',
    dbRows.filter((row) => normalize(row.migration_status) === 'pending').length
  )
  const backupAttention = numberFromDashboard(
    dbDashboard,
    'backup_attention',
    dbRows.filter((row) => ['stale', 'failed', 'not_configured'].includes(normalize(row.backup_status))).length
  )

  const targetTotal = numberFromDashboard(targetDashboard, 'total', sumDashboardValues(targetDashboard) || targetRows.length)
  const readyTargets = numberFromDashboard(
    targetDashboard,
    'ready',
    targetRows.filter((target) => normalize(target.target_status) === 'ready').length
  )
  const unreachableTargets = numberFromDashboard(
    targetDashboard,
    'unreachable',
    targetRows.filter((target) => normalize(target.target_status) === 'unreachable').length
  )

  const totalItems = serviceTotal + ciTotal + dbRows.length + targetTotal
  const criticalSignals = downServices + failedRuns + dbCritical + unreachableTargets
  const warningSignals = degradedServices + runningRuns + pendingMigrations + backupAttention + dbAttention
  const overallTone = totalItems === 0 ? 'empty' : criticalSignals > 0 ? 'critical' : warningSignals > 0 ? 'warning' : 'healthy'

  return {
    overallTone,
    summaryCards: [
      {
        id: 'services',
        label: 'Services',
        value: serviceTotal,
        hint: `${activeServices} active / ${serviceTotal} total${degradedServices ? ` · ${degradedServices} degraded` : ''}${downServices ? ` · ${downServices} down` : ''}`,
        tone: downServices ? 'critical' : degradedServices ? 'warning' : serviceTotal ? 'healthy' : 'empty',
      },
      {
        id: 'ci',
        label: 'CI/CD runs',
        value: ciTotal,
        hint: `${failedRuns} failed · ${runningRuns} running`,
        tone: failedRuns ? 'critical' : runningRuns ? 'warning' : ciTotal ? 'healthy' : 'empty',
      },
      {
        id: 'database',
        label: 'Database status',
        value: dbRows.length,
        hint: `${dbAttention} attention · ${pendingMigrations} pending migrations · ${backupAttention} backup attention`,
        tone: dbCritical ? 'critical' : dbAttention ? 'warning' : dbRows.length ? 'healthy' : 'empty',
      },
      {
        id: 'targets',
        label: 'Deployment targets',
        value: targetTotal,
        hint: `${readyTargets} ready · ${unreachableTargets} unreachable`,
        tone: unreachableTargets ? 'critical' : targetTotal && readyTargets < targetTotal ? 'warning' : targetTotal ? 'healthy' : 'empty',
      },
    ],
    sections: {
      services: makeSection(buildServiceItems(serviceRows), 'No DevOps services registered yet'),
      ciRuns: makeSection(buildCiItems(runRows), 'No CI/CD runs recorded yet'),
      database: makeSection(buildDbItems(dbRows), 'No database status records yet'),
      deploymentTargets: makeSection(buildTargetItems(targetRows), 'No deployment targets registered yet'),
    },
  }
}
