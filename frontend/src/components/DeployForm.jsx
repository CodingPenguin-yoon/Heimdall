import { Server, Cpu, HardDrive, HardDriveIcon, Network, Globe } from 'lucide-react'

function DeployForm({ config, onConfigChange }) {
  const handleChange = (field, value) => {
    onConfigChange((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Server className="w-5 h-5 text-blue-600" />
          Instance Configuration
        </h2>
        <p className="text-sm text-gray-500 mt-1">Configure your infrastructure instance settings</p>
      </div>

      {/* Form Content */}
      <div className="p-6 space-y-6">
        {/* Basic Information Section */}
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Basic Information</h3>
          <div className="space-y-4">
            {/* Server Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Instance Name
              </label>
              <input
                type="text"
                value={config.serverName}
                onChange={(e) => handleChange('serverName', e.target.value)}
                placeholder="e.g., web-server-01"
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-colors"
              />
              <p className="mt-1 text-xs text-gray-500">A unique name for your instance</p>
            </div>
          </div>
        </div>

        {/* Compute Resources Section */}
        <div className="pt-4 border-t border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide flex items-center gap-2">
            <Cpu className="w-4 h-4" />
            Compute Resources
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {/* CPU Cores */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                CPU Cores
              </label>
              <input
                type="number"
                min="1"
                max="32"
                value={config.cpuCores}
                onChange={(e) => handleChange('cpuCores', e.target.value)}
                placeholder="4"
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-colors"
              />
            </div>

            {/* Memory */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                <HardDrive className="w-3.5 h-3.5" />
                Memory (GB)
              </label>
              <input
                type="number"
                min="1"
                max="256"
                value={config.memory}
                onChange={(e) => handleChange('memory', e.target.value)}
                placeholder="8"
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-colors"
              />
            </div>
          </div>
        </div>

        {/* Storage Section */}
        <div className="pt-4 border-t border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide flex items-center gap-2">
            <HardDriveIcon className="w-4 h-4" />
            Storage
          </h3>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Disk Size (GB)
            </label>
            <input
              type="number"
              min="10"
              max="2048"
              value={config.diskSize}
              onChange={(e) => handleChange('diskSize', e.target.value)}
              placeholder="50"
              className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-colors"
            />
            <p className="mt-1 text-xs text-gray-500">Minimum 10 GB, Maximum 2048 GB</p>
          </div>
        </div>

        {/* Network Section */}
        <div className="pt-4 border-t border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide flex items-center gap-2">
            <Network className="w-4 h-4" />
            Network
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Network Type
              </label>
              <select
                value={config.networkType}
                onChange={(e) => handleChange('networkType', e.target.value)}
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 transition-colors"
              >
                <option value="private">Private Network</option>
                <option value="public">Public Network</option>
                <option value="both">Both</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                <Globe className="w-3.5 h-3.5" />
                Region
              </label>
              <select
                value={config.region}
                onChange={(e) => handleChange('region', e.target.value)}
                className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 transition-colors"
              >
                <option value="us-east-1">US East (N. Virginia)</option>
                <option value="us-west-1">US West (N. California)</option>
                <option value="eu-west-1">Europe (Ireland)</option>
                <option value="ap-northeast-1">Asia Pacific (Tokyo)</option>
                <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DeployForm
