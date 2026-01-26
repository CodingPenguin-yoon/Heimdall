import { CheckCircle2, XCircle, Loader2, Clock, AlertCircle } from 'lucide-react'

function StatusPanel({ status }) {
  const getStatusConfig = () => {
    switch (status) {
      case 'success':
      case 'completed':
        return {
          icon: CheckCircle2,
          color: 'text-green-600',
          bgColor: 'bg-green-50',
          borderColor: 'border-green-200',
          progressColor: 'bg-green-500',
          label: 'Success',
          progress: 100,
        }
      case 'failed':
      case 'error':
        return {
          icon: XCircle,
          color: 'text-red-600',
          bgColor: 'bg-red-50',
          borderColor: 'border-red-200',
          progressColor: 'bg-red-500',
          label: 'Failed',
          progress: 0,
        }
      case 'deploying':
      case 'in_progress':
      case 'processing':
        return {
          icon: Loader2,
          color: 'text-blue-600',
          bgColor: 'bg-blue-50',
          borderColor: 'border-blue-200',
          progressColor: 'bg-blue-500',
          label: 'Deploying',
          progress: 50,
        }
      case 'destroying':
        return {
          icon: Loader2,
          color: 'text-orange-600',
          bgColor: 'bg-orange-50',
          borderColor: 'border-orange-200',
          progressColor: 'bg-orange-500',
          label: 'Destroying',
          progress: 50,
        }
      case 'pending':
        return {
          icon: Clock,
          color: 'text-yellow-600',
          bgColor: 'bg-yellow-50',
          borderColor: 'border-yellow-200',
          progressColor: 'bg-yellow-500',
          label: 'Pending',
          progress: 25,
        }
      default:
        return {
          icon: AlertCircle,
          color: 'text-gray-600',
          bgColor: 'bg-gray-50',
          borderColor: 'border-gray-200',
          progressColor: 'bg-gray-300',
          label: 'Idle',
          progress: 0,
        }
    }
  }

  const statusConfig = getStatusConfig()
  const Icon = statusConfig.icon

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Instance Status</h2>
        <p className="text-sm text-gray-500 mt-1">Real-time deployment status</p>
      </div>

      <div className="p-6">
        {/* Status Badge */}
        <div
          className={`flex items-center gap-3 px-4 py-3 rounded-md border ${statusConfig.bgColor} ${statusConfig.borderColor} mb-6`}
        >
          <Icon
            className={`w-6 h-6 ${statusConfig.color} ${
              status === 'deploying' || status === 'destroying'
                ? 'animate-spin'
                : ''
            }`}
          />
          <span className={`font-semibold ${statusConfig.color}`}>
            {statusConfig.label}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2 mb-6">
          <div className="flex justify-between text-sm text-gray-600">
            <span className="font-medium">Progress</span>
            <span className="font-semibold">{statusConfig.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${statusConfig.progressColor}`}
              style={{ width: `${statusConfig.progress}%` }}
            />
          </div>
        </div>

        {/* Status Details */}
        <div className="pt-4 border-t border-gray-200">
          <div className="text-sm">
            <div className="flex justify-between items-center">
              <span className="text-gray-600 font-medium">Current Status:</span>
              <span className="text-gray-900 font-semibold uppercase">{status || 'idle'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default StatusPanel
