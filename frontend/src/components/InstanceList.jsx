import { useState, useEffect } from 'react'
import { Server, Cpu, HardDrive, Trash2, RefreshCw, Loader2, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react'
import { getInstances, getServers, destroyInfrastructure } from '../services/api'

function InstanceList({ onLogsUpdate, onStatusChange }) {
  const [instances, setInstances] = useState([])
  const [servers, setServers] = useState([])
  const [groupedInstances, setGroupedInstances] = useState({})
  const [expandedServers, setExpandedServers] = useState(new Set())
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
      
      // 서버 목록과 인스턴스 목록을 동시에 가져오기
      const [instancesResponse, serversResponse] = await Promise.all([
        getInstances(),
        getServers()
      ])
      
      const instancesList = instancesResponse.data?.vms || instancesResponse.data?.instances || instancesResponse.data || []
      const serversList = serversResponse.data?.servers || serversResponse.data || []
      
      setInstances(instancesList)
      setServers(serversList)
      
      // 서버 목록을 이름순으로 정렬하여 일정한 순서 유지
      const sortedServers = [...serversList].sort((a, b) => {
        const nameA = (a.name || a.server_name || a.server_id || a.id || '').toLowerCase()
        const nameB = (b.name || b.server_name || b.server_id || b.id || '').toLowerCase()
        return nameA.localeCompare(nameB)
      })
      
      // 서버별로 인스턴스 그룹화
      const grouped = {}
      sortedServers.forEach(server => {
        const serverId = server.server_id || server.id
        grouped[serverId] = {
          server: server,
          instances: []
        }
      })
      
      instancesList.forEach(instance => {
        const node = instance.node || instance.server_id
        if (node && grouped[node]) {
          grouped[node].instances.push(instance)
        } else {
          // 노드 정보가 없으면 'Unknown' 그룹에 추가
          if (!grouped['Unknown']) {
            grouped['Unknown'] = {
              server: { server_id: 'Unknown', name: 'Unknown', status: 'unknown' },
              instances: []
            }
          }
          grouped['Unknown'].instances.push(instance)
        }
      })
      
      // 각 서버의 인스턴스 정렬: 상태(running 우선) → 이름순
      Object.keys(grouped).forEach(serverId => {
        grouped[serverId].instances.sort((a, b) => {
          // 상태 우선순위: running > stopped > 기타
          const statusOrder = { 'running': 0, 'stopped': 1 }
          const statusA = (a.status || '').toLowerCase()
          const statusB = (b.status || '').toLowerCase()
          const statusPriorityA = statusOrder[statusA] !== undefined ? statusOrder[statusA] : 2
          const statusPriorityB = statusOrder[statusB] !== undefined ? statusOrder[statusB] : 2
          
          // 상태가 다르면 상태 우선순위로 정렬
          if (statusPriorityA !== statusPriorityB) {
            return statusPriorityA - statusPriorityB
          }
          
          // 상태가 같으면 이름순으로 정렬
          const nameA = (a.name || a.server_name || `vm-${a.vmid || ''}`).toLowerCase()
          const nameB = (b.name || b.server_name || `vm-${b.vmid || ''}`).toLowerCase()
          return nameA.localeCompare(nameB)
        })
      })
      
      setGroupedInstances(grouped)
      
      // 처음 로드 시 모든 서버를 확장 상태로 설정
      if (expandedServers.size === 0) {
        setExpandedServers(new Set(Object.keys(grouped)))
      }
      
      const totalInstances = instancesList.length
      addLog(`Loaded ${totalInstances} instances across ${serversList.length} servers`, 'success')
    } catch (error) {
      console.error('Failed to fetch instances:', error)
      addLog(`Failed to load instances: ${error.message}`, 'error')
      setInstances([])
      setServers([])
      setGroupedInstances({})
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

  const toggleServer = (serverId) => {
    setExpandedServers(prev => {
      const newSet = new Set(prev)
      if (newSet.has(serverId)) {
        newSet.delete(serverId)
      } else {
        newSet.add(serverId)
      }
      return newSet
    })
  }

  return (
    <div className="p-6">
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
        ) : Object.keys(groupedInstances).length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <AlertCircle className="w-12 h-12 text-gray-400 mb-4" />
            <p className="text-gray-600 font-medium">No instances found</p>
            <p className="text-sm text-gray-500 mt-1">Create a new instance to get started</p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedInstances)
              .sort(([idA], [idB]) => {
                // Unknown은 맨 뒤로
                if (idA === 'Unknown') return 1
                if (idB === 'Unknown') return -1
                // 서버 이름순으로 정렬
                const nameA = (groupedInstances[idA]?.server?.name || idA).toLowerCase()
                const nameB = (groupedInstances[idB]?.server?.name || idB).toLowerCase()
                return nameA.localeCompare(nameB)
              })
              .map(([serverId, group]) => {
              const isExpanded = expandedServers.has(serverId)
              const server = group.server
              const serverInstances = group.instances
              const serverStatus = server.status === 'online' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
              
              return (
                <div key={serverId} className="border border-gray-200 rounded-lg overflow-hidden">
                  {/* 서버 헤더 */}
                  <div 
                    className="bg-gray-50 px-4 py-3 cursor-pointer hover:bg-gray-100 transition-colors flex items-center justify-between"
                    onClick={() => toggleServer(serverId)}
                  >
                    <div className="flex items-center gap-3">
                      {isExpanded ? (
                        <ChevronDown className="w-5 h-5 text-gray-500" />
                      ) : (
                        <ChevronRight className="w-5 h-5 text-gray-500" />
                      )}
                      <Server className="w-5 h-5 text-blue-600" />
                      <div>
                        <div className="font-semibold text-gray-900">{server.name || server.server_id}</div>
                        <div className="text-xs text-gray-500 mt-0.5">
                          {serverInstances.length} instance{serverInstances.length !== 1 ? 's' : ''}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 text-xs font-semibold rounded ${serverStatus}`}>
                        {server.status || 'unknown'}
                      </span>
                    </div>
                  </div>
                  
                  {/* VM 목록 */}
                  {isExpanded && (
                    <div className="overflow-x-auto">
                      {serverInstances.length === 0 ? (
                        <div className="px-4 py-8 text-center text-gray-500 text-sm">
                          No instances on this server
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full table-fixed">
                            <colgroup>
                              <col className="w-[200px]" /> {/* Name - 고정 너비 */}
                              <col className="w-[100px]" /> {/* Status - 고정 너비 */}
                              <col className="w-[90px]" /> {/* CPU - 고정 너비 */}
                              <col className="w-[100px]" /> {/* Memory - 고정 너비 */}
                              <col className="w-[200px]" /> {/* Disk - 고정 너비 */}
                              <col className="w-[120px]" /> {/* Actions - 고정 너비 */}
                            </colgroup>
                            <thead>
                              <tr className="border-b border-gray-200 bg-gray-50">
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
                                <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Disk</th>
                                <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {serverInstances.map((instance, index) => {
                                const instanceName = instance.name || instance.server_name || `VM ${instance.vmid || ''}`
                                return (
                                  <tr
                                    key={instance.id || instance.vm_id || index}
                                    className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                                  >
                                    <td className="py-4 px-4">
                                      <div 
                                        className="font-medium text-gray-900 truncate" 
                                        title={instanceName}
                                      >
                                        {instanceName}
                                      </div>
                                      {instance.vmid && (
                                        <div className="text-xs text-gray-500 mt-0.5 truncate">ID: {instance.vmid}</div>
                                      )}
                                    </td>
                                    <td className="py-4 px-4">
                                      <div className="flex-shrink-0">
                                        {getStatusBadge(instance.status)}
                                      </div>
                                    </td>
                                    <td className="py-4 px-4 text-sm text-gray-600 whitespace-nowrap">
                                      {instance.cpu_cores || instance.cpu || '-'} cores
                                    </td>
                                    <td className="py-4 px-4 text-sm text-gray-600 whitespace-nowrap">
                                      {instance.memory_gb || instance.memory || '-'} GB
                                    </td>
                                    <td className="py-4 px-4 text-sm text-gray-600">
                                      {instance.disks && instance.disks.length > 0 ? (
                                        <div className="space-y-1">
                                          {instance.disks.map((disk, idx) => (
                                            <div key={idx} className="text-xs truncate" title={`${disk.device}: ${disk.size_gb} GB${disk.storage !== 'unknown' ? ` (${disk.storage})` : ''}`}>
                                              {disk.device}: {disk.size_gb} GB
                                              {disk.storage !== 'unknown' && (
                                                <span className="text-gray-400 ml-1">({disk.storage})</span>
                                              )}
                                            </div>
                                          ))}
                                          {instance.disks.length > 1 && (
                                            <div className="text-xs font-semibold text-gray-700 pt-1 border-t border-gray-200">
                                              총: {instance.disk_gb || instance.disks.reduce((sum, d) => sum + d.size_gb, 0).toFixed(2)} GB
                                            </div>
                                          )}
                                        </div>
                                      ) : instance.disk_gb ? (
                                        `${instance.disk_gb} GB`
                                      ) : (
                                        '-'
                                      )}
                                    </td>
                                    <td className="py-4 px-4">
                                      <div className="flex justify-end">
                                        <button
                                          onClick={() => handleDestroy(instance.name || instance.server_name)}
                                          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 rounded-md transition-colors whitespace-nowrap"
                                        >
                                          <Trash2 className="w-4 h-4" />
                                          Terminate
                                        </button>
                                      </div>
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default InstanceList
