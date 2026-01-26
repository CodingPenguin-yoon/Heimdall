import { useEffect, useRef } from 'react'
import { Terminal } from 'lucide-react'

function LogViewer({ logs }) {
  const logEndRef = useRef(null)

  useEffect(() => {
    // 자동 스크롤 (새 로그가 추가될 때)
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const getLogColor = (type) => {
    switch (type) {
      case 'success':
        return 'text-green-600'
      case 'error':
        return 'text-red-600'
      case 'warning':
        return 'text-yellow-600'
      default:
        return 'text-gray-800'
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Terminal className="w-5 h-5 text-blue-600" />
          Activity Log
        </h2>
        <p className="text-sm text-gray-500 mt-1">View deployment and operation logs</p>
      </div>

      <div className="p-6">
        <div className="bg-gray-900 rounded-md p-4 h-96 overflow-y-auto font-mono text-sm border border-gray-300">
          {logs.length === 0 ? (
            <div className="text-gray-500">No logs yet. Start a deployment to see logs here.</div>
          ) : (
            <div className="space-y-1">
              {logs.map((log, index) => (
                <div key={index} className="flex gap-3">
                  <span className="text-gray-500 shrink-0">[{log.timestamp}]</span>
                  <span className={getLogColor(log.type)}>{log.message}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default LogViewer
