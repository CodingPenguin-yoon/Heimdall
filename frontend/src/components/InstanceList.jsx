import { useState, useEffect } from 'react'
import { Server, Cpu, HardDrive, Trash2, RefreshCw, Loader2, AlertCircle } from 'lucide-react'
import { getInstances, destroyInfrastructure } from '../services/api'

function InstanceList({ onLogsUpdate, onStatusChange }) {
  const [instances, setInstances] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString()
    onLogsUpdate((prev) => [
      ...prev,
      { timestamp, message, type },
    ])
  }

  const fetchInstances = async () => {
    try {
      setRefreshing(true)
      const response = await getInstances()
      setInstances(response.data?.instances || response.data || [])
      addLog(`Loaded ${response.data?.instances?.length || response.data?.length || 0} instances`, 'success')
    } catch (error) {
      console.error('Failed to fetch instances:', error)
      addLog(`Failed to load instances: ${error.message}`, 'error')
      // 에러 발생 시 빈 배열로 설정
      setInstances([])
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchInstances()
    // 30초마다 자동 새로고침
    const interval = setInterval(fetchInstances, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleDestroy = async (serverName) => {
    if (!confirm(`Are you sure you want to terminate instance "${serverName}"?`)) {
      return
    }

    try {
      onStatusChange('destroying')
      addLog(`Terminating instance: ${serverName}...`, 'info')
      await destroyInfrastructure(serverName)
      addLog(`Instance "${serverName}" terminated successfully`, 'success')
      onStatusChange('idle')
      // 목록 새로고침
      await fetchInstances()
    } catch (error) {
      addLog(`Failed to terminate instance: ${error.message}`, 'error')
      onStatusChange('error')
    }
  }

  const getStatusBadge = (status) => {
    const statusConfig = {
      running: { color: 'bg-green-100 text-green-800 border-green-200', label: 'Running' },
      stopped: { color: 'bg-gray-100 text-gray-800 border-gray-200', label: 'Stopped' },
      deploying: { color: 'bg-blue-100 text-blue-800 border-blue-200', label: 'Deploying' },
      failed: { color: 'bg-red-100 text-red-800 border-red-200', label: 'Failed' },
    }
    const config = statusConfig[status?.toLowerCase()] || statusConfig.stopped
    return (
      <span className={`px-2 py-1 text-xs font-semibold rounded border ${config.color}`}>
        {config.label}
      </span>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-600" />
            Instances
          </h2>
          <p className="text-sm text-gray-500 mt-1">Manage your infrastructure instances</p>
        </div>
        <button
          onClick={fetchInstances}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Content */}
      <div>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
            <span className="ml-3 text-gray-600">Loading instances...</span>
          </div>
        ) : instances.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <AlertCircle className="w-12 h-12 text-gray-400 mb-4" />
            <p className="text-gray-600 font-medium">No instances found</p>
            <p className="text-sm text-gray-500 mt-1">Create a new instance to get started</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Name</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                    <Cpu className="w-4 h-4 inline mr-1" />
                    CPU
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                    <HardDrive className="w-4 h-4 inline mr-1" />
                    Memory
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Region</th>
                  <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {instances.map((instance, index) => (
                  <tr
                    key={instance.id || instance.server_name || index}
                    className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                  >
                    <td className="py-4 px-4">
                      <div className="font-medium text-gray-900">
                        {instance.server_name || instance.name || 'Unknown'}
                      </div>
                    </td>
                    <td className="py-4 px-4">{getStatusBadge(instance.status)}</td>
                    <td className="py-4 px-4 text-sm text-gray-600">
                      {instance.cpu_cores || instance.cpu || '-'} cores
                    </td>
                    <td className="py-4 px-4 text-sm text-gray-600">
                      {instance.memory_gb || instance.memory || '-'} GB
                    </td>
                    <td className="py-4 px-4 text-sm text-gray-600">
                      {instance.region || '-'}
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex justify-end">
                        <button
                          onClick={() => handleDestroy(instance.server_name || instance.name)}
                          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 rounded-md transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                          Terminate
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default InstanceList
