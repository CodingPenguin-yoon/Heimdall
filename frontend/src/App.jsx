import { useState } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import CreateInstanceWizard from './components/CreateInstanceWizard'
import ControlCenter from './components/ControlCenter'
import InstanceList from './components/InstanceList'
import MonitoringDashboard from './components/MonitoringDashboard'
import StatusPanel from './components/StatusPanel'
import LogViewer from './components/LogViewer'
import LlmInfraChat from './components/LlmInfraChat'
import { Server, List, Plus, Activity, Sparkles } from 'lucide-react'
import { deployInfrastructure, checkStatus, getLogs } from './services/api'

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const activeTab = location.pathname === '/' ? 'create' : location.pathname.replace('/', '')
  const [deployConfig, setDeployConfig] = useState({
    selectedServerId: '',
    selectedTemplateId: '',
    cpuCores: '',
    memory: '',
    selectedStorageId: '',
    selectedNetworkIds: [],
    serverName: '',
    selectedPackages: [],
    selectedRoles: [],
  })
  const [status, setStatus] = useState('idle')
  const [logs, setLogs] = useState([])

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs((prev) => [...prev, { timestamp, message, type }])
  }

  const startPolling = async (taskId) => {
    let lastLogCount = 0
    
    const pollInterval = setInterval(async () => {
      try {
        // 상태 확인
        const statusResponse = await checkStatus(taskId)
        const currentStatus = statusResponse.data?.status || statusResponse.status

        // 로그 조회 및 업데이트
        try {
          const logsResponse = await getLogs(taskId)
          const logs = logsResponse.data?.logs || []
          
          // 새로운 로그만 추가
          if (logs.length > lastLogCount) {
            const newLogs = logs.slice(lastLogCount)
            newLogs.forEach((logLine) => {
              // 로그 타입 판단 (ERROR, EXCEPTION 등 키워드 기반)
              let logType = 'info'
              if (logLine.includes('ERROR') || logLine.includes('EXCEPTION') || logLine.includes('실패')) {
                logType = 'error'
              } else if (logLine.includes('경고') || logLine.includes('WARNING')) {
                logType = 'warning'
              } else if (logLine.includes('완료') || logLine.includes('SUCCESS')) {
                logType = 'success'
              }
              
              // 타임스탬프 제거 (이미 포함되어 있음)
              const message = logLine.replace(/^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] /, '')
              addLog(message, logType)
            })
            lastLogCount = logs.length
          }
        } catch (logError) {
          // 로그 조회 실패는 무시 (상태는 계속 확인)
          console.warn('Log fetch error:', logError)
        }

        // 상태 업데이트
        if (currentStatus === 'Success' || currentStatus === 'success' || currentStatus === 'completed') {
          clearInterval(pollInterval)
          setStatus('success')
          addLog('Deployment completed successfully!', 'success')
        } else if (currentStatus === 'Failed' || currentStatus === 'failed' || currentStatus === 'error') {
          clearInterval(pollInterval)
          setStatus('failed')
          addLog('Deployment failed!', 'error')
        } else {
          setStatus(currentStatus.toLowerCase())
        }
      } catch (error) {
        addLog(`Polling error: ${error.message}`, 'error')
        clearInterval(pollInterval)
        setStatus('error')
      }
    }, 2000) // 2초 간격으로 폴링 (더 빠른 실시간 업데이트)

    // 최대 10분 후 타임아웃
    setTimeout(() => {
      clearInterval(pollInterval)
    }, 600000)
  }

  const handleDeploy = async () => {
    if (
      !deployConfig.selectedServerId ||
      !deployConfig.selectedStorageId ||
      !deployConfig.selectedNetworkIds?.length ||
      (!deployConfig.selectedTemplateId && (!deployConfig.cpuCores || !deployConfig.memory))
    ) {
      addLog('Please complete all steps before deploying', 'error')
      return
    }

    setStatus('deploying')
    addLog('Starting deployment...', 'info')

    try {
      const response = await deployInfrastructure({
        server_id: deployConfig.selectedServerId,
        template_id: deployConfig.selectedTemplateId || undefined,
        iso_image_id: deployConfig.selectedISOImageId || undefined,
        cpu_cores: deployConfig.cpuCores ? parseInt(deployConfig.cpuCores) : undefined,
        memory_gb: deployConfig.memory ? parseInt(deployConfig.memory) : undefined,
        storage_id: deployConfig.selectedStorageId,
        network_ids: deployConfig.selectedNetworkIds,
        server_name: deployConfig.serverName || `instance-${Date.now()}`,
        ansible_packages: deployConfig.selectedPackages || [],
        ansible_roles: deployConfig.selectedRoles || [],
      })
      const taskId = response.data?.task_id || response.data?.id

      if (!taskId) {
        throw new Error('Task ID를 받지 못했습니다.')
      }

      addLog(`Deployment initiated. Task ID: ${taskId}`, 'success')
      addLog('Starting real-time log polling...', 'info')

      await startPolling(taskId)
    } catch (error) {
      setStatus('error')
      const errorMessage = error.response?.data?.detail || error.message || '알 수 없는 오류가 발생했습니다.'
      addLog(`Deployment error: ${errorMessage}`, 'error')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="container mx-auto px-8 py-5">
          <div className="flex items-center gap-3">
            <Server className="w-8 h-8 text-blue-600" />
            <h1 className="text-2xl font-semibold text-gray-900">Infrastructure Control Dashboard</h1>
          </div>
        </div>
      </header>

      {/* Tabs Navigation */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="container mx-auto px-8">
          <div className="flex">
            <button
              onClick={() => navigate('/list')}
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'list'
                  ? 'text-blue-600 border-blue-600 bg-blue-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <List className="w-5 h-5" />
              Instance List
            </button>
            <button
              onClick={() => navigate('/')}
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'create' || location.pathname === '/'
                  ? 'text-blue-600 border-blue-600 bg-blue-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Plus className="w-5 h-5" />
              Create Instance
            </button>
            <button
              onClick={() => navigate('/monitoring')}
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
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
              className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors border-b-2 ${
                activeTab === 'assistant'
                  ? 'text-purple-600 border-purple-600 bg-purple-50'
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
          {/* Instance List Route */}
          <Route
            path="/list"
            element={
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                <InstanceList onLogsUpdate={setLogs} onStatusChange={setStatus} />
              </div>
            }
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

          {/* Create Instance Route (Default) */}
          <Route
            path="/"
            element={
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Left Column */}
                <div className="space-y-6">
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                    <div className="p-6">
                      <CreateInstanceWizard
                        config={deployConfig}
                        onConfigChange={setDeployConfig}
                        onDeploy={handleDeploy}
                      />
                    </div>
                  </div>
                </div>

                {/* Right Column */}
                <div className="space-y-6">
                  <StatusPanel status={status} />
                  <LogViewer logs={logs} />
                </div>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  )
}

export default App
