import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Clock3,
  Copy,
  ExternalLink,
  FolderGit2,
  GitBranch,
  LayoutList,
  Radar,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react'

import {
  createGitLabProject,
  getGitLabProjectSettings,
  getGitLabProjects,
  syncGitLabProjects,
  updateGitLabProjectSettings,
} from '../services/api'

const rolloutSteps = [
  {
    title: '1. 프로젝트 감지',
    description: 'GitLab 프로젝트를 inventory로 읽어와 배포 대상 후보를 고정합니다.',
    icon: Radar,
  },
  {
    title: '2. 설정 확인',
    description: '프로젝트별 환경 정책과 bootstrap 입력값을 확인하는 단계를 둡니다.',
    icon: FolderGit2,
  },
  {
    title: '3. Deploy Staging',
    description: '준비가 끝난 프로젝트만 staging 배포 흐름으로 넘기는 구조를 유지합니다.',
    icon: GitBranch,
  },
]

const navigationCards = [
  {
    title: 'Task Board',
    description: '현재 배포 작업과 로그 흐름을 확인합니다.',
    path: '/tasks',
    label: 'Task Board 열기',
    icon: Clock3,
  },
  {
    title: 'Instance List',
    description: '이미 배포된 인스턴스 상태와 운영 액션을 확인합니다.',
    path: '/list',
    label: 'Instance List 열기',
    icon: LayoutList,
  },
  {
    title: 'Monitoring',
    description: '노드와 VM 리소스 사용률을 빠르게 점검합니다.',
    path: '/monitoring',
    label: 'Monitoring 열기',
    icon: Activity,
  },
]

const initialCreateForm = {
  name: '',
  path: '',
  description: '',
  visibility: 'private',
  initialize_with_readme: true,
  default_branch: '',
}

const visibilityBadgeClassNames = {
  private: 'border-gray-300 bg-gray-100 text-gray-700',
  internal: 'border-blue-200 bg-blue-50 text-blue-700',
  public: 'border-emerald-200 bg-emerald-50 text-emerald-700',
}

const configurationStatusBadgeClassNames = {
  discovered: 'border-gray-300 bg-gray-100 text-gray-700',
  configured: 'border-blue-200 bg-blue-50 text-blue-700',
  ready_for_bootstrap: 'border-emerald-200 bg-emerald-50 text-emerald-700',
}

const configurationStatusLabels = {
  discovered: 'Discovered',
  configured: 'Configured',
  ready_for_bootstrap: 'Ready for bootstrap',
}

const initialSettingsForm = {
  staging_enabled: false,
  ready_for_bootstrap: false,
  database_required: false,
  database_engine: 'postgres',
  database_mode: 'shared-cluster',
  migration_command: '',
  deploy_branch: 'main',
  bootstrap_strategy: 'merge_request',
  notes: '',
}

const bootstrapStrategyLabels = {
  merge_request: 'Merge Request',
  direct_commit: 'Direct commit',
  manual: 'Manual',
}

