import { useState } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import GitLabWorkspace from './components/GitLabWorkspace'
import InstanceList from './components/InstanceList'
import MonitoringDashboard from './components/MonitoringDashboard'
import LlmInfraChat from './components/LlmInfraChat'
import TaskBoard from './components/TaskBoard'
import OverviewDashboard from './components/OverviewDashboard'
import { Server, List, Activity, Sparkles, Clock3, GitBranch, LayoutDashboard } from 'lucide-react'

const getActiveTab = (pathname) => {
  if (pathname === '/') return 'overview'
  if (pathname.startsWith('/list')) return 'list'
  if (pathname.startsWith('/tasks')) return 'tasks'
  if (pathname.startsWith('/gitlab')) return 'gitlab'
  if (pathname.startsWith('/monitoring')) return 'monitoring'
  if (pathname.startsWith('/assistant')) return 'assistant'
  return 'overview'
}

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const activeTab = getActiveTab(location.pathname)
  const [status, setStatus] = useState('idle')
  const [logs, setLogs] = useState([])
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="container mx-auto px-8 py-5">
          <div className="flex items-center gap-3">
            <Server className="w-8 h-8 text-blue-600" />
            <h1 className="text-2xl font-semibold text-gray-900">Infrastructure Control Plane</h1>
          </div>
        </div>
      </header>

      {/* Tabs Navigation */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="container mx-auto px-8">
          <div className="flex overflow-x-auto">
            <button
              onClick={() => navigate('/')}
              className={`flex shrink-0 items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'overview'
                  ? 'text-slate-900 border-slate-900 bg-slate-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <LayoutDashboard className="w-5 h-5" />
              Overview
            </button>
            <button
              onClick={() => navigate('/list')}
              className={`flex shrink-0 items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'list'
                  ? 'text-blue-600 border-blue-600 bg-blue-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <List className="w-5 h-5" />
              Instance List
            </button>
            <button
              onClick={() => navigate('/tasks')}
              className={`flex shrink-0 items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'tasks'
                  ? 'text-blue-600 border-blue-600 bg-blue-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Clock3 className="w-5 h-5" />
              Task Board
            </button>
            <button
              onClick={() => navigate('/gitlab')}
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'gitlab'
                  ? 'text-blue-600 border-blue-600 bg-blue-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <GitBranch className="w-5 h-5" />
              GitLab
            </button>
            <button
              onClick={() => navigate('/monitoring')}
              className={`flex shrink-0 items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'monitoring'
                  ? 'text-blue-600 border-blue-600 bg-blue-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Activity className="w-5 h-5" />
              Monitoring
            </button>
            <button
              onClick={() => navigate('/assistant')}
              className={`flex shrink-0 items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'assistant'
                  ? 'text-orange-600 border-orange-600 bg-orange-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Sparkles className="w-5 h-5" />
              LLM Assistant
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="container mx-auto px-8 py-8">
        <Routes>
          {/* Overview Route */}
          <Route
            path="/"
            element={<OverviewDashboard onNavigate={navigate} />}
          />

          {/* Instance List Route */}
          <Route
            path="/list"
            element={
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                <InstanceList onLogsUpdate={setLogs} onStatusChange={setStatus} />
              </div>
            }
          />

          {/* Task Board Route */}
          <Route
            path="/tasks"
            element={
              <TaskBoard focusTaskId={location.state?.focusTaskId} />
            }
          />

          {/* GitLab Workspace Route */}
          <Route
            path="/gitlab"
            element={<GitLabWorkspace />}
          />

          {/* Monitoring Dashboard Route */}
          <Route
            path="/monitoring"
            element={
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                <MonitoringDashboard />
              </div>
            }
          />

          {/* LLM Assistant Route */}
          <Route
            path="/assistant"
            element={
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
                <LlmInfraChat />
              </div>
            }
          />

        </Routes>
      </main>
    </div>
  )
}

export default App
