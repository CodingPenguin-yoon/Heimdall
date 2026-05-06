import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  GitBranch,
  Loader2,
  RefreshCw,
  Server,
} from 'lucide-react'
import { devopsApi } from '../services/devopsApi'
import { buildDevopsDashboardViewModel } from '../utils/devopsDashboard'

const CARD_ICONS = {
  services: Server,
  ci: GitBranch,
  database: Database,
  targets: Activity,
}

function toneClasses(tone) {
  if (tone === 'critical') return 'border-red-200 bg-red-50 text-red-700'
  if (tone === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700'
  if (tone === 'healthy') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  return 'border-slate-200 bg-slate-50 text-slate-600'
}

function toneLabel(tone) {
  if (tone === 'critical') return 'Needs attention'
  if (tone === 'warning') return 'Watch'
  if (tone === 'healthy') return 'Stable'
  return 'Empty'
}

function SummaryCard({ card }) {
  const Icon = CARD_ICONS[card.id] || Activity
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-medium text-slate-500">{card.label}</div>
          <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{card.value}</div>
          <div className="mt-2 text-sm text-slate-600">{card.hint}</div>
        </div>
        <div className={`rounded-2xl border p-3 ${toneClasses(card.tone)}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  )
}

function StatusPill({ tone, label }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${toneClasses(tone)}`}>
      {label}
    </span>
  )
}

function DevOpsSection({ title, description, section }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-950">{title}</h3>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
        <StatusPill tone={section.state === 'empty' ? 'empty' : 'healthy'} label={section.message} />
      </div>

      {section.state === 'empty' ? (
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          {section.message}
        </div>
      ) : (
        <div className="space-y-3">
          {section.items.map((item) => (
            <div key={item.id} className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-slate-950">{item.title}</div>
                  <div className="mt-1 truncate text-xs text-slate-500">{item.subtitle}</div>
                  <div className="mt-2 text-xs text-slate-600">{item.detail}</div>
                </div>
                <StatusPill tone={item.tone} label={item.status} />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function DevOpsDashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [services, setServices] = useState([])
  const [ciRuns, setCiRuns] = useState([])
  const [dbStatuses, setDbStatuses] = useState([])
  const [deploymentTargets, setDeploymentTargets] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadIssues, setLoadIssues] = useState([])
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null)
  const mountedRef = useRef(false)

  const fetchDevOpsData = async () => {
    if (!mountedRef.current) {
      return
    }
    setRefreshing(true)
    const results = await Promise.allSettled([
      devopsApi.getDashboard(),
      devopsApi.listServices(),
      devopsApi.listCiRuns({ limit: 50 }),
      devopsApi.listDbStatus(),
      devopsApi.listDeploymentTargets(),
    ])

    if (!mountedRef.current) {
      return
    }

    const nextIssues = []
    if (results[0].status === 'fulfilled') {
      setDashboard(results[0].value.data || {})
    } else {
      nextIssues.push('dashboard')
      setDashboard({})
    }

    if (results[1].status === 'fulfilled') {
      setServices(results[1].value.data?.services || [])
    } else {
      nextIssues.push('services')
      setServices([])
    }

    if (results[2].status === 'fulfilled') {
      setCiRuns(results[2].value.data?.ci_runs || [])
    } else {
      nextIssues.push('ci/cd')
      setCiRuns([])
    }

    if (results[3].status === 'fulfilled') {
      setDbStatuses(results[3].value.data?.db_statuses || [])
    } else {
      nextIssues.push('database')
      setDbStatuses([])
    }

    if (results[4].status === 'fulfilled') {
      setDeploymentTargets(results[4].value.data?.deployment_targets || [])
    } else {
      nextIssues.push('deployment targets')
      setDeploymentTargets([])
    }

    setLoadIssues(nextIssues)
    setLastUpdatedAt(new Date())
    setLoading(false)
    setRefreshing(false)
  }

  useEffect(() => {
    mountedRef.current = true
    fetchDevOpsData()
    return () => {
      mountedRef.current = false
    }
  }, [])

  const viewModel = useMemo(
    () => buildDevopsDashboardViewModel({ dashboard, services, ciRuns, dbStatuses, deploymentTargets }),
    [dashboard, services, ciRuns, dbStatuses, deploymentTargets]
  )

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-slate-500" />
        <div className="mt-3 text-sm font-medium text-slate-600">Loading DevOps dashboard...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:flex-row md:items-start">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-500">
            <Activity className="h-4 w-4" />
            DevOps Operations
          </div>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Read-only DevOps dashboard</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">
            Service catalog, CI/CD runs, database posture, and deployment target status from the typed `/api/devops/*` contract.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <StatusPill tone={viewModel.overallTone} label={toneLabel(viewModel.overallTone)} />
            {lastUpdatedAt && (
              <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                <Clock3 className="h-3.5 w-3.5" />
                Updated {lastUpdatedAt.toLocaleString()}
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={fetchDevOpsData}
          disabled={refreshing}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {loadIssues.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <div className="font-semibold">Partial data load issue</div>
            <div className="mt-1">Unable to load: {loadIssues.join(', ')}. The dashboard is still read-only and safe to refresh.</div>
          </div>
        </div>
      )}

      {viewModel.overallTone === 'healthy' && (
        <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <CheckCircle2 className="h-4 w-4" />
          DevOps signals currently look stable.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {viewModel.summaryCards.map((card) => (
          <SummaryCard key={card.id} card={card} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <DevOpsSection
          title="Services"
          description="Catalog and lifecycle posture for application services."
          section={viewModel.sections.services}
        />
        <DevOpsSection
          title="CI/CD"
          description="Recent pipeline/build/test/deploy status."
          section={viewModel.sections.ciRuns}
        />
        <DevOpsSection
          title="Database"
          description="Connection, migration, backup, and restore readiness."
          section={viewModel.sections.database}
        />
        <DevOpsSection
          title="Deployment targets"
          description="Read-only target reachability and provider references."
          section={viewModel.sections.deploymentTargets}
        />
      </div>
    </div>
  )
}

export default DevOpsDashboard