function GitLabWorkspace() {
  const [activeView, setActiveView] = useState('overview')
  const [inventory, setInventory] = useState({
    configured: false,
    can_sync: false,
    default_namespace_path: 'heimdall',
    configuration_error: null,
    projects: [],
    last_sync: null,
  })
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [inventoryNotice, setInventoryNotice] = useState('')
  const [createError, setCreateError] = useState('')
  const [creating, setCreating] = useState(false)
  const [createForm, setCreateForm] = useState(initialCreateForm)
  const [editingSettingsProjectId, setEditingSettingsProjectId] = useState(null)
  const [settingsForm, setSettingsForm] = useState(initialSettingsForm)
  const [settingsLoadingProjectId, setSettingsLoadingProjectId] = useState(null)
  const [settingsSavingProjectId, setSettingsSavingProjectId] = useState(null)
  const [settingsError, setSettingsError] = useState('')
  const [expandedCloneProjectId, setExpandedCloneProjectId] = useState(null)
  const [copyFeedback, setCopyFeedback] = useState({ projectId: null, field: null, status: '' })
  const [showCreateForm, setShowCreateForm] = useState(false)

  const loadInventory = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await getGitLabProjects()
      setInventory(response.data)
    } catch (apiError) {
      setError(apiError.response?.data?.detail || 'GitLab inventory를 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    setError('')
    try {
      await syncGitLabProjects()
      await loadInventory()
    } catch (apiError) {
      setError(apiError.response?.data?.detail || 'GitLab 수동 동기화에 실패했습니다.')
    } finally {
      setSyncing(false)
    }
  }

  const handleCreateFormChange = (event) => {
    const { name, value, type, checked } = event.target
    setCreateForm((current) => {
      const next = {
        ...current,
        [name]: type === 'checkbox' ? checked : value,
      }
      if (name === 'initialize_with_readme' && !checked) {
        next.default_branch = ''
      }
      return next
    })
  }

  const handleCreateProject = async (event) => {
    event.preventDefault()
    setCreating(true)
    setCreateError('')
    setInventoryNotice('')

    try {
      const payload = {
        name: createForm.name.trim(),
        visibility: createForm.visibility,
        initialize_with_readme: createForm.initialize_with_readme,
      }

      if (createForm.path.trim()) {
        payload.path = createForm.path.trim()
      }
      if (createForm.description.trim()) {
        payload.description = createForm.description.trim()
      }
      if (createForm.default_branch.trim()) {
        payload.default_branch = createForm.default_branch.trim()
      }

      const response = await createGitLabProject(payload)
      await loadInventory()
      setCreateForm(initialCreateForm)
      setShowCreateForm(false)
      setInventoryNotice(`프로젝트가 생성되었습니다: ${response.data.project.path_with_namespace}`)
    } catch (apiError) {
      setCreateError(apiError.response?.data?.detail || 'GitLab 프로젝트 생성에 실패했습니다.')
    } finally {
      setCreating(false)
    }
  }

  const handleCloneToggle = (projectId) => {
    setExpandedCloneProjectId((current) => (current === projectId ? null : projectId))
  }

  const handleSettingsToggle = async (projectId) => {
    if (editingSettingsProjectId === projectId) {
      setEditingSettingsProjectId(null)
      setSettingsError('')
      setSettingsForm(initialSettingsForm)
      return
    }

    setSettingsLoadingProjectId(projectId)
    setSettingsError('')

    try {
      const response = await getGitLabProjectSettings(projectId)
      setSettingsForm({
        staging_enabled: Boolean(response.data.staging_enabled),
        ready_for_bootstrap: Boolean(response.data.ready_for_bootstrap),
        database_required: Boolean(response.data.database_required),
        database_engine: response.data.database_engine || 'postgres',
        database_mode: response.data.database_mode || 'shared-cluster',
        migration_command: response.data.migration_command || '',
        deploy_branch: response.data.deploy_branch || 'main',
        bootstrap_strategy: response.data.bootstrap_strategy || 'merge_request',
        notes: response.data.notes || '',
      })
      setEditingSettingsProjectId(projectId)
    } catch (apiError) {
      setSettingsError(apiError.response?.data?.detail || '프로젝트 설정을 불러오지 못했습니다.')
      setEditingSettingsProjectId(projectId)
      setSettingsForm(initialSettingsForm)
    } finally {
      setSettingsLoadingProjectId(null)
    }
  }

  const handleSettingsFormChange = (event) => {
    const { name, checked, value, type } = event.target

    setSettingsForm((current) => {
      const next = {
        ...current,
        [name]: type === 'checkbox' ? checked : value,
      }

      if (name === 'ready_for_bootstrap' && checked) {
        next.staging_enabled = true
      }

      if (name === 'staging_enabled' && !checked) {
        next.ready_for_bootstrap = false
      }

      if (name === 'database_required' && !checked) {
        next.database_engine = 'postgres'
        next.database_mode = 'shared-cluster'
        next.migration_command = ''
      }

      return next
    })
  }

  const handleSaveSettings = async (projectId) => {
    setSettingsSavingProjectId(projectId)
    setSettingsError('')
    setInventoryNotice('')

    try {
      await updateGitLabProjectSettings(projectId, settingsForm)
      await loadInventory()
      setEditingSettingsProjectId(null)
      setSettingsForm(initialSettingsForm)
      setInventoryNotice('프로젝트 설정이 저장되었습니다.')
    } catch (apiError) {
      setSettingsError(apiError.response?.data?.detail || '프로젝트 설정 저장에 실패했습니다.')
    } finally {
      setSettingsSavingProjectId(null)
    }
  }

  const handleCopyCloneUrl = async (projectId, field, value) => {
    if (!value) {
      setCopyFeedback({ projectId, field, status: 'unavailable' })
      return
    }

    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error('clipboard unavailable')
      }
      await navigator.clipboard.writeText(value)
      setCopyFeedback({ projectId, field, status: 'copied' })
    } catch (copyError) {
      setCopyFeedback({ projectId, field, status: 'failed' })
    }
  }

  useEffect(() => {
    loadInventory()
  }, [])

  const projectCount = inventory.projects?.length || 0
  const lastSync = inventory.last_sync
  const statusValue = inventory.configured ? 'Configured' : 'Needs setup'
  const syncValue = lastSync?.status === 'success' ? 'Synced' : lastSync?.status === 'error' ? 'Sync error' : 'Idle'
  const defaultNamespacePath = inventory.default_namespace_path || 'heimdall'
  const setupProjects = inventory.projects || []

  return (
    <div className="mx-auto max-w-[1440px] space-y-8">
      <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-8 py-8 xl:px-10">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-stretch">
            <div className="max-w-4xl space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700">
                <GitBranch className="h-4 w-4" />
                GitLab Workspace
              </div>
              <div className="space-y-2">
                <h2 className="text-3xl font-semibold tracking-tight text-gray-900">
                  GitLab inventory를 platform DB 기준으로 확인합니다
                </h2>
                <p className="text-sm leading-6 text-gray-600">
                  이 탭은 저장된 GitLab 프로젝트 목록을 보여주고, 필요할 때만 수동 동기화를 실행합니다.
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5">
              <div className="flex h-full flex-col gap-4">
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-gray-900">수동 동기화</p>
                  <p className="text-sm leading-6 text-gray-600">
                    System Hook이 들어와도 수동 sync를 fallback으로 유지합니다.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleSync}
                  disabled={!inventory.can_sync || syncing}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-blue-300 bg-white px-4 py-3 text-sm font-medium text-blue-700 transition-colors hover:border-blue-400 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                >
                  <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
                  Sync now
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 px-8 py-6 md:grid-cols-2 xl:px-10">
          <article className="rounded-xl border border-gray-200 bg-white p-5 border-l-4 border-l-blue-500">
            <p className="text-sm font-medium text-gray-500">GitLab config</p>
            <p className="mt-2 text-xl font-semibold text-gray-900">{statusValue}</p>
            <p className="mt-3 text-sm leading-6 text-gray-600">
              {inventory.configuration_error || 'GitLab base URL validation passed.'}
            </p>
          </article>
          <article className="rounded-xl border border-gray-200 bg-white p-5 border-l-4 border-l-emerald-500">
            <p className="text-sm font-medium text-gray-500">Persisted projects</p>
            <p className="mt-2 text-xl font-semibold text-gray-900">{projectCount}</p>
            <p className="mt-3 text-sm leading-6 text-gray-600">
              Last sync state: {syncValue}
              {lastSync?.updated_at ? ` · ${lastSync.updated_at}` : ''}
            </p>
          </article>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-200 bg-rose-50 px-6 py-4 text-sm text-rose-700">
          {error}
        </section>
      ) : null}

      <section className="rounded-2xl border border-gray-200 bg-white px-8 shadow-sm xl:px-10">
        <div className="flex flex-col gap-4 border-b border-gray-200 py-5 sm:flex-row sm:items-end sm:justify-between">
          <div
            role="tablist"
            aria-label="GitLab workspace views"
            className="flex w-full items-center gap-2 overflow-x-auto"
          >
            <button
              type="button"
              onClick={() => setActiveView('overview')}
              id="gitlab-workspace-tab-overview"
              role="tab"
              aria-selected={activeView === 'overview'}
              aria-controls="gitlab-workspace-panel-overview"
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeView === 'overview'
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-600 border-transparent hover:text-gray-900'
              }`}
            >
              Overview
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveView('project-setup')
                setShowCreateForm(false)
                setCreateError('')
              }}
              id="gitlab-workspace-tab-project-setup"
              role="tab"
              aria-selected={activeView === 'project-setup'}
              aria-controls="gitlab-workspace-panel-project-setup"
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeView === 'project-setup'
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-600 border-transparent hover:text-gray-900'
              }`}
            >
              Project Setup
            </button>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            {activeView === 'overview' ? (
              <button
                type="button"
                onClick={() => {
                  setCreateError('')
                  setShowCreateForm((current) => !current)
                }}
                className="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-white px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:border-blue-400"
              >
                {showCreateForm ? 'Hide create form' : 'Create repo'}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setActiveView('overview')
                  setShowCreateForm(false)
                }}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-blue-300 hover:text-blue-700"
              >
                Back to overview
              </button>
            )}
          </div>
        </div>
      </section>

      {inventoryNotice ? (
        <section className="rounded-2xl border border-emerald-200 bg-emerald-50 px-6 py-4 text-sm text-emerald-700">
          {inventoryNotice}
        </section>
      ) : null}

      {activeView === 'overview' ? (
        <div
          id="gitlab-workspace-panel-overview"
          role="tabpanel"
          aria-labelledby="gitlab-workspace-tab-overview"
          className="space-y-6"
        >
          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_380px]">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-blue-50 p-2">
                  <GitBranch className="h-5 w-5 text-blue-700" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">연결 이후 기본 흐름</h3>
                  <p className="text-sm text-gray-500">첫 inventory slice에서 유지할 운영 기준입니다.</p>
                </div>
              </div>

              <div className="mt-6 space-y-4">
                {rolloutSteps.map(({ title, description, icon: Icon }) => (
                  <div key={title} className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                    <div className="flex items-start gap-3">
                      <div className="rounded-lg bg-white p-2 shadow-sm">
                        <Icon className="h-4 w-4 text-gray-700" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900">{title}</h4>
                        <p className="mt-2 text-sm leading-6 text-gray-600">{description}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm xl:self-start">
              <h3 className="text-lg font-semibold text-gray-900">현재 상태</h3>
              <div className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
                <p className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  persisted inventory를 기본으로 노출하고, project 관련 GitLab System Hook이 들어오면 inventory sync만 자동 반영합니다.
                </p>
                <p className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  sync 실행과 System Hook 처리에는 GitLab token과 webhook secret이 필요하고, 목록 조회는 DB에 저장된 결과를 그대로 사용합니다.
                </p>
                {!inventory.can_sync ? (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
                    <div className="flex items-start gap-3">
                      <ShieldAlert className="mt-0.5 h-5 w-5 text-amber-600" />
                      <p>수동 동기화를 실행하려면 유효한 `GITLAB_BASE_URL`과 `GITLAB_API_TOKEN`이 필요합니다.</p>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Persisted GitLab Projects</h3>
                <p className="text-sm text-gray-500">레포 목록과 clone 주소를 중심으로 빠르게 확인합니다.</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setCreateError('')
                  setShowCreateForm((current) => !current)
                }}
                className="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-white px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:border-blue-400"
              >
                {showCreateForm ? 'Hide create form' : 'Create repo'}
              </button>
            </div>

            {showCreateForm ? (
              <div className="mt-6 rounded-2xl border border-blue-100 bg-blue-50/50 p-5">
                <div className="flex items-center gap-4">
                  <div>
                    <h4 className="text-base font-semibold text-gray-900">Create GitLab Project</h4>
                    <p className="text-sm text-gray-500">GitLab UI를 열지 않고 바로 새 저장소를 만듭니다.</p>
                  </div>
                </div>

                <form className="mt-6 space-y-4" onSubmit={handleCreateProject}>
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-gray-700">Name</span>
                      <input
                        type="text"
                        name="name"
                        value={createForm.name}
                        onChange={handleCreateFormChange}
                        required
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                        placeholder="my-service"
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-gray-700">Path</span>
                      <input
                        type="text"
                        name="path"
                        value={createForm.path}
                        onChange={handleCreateFormChange}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                        placeholder="optional-repo-path"
                      />
                    </label>
                    <div className="space-y-2">
                      <span className="text-sm font-medium text-gray-700">Namespace</span>
                      <div className="rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                        {defaultNamespacePath}
                      </div>
                    </div>
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-gray-700">Visibility</span>
                      <select
                        name="visibility"
                        value={createForm.visibility}
                        onChange={handleCreateFormChange}
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                      >
                        <option value="private">private</option>
                        <option value="internal">internal</option>
                        <option value="public">public</option>
                      </select>
                    </label>
                  </div>

                  <label className="block space-y-2">
                    <span className="text-sm font-medium text-gray-700">Description</span>
                    <textarea
                      name="description"
                      value={createForm.description}
                      onChange={handleCreateFormChange}
                      rows={3}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                      placeholder="optional project description"
                    />
                  </label>

                  <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                    <label className="space-y-2">
                      <span className="text-sm font-medium text-gray-700">Default branch</span>
                      <input
                        type="text"
                        name="default_branch"
                        value={createForm.default_branch}
                        onChange={handleCreateFormChange}
                        disabled={!createForm.initialize_with_readme}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400 disabled:bg-gray-50 disabled:text-gray-400"
                        placeholder={createForm.initialize_with_readme ? 'main' : 'README initialization required'}
                      />
                    </label>
                    <label className="inline-flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        name="initialize_with_readme"
                        checked={createForm.initialize_with_readme}
                        onChange={handleCreateFormChange}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600"
                      />
                      Initialize with README
                    </label>
                  </div>

                  {createError ? (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                      {createError}
                    </div>
                  ) : null}

                  <div className="flex items-center justify-between gap-4 border-t border-gray-200 pt-4">
                    <p className="text-sm text-gray-500">
                      새 프로젝트는 고정 namespace `{defaultNamespacePath}` 에 생성됩니다.
                    </p>
                    <button
                      type="submit"
                      disabled={creating || !inventory.can_sync}
                      className="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-white px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:border-blue-400 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                    >
                      <RefreshCw className={`h-4 w-4 ${creating ? 'animate-spin' : ''}`} />
                      Create project
                    </button>
                  </div>
                </form>
              </div>
            ) : null}

            <div className="mt-6">
              {loading ? (
                <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-600">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  GitLab inventory를 불러오는 중입니다.
                </div>
              ) : projectCount === 0 ? (
                <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-8 text-sm text-gray-600">
                  저장된 GitLab 프로젝트가 없습니다. 설정을 확인한 뒤 `Sync now`를 실행하세요.
                </div>
              ) : (
                <div className="space-y-4">
                  {inventory.projects.map((project) => {
                    const isCloneOpen = expandedCloneProjectId === project.gitlab_project_id
                    const configurationStatus = project.configuration_status || 'discovered'
                    const visibilityBadgeClassName =
                      visibilityBadgeClassNames[project.visibility] || visibilityBadgeClassNames.private
                    const configurationBadgeClassName =
                      configurationStatusBadgeClassNames[configurationStatus] ||
                      configurationStatusBadgeClassNames.discovered
                    const configurationLabel =
                      configurationStatusLabels[configurationStatus] || configurationStatusLabels.discovered

                    return (
                      <article
                        key={project.gitlab_project_id}
                        className="rounded-xl border border-gray-200 bg-gray-50 p-4 transition-colors hover:border-blue-200 hover:bg-blue-50/60 md:p-5"
                      >
                        <div className="flex flex-col gap-5 xl:grid xl:grid-cols-[minmax(0,1fr)_220px] xl:items-start">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="truncate text-base font-semibold text-gray-900">{project.path_with_namespace}</p>
                              <span
                                className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-semibold ${visibilityBadgeClassName}`}
                              >
                                {project.visibility}
                              </span>
                              {project.archived ? (
                                <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700">
                                  archived
                                </span>
                              ) : null}
                              <span
                                className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-semibold ${configurationBadgeClassName}`}
                              >
                                {configurationLabel}
                              </span>
                            </div>
                            <p className="mt-2 break-all text-sm text-gray-500">{project.http_url_to_repo}</p>

                            <div className="mt-4 grid gap-3 md:grid-cols-2">
                              {[
                                { label: 'Default branch', value: project.default_branch || '-' },
                                { label: 'Last activity', value: project.last_activity_at || '-' },
                              ].map(({ label, value }) => (
                                <div key={label} className="rounded-lg border border-white bg-white px-4 py-3">
                                  <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                                    {label}
                                  </p>
                                  <p className="mt-1 break-all text-sm font-medium text-gray-700">
                                    {value}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-2 lg:justify-end xl:flex-col xl:items-stretch">
                            <a
                              href={project.web_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center justify-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-xs font-medium text-gray-700 transition-colors hover:border-blue-300 hover:text-blue-700 xl:w-full"
                            >
                              Open
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                            <button
                              type="button"
                              onClick={() => handleCloneToggle(project.gitlab_project_id)}
                              aria-expanded={isCloneOpen}
                              className="inline-flex items-center justify-center gap-2 rounded-md border border-blue-300 bg-white px-3 py-2 text-xs font-medium text-blue-700 transition-colors hover:border-blue-400 xl:w-full"
                            >
                              Clone
                              {isCloneOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                            </button>
                          </div>
                        </div>

                        {isCloneOpen ? (
                          <div className="mt-4 rounded-xl border border-gray-200 bg-white p-4">
                            <div className="grid gap-3 md:grid-cols-2">
                              {[
                                { label: 'HTTPS', field: 'http_url_to_repo', value: project.http_url_to_repo },
                                { label: 'SSH', field: 'ssh_url_to_repo', value: project.ssh_url_to_repo },
                              ].map(({ label, field, value }) => {
                                const status =
                                  copyFeedback.projectId === project.gitlab_project_id && copyFeedback.field === field
                                    ? copyFeedback.status
                                    : ''

                                return (
                                  <div key={field} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                                    <div className="flex items-center justify-between gap-3">
                                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
                                      <button
                                        type="button"
                                        onClick={() => handleCopyCloneUrl(project.gitlab_project_id, field, value)}
                                        disabled={!value}
                                        className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                                      >
                                        {status === 'copied' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                                        Copy
                                      </button>
                                    </div>
                                    <p className="mt-2 break-all text-sm text-gray-700">{value || 'Not available yet. Run sync to backfill existing rows.'}</p>
                                    {status === 'copied' ? (
                                      <p className="mt-2 text-xs text-emerald-600">Copied to clipboard.</p>
                                    ) : null}
                                    {status === 'failed' ? (
                                      <p className="mt-2 text-xs text-rose-600">Clipboard copy failed in this browser.</p>
                                    ) : null}
                                    {status === 'unavailable' ? (
                                      <p className="mt-2 text-xs text-gray-500">No clone URL is stored for this protocol yet.</p>
                                    ) : null}
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        ) : null}
                      </article>
                    )
                  })}
                </div>
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">운영 화면으로 이동</h3>
                <p className="text-sm text-gray-500">GitLab inventory와 별개로 바로 사용할 수 있는 기존 화면입니다.</p>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {navigationCards.map(({ title, description, path, label, icon: Icon }) => (
                <article key={title} className="rounded-xl border border-gray-200 bg-gray-50 p-5">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-white p-2 shadow-sm">
                      <Icon className="h-5 w-5 text-gray-700" />
                    </div>
                    <h4 className="text-sm font-semibold text-gray-900">{title}</h4>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-gray-600">{description}</p>
                  <Link
                    to={path}
                    className="mt-5 inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-blue-300 hover:text-blue-700"
                  >
                    {label}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </article>
              ))}
            </div>
          </section>
        </div>
      ) : (
        <div
          id="gitlab-workspace-panel-project-setup"
          role="tabpanel"
          aria-labelledby="gitlab-workspace-tab-project-setup"
          className="space-y-6"
        >
          <section className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm xl:self-start">
              <h3 className="text-lg font-semibold text-gray-900">Project Setup</h3>
              <div className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
                <p className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  이 탭에서는 프로젝트별 staging 준비 상태와 bootstrap 전 메모만 관리합니다.
                </p>
                <p className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  DB 필요 여부, 배포 브랜치, bootstrap 전략까지 이 단계에서 확정하고 실제 실행은 다음 단계에서 붙입니다.
                </p>
              </div>
            </div>

            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Project configuration</h3>
                  <p className="text-sm text-gray-500">기존 persisted project를 기준으로 platform-side 설정만 편집합니다.</p>
                </div>
                <span className="text-sm text-gray-500">{setupProjects.length} project(s)</span>
              </div>

              <div className="mt-6">
                {loading ? (
                  <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-600">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    프로젝트 설정 대상을 불러오는 중입니다.
                  </div>
                ) : setupProjects.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-8 text-sm text-gray-600">
                    설정할 GitLab 프로젝트가 없습니다. 먼저 Overview에서 프로젝트를 동기화하거나 생성하세요.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {setupProjects.map((project) => {
                      const isSettingsOpen = editingSettingsProjectId === project.gitlab_project_id
                      const configurationStatus = project.configuration_status || 'discovered'
                      const configurationBadgeClassName =
                        configurationStatusBadgeClassNames[configurationStatus] ||
                        configurationStatusBadgeClassNames.discovered
                      const configurationLabel =
                        configurationStatusLabels[configurationStatus] || configurationStatusLabels.discovered
                      const settingsSummary = project.settings_summary
                      const stagingSummaryLabel =
                        settingsSummary == null
                          ? 'Not configured'
                          : settingsSummary.staging_enabled
                            ? 'Enabled'
                            : 'Disabled'
                      const databaseSummaryLabel =
                        settingsSummary?.database_required
                          ? `${settingsSummary.database_engine || 'postgres'} · ${settingsSummary.database_mode || 'shared-cluster'}`
                          : 'Not required'
                      const settingsUpdatedAt = settingsSummary?.updated_at || '-'
                      const deployBranchSummary = settingsSummary?.deploy_branch || 'main'
                      const bootstrapStrategySummary =
                        bootstrapStrategyLabels[settingsSummary?.bootstrap_strategy] || 'Merge Request'

                      return (
                        <article
                          key={project.gitlab_project_id}
                          className="rounded-xl border border-gray-200 bg-gray-50 p-5"
                        >
                          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="truncate text-base font-semibold text-gray-900">
                                  {project.path_with_namespace}
                                </p>
                                <span
                                  className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-semibold ${configurationBadgeClassName}`}
                                >
                                  {configurationLabel}
                                </span>
                              </div>
                              <div className="mt-4 grid gap-3 md:grid-cols-2">
                                {[
                                  { label: 'Staging', value: stagingSummaryLabel },
                                  { label: 'Database', value: databaseSummaryLabel },
                                  { label: 'Deploy branch', value: deployBranchSummary },
                                  { label: 'Bootstrap', value: bootstrapStrategySummary },
                                  { label: 'Settings updated', value: settingsUpdatedAt },
                                ].map(({ label, value }) => (
                                  <div key={label} className="rounded-lg border border-white bg-white px-4 py-3">
                                    <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                                      {label}
                                    </p>
                                    <p className="mt-1 break-all text-sm font-medium text-gray-700">
                                      {value}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={() => handleSettingsToggle(project.gitlab_project_id)}
                              disabled={settingsLoadingProjectId === project.gitlab_project_id}
                              className="inline-flex items-center justify-center gap-2 rounded-lg border border-blue-300 bg-white px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:border-blue-400 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                            >
                              {settingsLoadingProjectId === project.gitlab_project_id
                                ? 'Loading...'
                                : isSettingsOpen
                                  ? 'Close setup'
                                  : 'Open setup'}
                            </button>
                          </div>

                          {isSettingsOpen ? (
                            <div className="mt-4 rounded-xl border border-gray-200 bg-white p-4">
                              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <h4 className="text-sm font-semibold text-gray-900">Project settings</h4>
                                  <p className="mt-1 text-sm text-gray-500">
                                    manifest 이전 단계에서 쓰는 platform-side 준비 정보만 저장합니다.
                                  </p>
                                </div>
                                <span
                                  className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-semibold ${configurationBadgeClassName}`}
                                >
                                  {configurationLabel}
                                </span>
                              </div>

                              <div className="mt-4 space-y-4">
                                <label className="flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700">
                                  <input
                                    type="checkbox"
                                    name="staging_enabled"
                                    checked={settingsForm.staging_enabled}
                                    onChange={handleSettingsFormChange}
                                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600"
                                  />
                                  <span>
                                    <span className="block font-medium text-gray-900">Enable staging flow</span>
                                    <span className="mt-1 block text-gray-500">
                                      나중에 staging 배포 대상으로 진행할 프로젝트인지 표시합니다.
                                    </span>
                                  </span>
                                </label>

                                <label className="flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700">
                                  <input
                                    type="checkbox"
                                    name="ready_for_bootstrap"
                                    checked={settingsForm.ready_for_bootstrap}
                                    onChange={handleSettingsFormChange}
                                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600"
                                  />
                                  <span>
                                    <span className="block font-medium text-gray-900">Ready for bootstrap</span>
                                    <span className="mt-1 block text-gray-500">
                                      기본 설정 검토가 끝나 다음 bootstrap 단계로 넘길 수 있음을 표시합니다.
                                    </span>
                                  </span>
                                </label>

                                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                                  <label className="flex items-start gap-3 text-sm text-gray-700">
                                    <input
                                      type="checkbox"
                                      name="database_required"
                                      checked={settingsForm.database_required}
                                      onChange={handleSettingsFormChange}
                                      className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600"
                                    />
                                    <span>
                                      <span className="block font-medium text-gray-900">Database required</span>
                                      <span className="mt-1 block text-gray-500">
                                        staging 배포 전에 플랫폼 DB 자동화가 필요한 프로젝트인지 표시합니다.
                                      </span>
                                    </span>
                                  </label>

                                  {settingsForm.database_required ? (
                                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                                      <label className="space-y-2">
                                        <span className="text-sm font-medium text-gray-700">Database engine</span>
                                        <select
                                          name="database_engine"
                                          value={settingsForm.database_engine}
                                          onChange={handleSettingsFormChange}
                                          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                                        >
                                          <option value="postgres">postgres</option>
                                        </select>
                                      </label>

                                      <label className="space-y-2">
                                        <span className="text-sm font-medium text-gray-700">Database mode</span>
                                        <select
                                          name="database_mode"
                                          value={settingsForm.database_mode}
                                          onChange={handleSettingsFormChange}
                                          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                                        >
                                          <option value="shared-cluster">shared-cluster</option>
                                          <option value="dedicated-instance">dedicated-instance</option>
                                        </select>
                                      </label>

                                      <label className="space-y-2 md:col-span-2">
                                        <span className="text-sm font-medium text-gray-700">Migration command</span>
                                        <input
                                          type="text"
                                          name="migration_command"
                                          value={settingsForm.migration_command}
                                          onChange={handleSettingsFormChange}
                                          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                                          placeholder="npm run migrate 또는 alembic upgrade head"
                                        />
                                      </label>
                                    </div>
                                  ) : null}
                                </div>

                                <div className="grid gap-4 md:grid-cols-2">
                                  <label className="space-y-2">
                                    <span className="text-sm font-medium text-gray-700">Deploy branch</span>
                                    <input
                                      type="text"
                                      name="deploy_branch"
                                      value={settingsForm.deploy_branch}
                                      onChange={handleSettingsFormChange}
                                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                                      placeholder="main"
                                    />
                                  </label>

                                  <label className="space-y-2">
                                    <span className="text-sm font-medium text-gray-700">Bootstrap strategy</span>
                                    <select
                                      name="bootstrap_strategy"
                                      value={settingsForm.bootstrap_strategy}
                                      onChange={handleSettingsFormChange}
                                      className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                                    >
                                      <option value="merge_request">merge_request</option>
                                      <option value="direct_commit">direct_commit</option>
                                      <option value="manual">manual</option>
                                    </select>
                                  </label>
                                </div>

                                <label className="block space-y-2">
                                  <span className="text-sm font-medium text-gray-700">Notes</span>
                                  <textarea
                                    name="notes"
                                    value={settingsForm.notes}
                                    onChange={handleSettingsFormChange}
                                    rows={3}
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-blue-400"
                                    placeholder="bootstrap 전에 기억해둘 메모를 남깁니다."
                                  />
                                </label>

                                {settingsError ? (
                                  <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                                    {settingsError}
                                  </div>
                                ) : null}

                                <div className="flex items-center justify-between gap-4 border-t border-gray-200 pt-4">
                                  <p className="text-sm text-gray-500">
                                    실제 bootstrap/staging 실행은 아직 없고, 지금은 준비 정보만 저장합니다.
                                  </p>
                                  <button
                                    type="button"
                                    onClick={() => handleSaveSettings(project.gitlab_project_id)}
                                    disabled={settingsSavingProjectId === project.gitlab_project_id}
                                    className="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-white px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:border-blue-400 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                                  >
                                    <RefreshCw className={`h-4 w-4 ${settingsSavingProjectId === project.gitlab_project_id ? 'animate-spin' : ''}`} />
                                    Save settings
                                  </button>
                                </div>
                              </div>
                            </div>
                          ) : null}
                        </article>
                      )
                    })}
                  </div>
                )}
              </div>
            </section>
          </section>
        </div>
      )}
    </div>
  )
}

export default GitLabWorkspace
