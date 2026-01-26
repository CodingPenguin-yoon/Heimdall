import { useState } from 'react'
import { Play, Trash2, Loader2 } from 'lucide-react'
import { deployInfrastructure, destroyInfrastructure, checkStatus, getLogs } from '../services/api'

function ControlCenter({ config, status, onStatusChange, onLogsUpdate }) {
  const [isProcessing, setIsProcessing] = useState(false)

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString()
    onLogsUpdate((prev) => [
      ...prev,
      { timestamp, message, type },
    ])
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
              // 로그 타입 판단
              let logType = 'info'
              if (logLine.includes('ERROR') || logLine.includes('EXCEPTION') || logLine.includes('실패')) {
                logType = 'error'
              } else if (logLine.includes('경고') || logLine.includes('WARNING')) {
                logType = 'warning'
              } else if (logLine.includes('완료') || logLine.includes('SUCCESS')) {
                logType = 'success'
              }
              
              const message = logLine.replace(/^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] /, '')
              addLog(message, logType)
            })
            lastLogCount = logs.length
          }
        } catch (logError) {
          console.warn('Log fetch error:', logError)
        }

        // 상태 업데이트
        if (currentStatus === 'Success' || currentStatus === 'success' || currentStatus === 'completed') {
          clearInterval(pollInterval)
          onStatusChange('success')
          setIsProcessing(false)
          addLog('Deployment completed successfully!', 'success')
        } else if (currentStatus === 'Failed' || currentStatus === 'failed' || currentStatus === 'error') {
          clearInterval(pollInterval)
          onStatusChange('failed')
          setIsProcessing(false)
          addLog('Deployment failed!', 'error')
        } else {
          onStatusChange(currentStatus.toLowerCase())
        }
      } catch (error) {
        addLog(`Polling error: ${error.message}`, 'error')
        clearInterval(pollInterval)
        setIsProcessing(false)
        onStatusChange('error')
      }
    }, 2000) // 2초 간격

    // 최대 10분 후 타임아웃
    setTimeout(() => {
      clearInterval(pollInterval)
      if (isProcessing) {
        setIsProcessing(false)
        addLog('Polling timeout after 10 minutes', 'warning')
      }
    }, 600000)
  }

  const handleDeploy = async () => {
    if (!config.serverName || !config.cpuCores || !config.memory || !config.diskSize) {
      addLog('Please fill in all required fields', 'error')
      return
    }

    setIsProcessing(true)
    onStatusChange('deploying')
    addLog('Starting deployment...', 'info')

    try {
      const response = await deployInfrastructure(config)
      const taskId = response.data?.task_id || response.data?.id

      if (!taskId) {
        throw new Error('Task ID를 받지 못했습니다.')
      }

      addLog(`Deployment initiated. Task ID: ${taskId}`, 'success')
      addLog('Starting real-time log polling...', 'info')

      // 폴링 시작
      await startPolling(taskId)
    } catch (error) {
      setIsProcessing(false)
      onStatusChange('error')
      const errorMessage = error.response?.data?.detail || error.message || '알 수 없는 오류가 발생했습니다.'
      addLog(`Deployment error: ${errorMessage}`, 'error')
    }
  }

  const handleDestroy = async () => {
    if (!config.serverName) {
      addLog('Server name is required for destroy operation', 'error')
      return
    }

    setIsProcessing(true)
    onStatusChange('destroying')
    addLog('Starting resource destruction...', 'info')

    try {
      const response = await destroyInfrastructure(config.serverName)
      addLog('Resources destroyed successfully', 'success')
      onStatusChange('idle')
      setIsProcessing(false)
    } catch (error) {
      setIsProcessing(false)
      onStatusChange('error')
      addLog(`Destroy error: ${error.message}`, 'error')
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Actions</h2>
        <p className="text-sm text-gray-500 mt-1">Deploy or destroy infrastructure instances</p>
      </div>

      <div className="p-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleDeploy}
            disabled={isProcessing || status === 'deploying'}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed rounded-md font-medium text-white transition-colors shadow-sm"
          >
            {isProcessing && status === 'deploying' ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Deploying...
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                Launch Instance
              </>
            )}
          </button>

          <button
            onClick={handleDestroy}
            disabled={isProcessing || status === 'destroying'}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-red-600 hover:bg-red-700 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed rounded-md font-medium text-white transition-colors shadow-sm"
          >
            {isProcessing && status === 'destroying' ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Destroying...
              </>
            ) : (
              <>
                <Trash2 className="w-5 h-5" />
                Terminate Instance
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ControlCenter
