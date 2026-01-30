import axios from 'axios'

// API 기본 URL 설정 (프록시를 통해 /api로 요청)
const API_BASE_URL = '/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30초 타임아웃
})

// 요청 인터셉터: API 호출 URL 로깅
apiClient.interceptors.request.use(
  (config) => {
    const fullUrl = `${config.baseURL}${config.url}`
    console.log(`[API Request] ${config.method?.toUpperCase()} ${fullUrl}`)
    if (config.params) {
      console.log('[API Params]', config.params)
    }
    if (config.data) {
      console.log('[API Data]', config.data)
    }
    return config
  },
  (error) => {
    console.error('[API Request Error]', error)
    return Promise.reject(error)
  }
)

// 응답 인터셉터: 응답 로깅
apiClient.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.config.method?.toUpperCase()} ${response.config.url}`, response.status, response.data)
    return response
  },
  (error) => {
    console.error(`[API Error] ${error.config?.method?.toUpperCase()} ${error.config?.url}`, error.response?.status, error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// 배포 시작 API
export const deployInfrastructure = async (config) => {
  try {
    // 새로운 마법사 스타일 config 또는 기존 config 모두 지원
    const payload = config.server_id
      ? {
          server_id: config.server_id,
          template_id: config.template_id,
          storage_id: config.storage_id,
          storage_type: config.storage_type,
          network_ids: config.network_ids,
          server_name: config.server_name,
          cpu_cores: config.cpu_cores,
          memory_gb: config.memory_gb,
          disk_size_gb: config.disk_size_gb || 50,
          ansible_packages: config.ansible_packages || [],
          ansible_roles: config.ansible_roles || [],
        }
      : {
          server_id: config.selectedServerId,
          template_id: config.selectedTemplateId,
          server_name: config.serverName || `instance-${Date.now()}`,
          cpu_cores: config.cpuCores ? parseInt(config.cpuCores) : undefined,
          memory_gb: config.memory ? parseInt(config.memory) : undefined,
          disk_size_gb: parseInt(config.diskSize) || 50,
          storage_id: config.selectedStorageId,
          network_ids: config.selectedNetworkIds || [],
          ansible_packages: config.selectedPackages || [],
          ansible_roles: config.selectedRoles || [],
        }
    const response = await apiClient.post('/deploy', payload)
    return response
  } catch (error) {
    console.error('Deploy API error:', error)
    throw error
  }
}

// 자원 회수 API
export const destroyInfrastructure = async (serverName) => {
  try {
    const response = await apiClient.post('/destroy', {
      server_name: serverName,
    })
    return response
  } catch (error) {
    console.error('Destroy API error:', error)
    throw error
  }
}

// 상태 확인 API
export const checkStatus = async (taskId) => {
  try {
    const response = await apiClient.get(`/status/${taskId}`)
    return response
  } catch (error) {
    console.error('Status API error:', error)
    throw error
  }
}

// 로그 조회 API
export const getLogs = async (taskId) => {
  try {
    const response = await apiClient.get(`/logs/${taskId}`)
    return response
  } catch (error) {
    console.error('Logs API error:', error)
    throw error
  }
}

// 인스턴스 목록 조회 API
export const getInstances = async () => {
  try {
    const response = await apiClient.get('/instances')
    return response
  } catch (error) {
    console.error('Get instances API error:', error)
    throw error
  }
}

// 서버/템플릿 목록 조회 API
export const getServers = async () => {
  try {
    const response = await apiClient.get('/servers')
    return response
  } catch (error) {
    console.error('Get servers API error:', error)
    throw error
  }
}

// 템플릿 목록 조회 API
export const getTemplates = async () => {
  try {
    const response = await apiClient.get('/templates')
    return response
  } catch (error) {
    console.error('Get templates API error:', error)
    throw error
  }
}

// 서버의 스토리지 목록 조회 API
export const getServerStorage = async (serverId) => {
  try {
    const response = await apiClient.get(`/servers/${serverId}/storage`)
    return response
  } catch (error) {
    console.error('Get server storage API error:', error)
    throw error
  }
}

// 서버의 네트워크 목록 조회 API
export const getServerNetworks = async (serverId) => {
  try {
    const response = await apiClient.get(`/servers/${serverId}/networks`)
    return response
  } catch (error) {
    console.error('Get server networks API error:', error)
    throw error
  }
}

// VM 목록 조회 API (템플릿 제외)
export const getVMs = async () => {
  try {
    const response = await apiClient.get('/vms')
    return response
  } catch (error) {
    console.error('Get VMs API error:', error)
    throw error
  }
}

// 서버의 ISO 이미지 목록 조회 API
export const getServerISOImages = async (serverId) => {
  try {
    const response = await apiClient.get(`/servers/${serverId}/iso-images`)
    return response
  } catch (error) {
    console.error('Get server ISO images API error:', error)
    throw error
  }
}

// 서버의 VM 목록 조회 API
export const getServerVMs = async (serverId) => {
  try {
    const response = await apiClient.get(`/servers/${serverId}/vms`)
    return response
  } catch (error) {
    console.error('Get server VMs API error:', error)
    throw error
  }
}

// 모니터링 API
export const getNodesMonitoring = async () => {
  try {
    const response = await apiClient.get('/monitoring/nodes')
    return response
  } catch (error) {
    console.error('Get nodes monitoring API error:', error)
    throw error
  }
}

export const getNodeMonitoring = async (nodeId) => {
  try {
    const response = await apiClient.get(`/monitoring/nodes/${nodeId}`)
    return response
  } catch (error) {
    console.error('Get node monitoring API error:', error)
    throw error
  }
}

export const getVMMonitoring = async (nodeId, vmid) => {
  try {
    const response = await apiClient.get(`/monitoring/vms/${nodeId}/${vmid}`)
    return response
  } catch (error) {
    console.error('Get VM monitoring API error:', error)
    throw error
  }
}

export default apiClient
