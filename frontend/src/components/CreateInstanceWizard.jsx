import { useState, useEffect } from 'react'
import { Server, Cpu, Network, ChevronRight, CheckCircle2, Loader2, HardDrive, Package } from 'lucide-react'
import { getServers, getTemplates, getServerStorage, getServerNetworks } from '../services/api'

const STEPS = [
  { id: 1, name: 'Server & Template', icon: Server },
  { id: 2, name: 'Spec & Storage', icon: Cpu },
  { id: 3, name: 'Network', icon: Network },
  { id: 4, name: 'Ansible Setup', icon: Package },
]

function CreateInstanceWizard({ config, onConfigChange, onDeploy }) {
  const [currentStep, setCurrentStep] = useState(1)
  const [servers, setServers] = useState([])
  const [templates, setTemplates] = useState([])
  const [storages, setStorages] = useState([])
  const [networks, setNetworks] = useState([])
  const [loading, setLoading] = useState(false)

  // 서버 목록 로드
  useEffect(() => {
    const fetchServers = async () => {
      try {
        setLoading(true)
        const response = await getServers()
        setServers(response.data?.servers || response.data || [])
      } catch (error) {
        console.error('Failed to fetch servers:', error)
        setServers([])
      } finally {
        setLoading(false)
      }
    }
    fetchServers()
  }, [])

  // 템플릿 목록 로드 (옵션)
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const response = await getTemplates()
        setTemplates(response.data?.templates || response.data || [])
      } catch (error) {
        console.error('Failed to fetch templates:', error)
        setTemplates([])
      }
    }
    fetchTemplates()
  }, [])

  // 서버 선택 시 스토리지 로드
  useEffect(() => {
    if (config.selectedServerId) {
      const fetchStorage = async () => {
        try {
          setLoading(true)
          const response = await getServerStorage(config.selectedServerId)
          setStorages(response.data?.storages || response.data || [])
        } catch (error) {
          console.error('Failed to fetch storage:', error)
          setStorages([])
        } finally {
          setLoading(false)
        }
      }
      fetchStorage()
    }
  }, [config.selectedServerId])

  // 서버 선택 시 네트워크 로드
  useEffect(() => {
    if (config.selectedServerId) {
      const fetchNetworks = async () => {
        try {
          setLoading(true)
          const response = await getServerNetworks(config.selectedServerId)
          setNetworks(response.data?.networks || response.data || [])
        } catch (error) {
          console.error('Failed to fetch networks:', error)
          setNetworks([])
        } finally {
          setLoading(false)
        }
      }
      fetchNetworks()
    }
  }, [config.selectedServerId])

  const handleNext = () => {
    if (currentStep < STEPS.length) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleServerSelect = (serverId) => {
    onConfigChange((prev) => ({
      ...prev,
      selectedServerId: serverId,
      selectedTemplateId: '',
      cpuCores: '',
      memory: '',
      selectedStorageId: '',
      selectedNetworkIds: [],
    }))
  }

  const handleTemplateSelect = (templateId) => {
    onConfigChange((prev) => ({
      ...prev,
      selectedTemplateId: templateId,
    }))
  }

  const handleSpecChange = (field, value) => {
    onConfigChange((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleStorageSelect = (storageId) => {
    onConfigChange((prev) => ({
      ...prev,
      selectedStorageId: storageId,
    }))
  }

  const handleNetworkToggle = (networkId) => {
    onConfigChange((prev) => {
      const currentNetworks = prev.selectedNetworkIds || []
      const isSelected = currentNetworks.includes(networkId)
      return {
        ...prev,
        selectedNetworkIds: isSelected
          ? currentNetworks.filter((id) => id !== networkId)
          : [...currentNetworks, networkId],
      }
    })
  }

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return !!config.selectedServerId
      case 2:
        return (
          (config.cpuCores && config.memory && config.selectedStorageId) ||
          (config.selectedTemplateId && config.selectedStorageId)
        )
      case 3:
        return config.selectedNetworkIds?.length > 0
      case 4:
        // Step 4는 선택 사항이므로 항상 진행 가능
        return true
      default:
        return false
    }
  }

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <ServerSelectionStep
            servers={servers}
            templates={templates}
            selectedServerId={config.selectedServerId}
            selectedTemplateId={config.selectedTemplateId}
            serverName={config.serverName || ''}
            onServerSelect={handleServerSelect}
            onTemplateSelect={handleTemplateSelect}
            onNameChange={(name) =>
              onConfigChange((prev) => ({ ...prev, serverName: name }))
            }
            loading={loading}
          />
        )
      case 2:
        return (
          <SpecStorageSelectionStep
            storages={storages}
            selectedTemplateId={config.selectedTemplateId}
            templates={templates}
            cpuCores={config.cpuCores || ''}
            memory={config.memory || ''}
            selectedStorageId={config.selectedStorageId}
            onSpecChange={handleSpecChange}
            onStorageSelect={handleStorageSelect}
            loading={loading}
          />
        )
      case 3:
        return (
          <NetworkSelectionStep
            networks={networks}
            selectedNetworkIds={config.selectedNetworkIds || []}
            onToggle={handleNetworkToggle}
            loading={loading}
          />
        )
      case 4:
        return (
          <AnsibleSetupStep
            selectedPackages={config.selectedPackages || []}
            selectedRoles={config.selectedRoles || []}
            onPackagesChange={(packages) =>
              onConfigChange((prev) => ({ ...prev, selectedPackages: packages }))
            }
            onRolesChange={(roles) =>
              onConfigChange((prev) => ({ ...prev, selectedRoles: roles }))
            }
          />
        )
      default:
        return null
    }
  }

  return (
    <div className="w-full max-w-full overflow-hidden">
      {/* Progress Steps - 탭 영역과 동일한 좌우 간격으로 맞춤, 클릭 가능 */}
      <div className="mb-6 w-full">
        <div className="flex items-center justify-between w-full gap-1">
          {STEPS.map((step, index) => {
            const Icon = step.icon
            const isActive = currentStep === step.id
            const isCompleted = currentStep > step.id
            const isLast = index === STEPS.length - 1
            // 이전 Step이나 완료된 Step으로는 자유롭게 이동 가능
            const canNavigate = step.id <= currentStep || isCompleted

            return (
              <div key={step.id} className="flex items-center flex-1 min-w-0">
                {/* Step Circle and Label - 클릭 가능 */}
                <button
                  onClick={() => {
                    if (canNavigate) {
                      setCurrentStep(step.id)
                    }
                  }}
                  disabled={!canNavigate}
                  className={`flex flex-col items-center w-full min-w-0 transition-all ${
                    canNavigate
                      ? 'cursor-pointer hover:opacity-80 active:scale-95'
                      : 'cursor-not-allowed opacity-50'
                  }`}
                  title={canNavigate ? `Go to Step ${step.id}: ${step.name}` : 'Complete previous steps first'}
                >
                  <div
                    className={`w-8 h-8 sm:w-9 sm:h-9 md:w-10 md:h-10 rounded-full flex items-center justify-center border-2 transition-all shrink-0 ${
                      isCompleted
                        ? 'bg-green-500 border-green-500 text-white'
                        : isActive
                        ? 'bg-blue-600 border-blue-600 text-white shadow-md'
                        : canNavigate
                        ? 'bg-white border-gray-300 text-gray-400 hover:border-blue-400'
                        : 'bg-white border-gray-200 text-gray-300'
                    }`}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="w-4 h-4 sm:w-4.5 sm:h-4.5 md:w-5 md:h-5" />
                    ) : (
                      <Icon className="w-4 h-4 sm:w-4.5 sm:h-4.5 md:w-5 md:h-5" />
                    )}
                  </div>
                  <div className="mt-1.5 text-center w-full min-w-0">
                    <div
                      className={`text-[10px] sm:text-[11px] md:text-xs font-medium ${
                        isActive ? 'text-blue-600' : isCompleted ? 'text-green-600' : canNavigate ? 'text-gray-400' : 'text-gray-300'
                      }`}
                    >
                      {step.id}
                    </div>
                    <div
                      className={`text-[9px] sm:text-[10px] md:text-[10px] mt-0.5 leading-tight ${
                        isActive ? 'text-gray-900 font-medium' : isCompleted ? 'text-gray-600' : canNavigate ? 'text-gray-500' : 'text-gray-300'
                      }`}
                    >
                      {step.name.split(' ').map((word, i) => (
                        <span key={i} className="block">{word}</span>
                      ))}
                    </div>
                  </div>
                </button>
                {/* Connector Line */}
                {!isLast && (
                  <div className="flex-1 mx-1 sm:mx-1.5 md:mx-2 lg:mx-3 shrink-0 min-w-[4px] sm:min-w-[8px]">
                    <div
                      className={`h-0.5 w-full ${
                        isCompleted ? 'bg-green-500' : 'bg-gray-300'
                      }`}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Step Content */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm min-h-[400px] max-h-[600px] overflow-hidden flex flex-col">
        {loading && currentStep === 1 ? (
          <div className="flex items-center justify-center py-12 p-4 md:p-6">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
            <span className="ml-3 text-gray-600">Loading servers...</span>
          </div>
        ) : (
          <div className="p-3 md:p-4 lg:p-6 w-full overflow-y-auto overflow-x-hidden flex-1">
            <div className="w-full max-w-full min-w-0">
              {renderStepContent()}
            </div>
          </div>
        )}
      </div>

      {/* Navigation Buttons */}
      <div className="mt-6 flex justify-between">
        <button
          onClick={handleBack}
          disabled={currentStep === 1}
          className="px-6 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Previous
        </button>
        <div className="flex gap-3">
          {currentStep < STEPS.length ? (
            <button
              onClick={handleNext}
              disabled={!canProceed()}
              className="px-6 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={onDeploy}
              disabled={!canProceed()}
              className="px-6 py-2.5 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              Launch Instance
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// Step 1: Server Selection + Template Selection (Optional)
function ServerSelectionStep({
  servers,
  templates,
  selectedServerId,
  selectedTemplateId,
  serverName,
  onServerSelect,
  onTemplateSelect,
  onNameChange,
  loading,
}) {
  return (
    <div className="w-full max-w-full min-w-0">
      <h3 className="text-base md:text-lg font-semibold text-gray-900 mb-1">Select Server</h3>
      <p className="text-xs md:text-sm text-gray-500 mb-2 md:mb-3">
        Choose a server and optionally select a template
      </p>

      {/* Instance Name Input */}
      <div className="mb-2 md:mb-3">
        <h4 className="text-xs md:text-sm font-semibold text-gray-700 mb-1.5 uppercase tracking-wide">
          Instance Name
        </h4>
        <div className="border border-gray-200 rounded-lg p-2 md:p-3 bg-gray-50 w-full max-w-full min-w-0">
          <label className="block text-xs md:text-sm font-medium text-gray-700 mb-1.5">
            Instance Name <span className="text-gray-400">(Optional)</span>
          </label>
          <input
            type="text"
            value={serverName}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="e.g., web-server-01"
            className="w-full max-w-full px-2 md:px-3 py-1.5 md:py-2 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 placeholder-gray-400 transition-colors"
          />
          <p className="mt-1 text-[10px] md:text-xs text-gray-500">
            Leave empty to auto-generate a name
          </p>
        </div>
      </div>

      {/* Server Selection */}
      <div className="mb-2 md:mb-3">
        <h4 className="text-xs md:text-sm font-semibold text-gray-700 mb-1.5 uppercase tracking-wide flex items-center gap-1.5">
          <Server className="w-3.5 h-3.5 md:w-4 md:h-4 text-blue-600 shrink-0" />
          Server Selection
        </h4>
        <div className="border border-gray-200 rounded-lg p-2 md:p-3 bg-gray-50 w-full max-w-full min-w-0 overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-6 md:py-8">
              <Loader2 className="w-5 h-5 md:w-6 md:h-6 text-blue-600 animate-spin" />
              <span className="ml-2 md:ml-3 text-xs md:text-sm text-gray-600">Loading...</span>
            </div>
          ) : servers.length === 0 ? (
            <div className="text-center py-6 md:py-8 text-gray-500 border border-gray-200 rounded-lg bg-white">
              <Server className="w-6 h-6 md:w-8 md:h-8 mx-auto mb-2 text-gray-400" />
              <p className="text-xs md:text-sm">No servers available</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 md:gap-3 w-full max-w-full">
              {servers.map((server) => (
                <button
                  key={server.id || server.server_id}
                  onClick={() => onServerSelect(server.id || server.server_id)}
                  className={`p-2 md:p-3 border-2 rounded-lg text-left transition-all hover:shadow-sm w-full max-w-full min-w-0 ${
                    selectedServerId === (server.id || server.server_id)
                      ? 'border-blue-600 bg-blue-50 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/30'
                  }`}
                >
                  <div className="flex items-start justify-between gap-1.5">
                    <div className="flex-1 min-w-0 overflow-hidden">
                      <div className="font-semibold text-xs md:text-sm text-gray-900 mb-0.5 truncate">
                        {server.name || server.server_name || 'Unnamed Server'}
                      </div>
                      {server.description && (
                        <div className="text-[10px] md:text-xs text-gray-500 mt-0.5 line-clamp-2">
                          {server.description}
                        </div>
                      )}
                    </div>
                    {selectedServerId === (server.id || server.server_id) && (
                      <CheckCircle2 className="w-4 h-4 md:w-5 md:h-5 text-blue-600 shrink-0" />
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Template Selection (Optional) */}
      {templates.length > 0 && (
        <div className="w-full max-w-full min-w-0">
          <h4 className="text-xs md:text-sm font-semibold text-gray-700 mb-1.5 uppercase tracking-wide flex items-center gap-1.5">
            <Server className="w-3.5 h-3.5 md:w-4 md:h-4 text-green-600 shrink-0" />
            Template Selection
          </h4>
          <div className="border border-gray-200 rounded-lg p-2 md:p-3 bg-gray-50 w-full max-w-full min-w-0 overflow-hidden">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 md:gap-3 w-full max-w-full">
              <button
                onClick={() => onTemplateSelect('')}
                className={`p-2 md:p-3 border-2 rounded-lg text-left transition-all hover:shadow-sm w-full max-w-full min-w-0 ${
                  !selectedTemplateId
                    ? 'border-blue-600 bg-blue-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/30'
                }`}
              >
                <div className="font-semibold text-xs md:text-sm text-gray-900">No Template</div>
                <div className="text-[10px] md:text-xs text-gray-600 mt-0.5">
                  Custom configuration
                </div>
              </button>
              {templates.map((template) => (
                <button
                  key={template.id || template.template_id}
                  onClick={() => onTemplateSelect(template.id || template.template_id)}
                  className={`p-2 md:p-3 border-2 rounded-lg text-left transition-all hover:shadow-sm w-full max-w-full min-w-0 ${
                    selectedTemplateId === (template.id || template.template_id)
                      ? 'border-blue-600 bg-blue-50 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/30'
                  }`}
                >
                  <div className="flex items-start justify-between gap-1.5">
                    <div className="flex-1 min-w-0 overflow-hidden">
                      <div className="font-semibold text-xs md:text-sm text-gray-900 mb-0.5 truncate">
                        {template.name || template.template_name || 'Unnamed Template'}
                      </div>
                      <div className="text-[10px] md:text-xs text-gray-600 space-y-0.5">
                        {template.cpu_cores && <div>CPU: {template.cpu_cores} cores</div>}
                        {template.memory_gb && <div>Memory: {template.memory_gb} GB</div>}
                      </div>
                    </div>
                    {selectedTemplateId === (template.id || template.template_id) && (
                      <CheckCircle2 className="w-4 h-4 md:w-5 md:h-5 text-blue-600 shrink-0" />
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Step 2: CPU/Memory Spec Selection + Storage List
function SpecStorageSelectionStep({
  storages,
  selectedTemplateId,
  templates,
  cpuCores,
  memory,
  selectedStorageId,
  onSpecChange,
  onStorageSelect,
  loading,
}) {
  const selectedTemplate = templates.find(
    (t) => (t.id || t.template_id) === selectedTemplateId
  )

  // 템플릿 선택 시 자동으로 스펙 채우기
  useEffect(() => {
    if (selectedTemplate) {
      onSpecChange('cpuCores', selectedTemplate.cpu_cores?.toString() || '')
      onSpecChange('memory', selectedTemplate.memory_gb?.toString() || '')
    }
  }, [selectedTemplateId, selectedTemplate, onSpecChange])

  return (
    <div className="w-full max-w-full min-w-0">
      <h3 className="text-base md:text-lg font-semibold text-gray-900 mb-1">Configure Spec & Storage</h3>
      <p className="text-xs md:text-sm text-gray-500 mb-2 md:mb-3">
        Set CPU, Memory and select storage for your instance
      </p>

      {/* CPU & Memory Spec */}
      <div className="mb-2 md:mb-3">
        <h4 className="text-xs md:text-sm font-semibold text-gray-700 mb-1.5 uppercase tracking-wide">
          Compute Resources
        </h4>
        <div className="grid grid-cols-2 gap-2 md:gap-3 w-full max-w-full">
          <div className="min-w-0">
            <label className="block text-xs md:text-sm font-medium text-gray-700 mb-1">
              CPU Cores <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="1"
              max="32"
              value={cpuCores}
              onChange={(e) => onSpecChange('cpuCores', e.target.value)}
              placeholder="4"
              disabled={!!selectedTemplateId}
              className="w-full max-w-full px-2 md:px-3 py-1.5 md:py-2 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 placeholder-gray-400 transition-colors disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            {selectedTemplateId && (
              <p className="mt-0.5 text-[10px] md:text-xs text-gray-500">
                Set by template
              </p>
            )}
          </div>
          <div className="min-w-0">
            <label className="block text-xs md:text-sm font-medium text-gray-700 mb-1">
              Memory (GB) <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="1"
              max="256"
              value={memory}
              onChange={(e) => onSpecChange('memory', e.target.value)}
              placeholder="8"
              disabled={!!selectedTemplateId}
              className="w-full max-w-full px-2 md:px-3 py-1.5 md:py-2 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 placeholder-gray-400 transition-colors disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            {selectedTemplateId && (
              <p className="mt-0.5 text-[10px] md:text-xs text-gray-500">
                Set by template
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Storage Selection */}
      <div>
        <h4 className="text-xs md:text-sm font-semibold text-gray-700 mb-1.5 uppercase tracking-wide">
          Storage
        </h4>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
            <span className="ml-3 text-gray-600">Loading storage options...</span>
          </div>
        ) : storages.length === 0 ? (
          <div className="text-center py-8 text-gray-500 border border-gray-200 rounded-lg">
            <HardDrive className="w-8 h-8 mx-auto mb-2 text-gray-400" />
            <p>No storage options available</p>
            <p className="text-xs mt-1">Please select a server first</p>
          </div>
        ) : (
          <div className="space-y-1.5 md:space-y-2 w-full max-w-full">
            {storages.map((storage) => (
              <button
                key={storage.id || storage.storage_id}
                onClick={() => onStorageSelect(storage.id || storage.storage_id)}
                className={`w-full max-w-full p-2 md:p-3 border-2 rounded-lg text-left transition-all ${
                  selectedStorageId === (storage.id || storage.storage_id)
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex-1 min-w-0 overflow-hidden">
                    <div className="font-semibold text-xs md:text-sm text-gray-900 truncate">
                      {storage.name || storage.storage_name || 'Unnamed Storage'}
                    </div>
                    <div className="text-[10px] md:text-xs text-gray-600 mt-0.5 line-clamp-1">
                      {storage.size_gb && `Size: ${storage.size_gb} GB`}
                      {storage.available_gb && ` • Available: ${storage.available_gb} GB`}
                      {storage.type && ` • Type: ${storage.type}`}
                    </div>
                  </div>
                  {selectedStorageId === (storage.id || storage.storage_id) && (
                    <CheckCircle2 className="w-4 h-4 md:w-5 md:h-5 text-blue-600 shrink-0" />
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Step 3: Network Selection
function NetworkSelectionStep({ networks, selectedNetworkIds, onToggle, loading }) {
  return (
    <div className="w-full max-w-full min-w-0">
      <h3 className="text-base md:text-lg font-semibold text-gray-900 mb-1">Configure Network</h3>
      <p className="text-xs md:text-sm text-gray-500 mb-2 md:mb-3">
        Select one or more networks for your instance
      </p>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
          <span className="ml-3 text-gray-600">Loading networks...</span>
        </div>
      ) : networks.length === 0 ? (
        <div className="text-center py-12 text-gray-500 border border-gray-200 rounded-lg">
          <Network className="w-12 h-12 mx-auto mb-4 text-gray-400" />
          <p>No networks available</p>
          <p className="text-xs mt-1">Please select a server first</p>
        </div>
      ) : (
        <div className="space-y-1.5 md:space-y-2 w-full max-w-full">
          {networks.map((network) => {
            const isSelected = selectedNetworkIds.includes(
              network.id || network.network_id
            )
            return (
              <button
                key={network.id || network.network_id}
                onClick={() => onToggle(network.id || network.network_id)}
                className={`w-full max-w-full p-2 md:p-3 border-2 rounded-lg text-left transition-all ${
                  isSelected
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex-1 min-w-0 overflow-hidden">
                    <div className="font-semibold text-xs md:text-sm text-gray-900 truncate">
                      {network.name || network.network_name || 'Unnamed Network'}
                    </div>
                    <div className="text-[10px] md:text-xs text-gray-600 mt-0.5 space-y-0.5">
                      {network.type && <div>Type: {network.type}</div>}
                      {network.cidr && <div>CIDR: {network.cidr}</div>}
                      {network.description && (
                        <div className="text-gray-500 line-clamp-1">{network.description}</div>
                      )}
                    </div>
                  </div>
                  <div
                    className={`w-4 h-4 md:w-5 md:h-5 rounded border-2 flex items-center justify-center shrink-0 ${
                      isSelected ? 'border-blue-600 bg-blue-600' : 'border-gray-300'
                    }`}
                  >
                    {isSelected && <CheckCircle2 className="w-3 h-3 md:w-4 md:h-4 text-white" />}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// Step 4: Ansible Setup - 패키지 및 역할 선택
function AnsibleSetupStep({
  selectedPackages,
  selectedRoles,
  onPackagesChange,
  onRolesChange,
}) {
  // 일반적인 패키지 목록
  const availablePackages = [
    { id: 'curl', name: 'curl', description: 'Command-line tool for transferring data' },
    { id: 'wget', name: 'wget', description: 'Non-interactive network downloader' },
    { id: 'git', name: 'Git', description: 'Version control system' },
    { id: 'vim', name: 'Vim', description: 'Text editor' },
    { id: 'htop', name: 'htop', description: 'Interactive process viewer' },
    { id: 'net-tools', name: 'net-tools', description: 'Network configuration tools (ifconfig, netstat)' },
    { id: 'docker', name: 'Docker', description: 'Container platform' },
    { id: 'docker-compose', name: 'Docker Compose', description: 'Multi-container Docker application tool' },
    { id: 'nginx', name: 'Nginx', description: 'Web server and reverse proxy' },
    { id: 'nodejs', name: 'Node.js', description: 'JavaScript runtime' },
    { id: 'python3-pip', name: 'Python pip', description: 'Python package installer' },
    { id: 'postgresql', name: 'PostgreSQL', description: 'Relational database' },
    { id: 'redis', name: 'Redis', description: 'In-memory data structure store' },
    { id: 'certbot', name: 'Certbot', description: 'Let\'s Encrypt SSL certificate tool' },
    { id: 'fail2ban', name: 'Fail2ban', description: 'Intrusion prevention software' },
  ]

  // Ansible 역할 목록
  const availableRoles = [
    { id: 'docker', name: 'Docker Setup', description: 'Install and configure Docker with Docker Compose' },
    { id: 'nginx', name: 'Nginx Web Server', description: 'Install and configure Nginx web server' },
    { id: 'ssl', name: 'SSL/TLS Setup', description: 'Configure SSL certificates with Let\'s Encrypt' },
    { id: 'firewall', name: 'Firewall Configuration', description: 'Configure UFW or firewalld' },
    { id: 'monitoring', name: 'Monitoring Tools', description: 'Install monitoring tools (Prometheus, Grafana)' },
    { id: 'backup', name: 'Backup Setup', description: 'Configure automated backup system' },
    { id: 'security', name: 'Security Hardening', description: 'Apply security best practices' },
    { id: 'kubernetes', name: 'Kubernetes', description: 'Install and configure Kubernetes cluster' },
  ]

  const handlePackageToggle = (packageId) => {
    const isSelected = selectedPackages.includes(packageId)
    if (isSelected) {
      onPackagesChange(selectedPackages.filter((id) => id !== packageId))
    } else {
      onPackagesChange([...selectedPackages, packageId])
    }
  }

  const handleRoleToggle = (roleId) => {
    const isSelected = selectedRoles.includes(roleId)
    if (isSelected) {
      onRolesChange(selectedRoles.filter((id) => id !== roleId))
    } else {
      onRolesChange([...selectedRoles, roleId])
    }
  }

  return (
    <div className="w-full max-w-full min-w-0">
      <h3 className="text-base md:text-lg font-semibold text-gray-900 mb-1">Ansible Configuration</h3>
      <p className="text-xs md:text-sm text-gray-500 mb-2 md:mb-3">
        Select packages and roles to install on your instance after deployment
      </p>

      {/* Packages Section */}
      <div className="mb-2 md:mb-3">
        <h4 className="text-xs md:text-sm font-semibold text-gray-700 mb-1.5 uppercase tracking-wide flex items-center gap-1.5">
          <Package className="w-3.5 h-3.5 md:w-4 md:h-4 text-blue-600 shrink-0" />
          Packages
        </h4>
        <p className="text-[10px] md:text-xs text-gray-500 mb-1.5">
          Select software packages to install via package manager (apt/yum)
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5 md:gap-2 max-h-48 md:max-h-64 lg:max-h-80 overflow-y-auto border border-gray-200 rounded-lg p-2 md:p-3 bg-gray-50 w-full max-w-full">
          {availablePackages.map((pkg) => {
            const isSelected = selectedPackages.includes(pkg.id)
            return (
              <button
                key={pkg.id}
                onClick={() => handlePackageToggle(pkg.id)}
                className={`p-1.5 md:p-2 border-2 rounded-lg text-left transition-all hover:shadow-sm w-full max-w-full min-w-0 ${
                  isSelected
                    ? 'border-blue-600 bg-blue-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/30'
                }`}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="flex-1 min-w-0 overflow-hidden">
                    <div className="font-semibold text-[10px] md:text-xs text-gray-900 truncate">{pkg.name}</div>
                    <div className="text-[9px] md:text-[10px] text-gray-600 mt-0.5 line-clamp-2">{pkg.description}</div>
                  </div>
                  <div
                    className={`w-3.5 h-3.5 md:w-4 md:h-4 rounded border-2 flex items-center justify-center shrink-0 ${
                      isSelected ? 'border-blue-600 bg-blue-600' : 'border-gray-300'
                    }`}
                  >
                    {isSelected && <CheckCircle2 className="w-2.5 h-2.5 md:w-3 md:h-3 text-white" />}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
        {selectedPackages.length > 0 && (
          <p className="mt-1 text-[10px] md:text-xs text-gray-600">
            {selectedPackages.length} package(s) selected
          </p>
        )}
      </div>

      {/* Roles Section */}
      <div>
        <h4 className="text-xs md:text-sm font-semibold text-gray-700 mb-1.5 uppercase tracking-wide flex items-center gap-1.5">
          <Package className="w-3.5 h-3.5 md:w-4 md:h-4 text-green-600 shrink-0" />
          Ansible Roles
        </h4>
        <p className="text-[10px] md:text-xs text-gray-500 mb-1.5">
          Select Ansible roles for advanced configuration and setup
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5 md:gap-2 max-h-48 md:max-h-64 lg:max-h-80 overflow-y-auto border border-gray-200 rounded-lg p-2 md:p-3 bg-gray-50 w-full max-w-full">
          {availableRoles.map((role) => {
            const isSelected = selectedRoles.includes(role.id)
            return (
              <button
                key={role.id}
                onClick={() => handleRoleToggle(role.id)}
                className={`p-1.5 md:p-2 border-2 rounded-lg text-left transition-all hover:shadow-sm w-full max-w-full min-w-0 ${
                  isSelected
                    ? 'border-green-600 bg-green-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-green-300 hover:bg-green-50/30'
                }`}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="flex-1 min-w-0 overflow-hidden">
                    <div className="font-semibold text-[10px] md:text-xs text-gray-900 truncate">{role.name}</div>
                    <div className="text-[9px] md:text-[10px] text-gray-600 mt-0.5 line-clamp-2">{role.description}</div>
                  </div>
                  <div
                    className={`w-3.5 h-3.5 md:w-4 md:h-4 rounded border-2 flex items-center justify-center shrink-0 ${
                      isSelected ? 'border-green-600 bg-green-600' : 'border-gray-300'
                    }`}
                  >
                    {isSelected && <CheckCircle2 className="w-2.5 h-2.5 md:w-3 md:h-3 text-white" />}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
        {selectedRoles.length > 0 && (
          <p className="mt-1 text-[10px] md:text-xs text-gray-600">
            {selectedRoles.length} role(s) selected
          </p>
        )}
      </div>

      {/* Info Message */}
      <div className="mt-2 md:mt-3 p-2 md:p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-[10px] md:text-xs text-blue-800 leading-relaxed">
          <strong>Note:</strong> Selected packages and roles will be installed automatically after the VM is created via Terraform.
          This step is optional - you can proceed without selecting anything.
        </p>
      </div>
    </div>
  )
}

export default CreateInstanceWizard
