import { useState } from 'react'
import { Send, Sparkles, Terminal, Play } from 'lucide-react'
import { llmChat, executeLlmAction } from '../services/api'

/**
 * LLM 기반 인프라 채팅 컴포넌트
 *
 * - 자연어 채팅 UI
 * - LLM이 제안한 인프라 액션 목록 표시
 * - 사용자가 액션을 선택/실행 버튼을 눌렀을 때만 실제 인프라 액션 실행
 */
function LlmInfraChat() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        '안녕하세요! Proxmox / Terraform / Ansible 기반 인프라 도우미입니다.\n' +
        '예: "현재 VM 상태 보여줘", "CPU 4코어, 메모리 8GB로 Ubuntu VM 하나 만들어줘"처럼 요청해 보세요.',
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [pendingActions, setPendingActions] = useState([])
  const [selectedActionIndex, setSelectedActionIndex] = useState(null)

  const addMessage = (role, content, extras = {}) => {
    setMessages((prev) => [...prev, { role, content, ...extras }])
  }

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return

    const userMessage = { role: 'user', content: trimmed }
    setInput('')
    addMessage('user', trimmed)
    setIsLoading(true)

    try {
      // 기존 대화 이력을 LLM API에 전달
      const payload = {
        messages: messages.map((m) => ({
          role: m.role,
          content: m.content,
        })),
        latest_message: userMessage,
        context: null,
      }

      const response = await llmChat(payload)
      const data = response.data || response

      const assistantMessage = data.assistant_message || 'LLM 응답을 가져오지 못했습니다.'
      const actions = Array.isArray(data.actions) ? data.actions : []
      const extraData = data.data || null

      // LLM 응답 + 백엔드가 자동 실행한 조회 결과(data)를 함께 메시지에 저장
      addMessage('assistant', assistantMessage, { data: extraData })

      // 읽기 전용(조회) 액션은 이미 백엔드에서 자동 실행되므로
      // 프론트에서는 수동 실행이 필요한 액션만 목록에 표시
      setPendingActions(actions.filter((a) => !['list_vms', 'list_nodes', 'get_vm_detail'].includes(a.type)))
      setSelectedActionIndex(null)
    } catch (error) {
      const errorMessage = error.response?.data?.detail || error.message || 'LLM 호출 중 오류가 발생했습니다.'
      addMessage('assistant', `LLM 호출 실패: ${errorMessage}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleExecuteAction = async (action, index) => {
    if (!action) return
    setSelectedActionIndex(index)
    setIsLoading(true)

    try {
      addMessage(
        'assistant',
        `선택한 액션을 실행합니다:\n- 타입: ${action.type}\n- 설명: ${action.description || '(설명 없음)'}`,
      )

      const response = await executeLlmAction({ action })
      const data = response.data || response

      const resultMessage = data.result_message || '액션 실행 결과 메시지를 가져오지 못했습니다.'
      addMessage('assistant', resultMessage)
    } catch (error) {
      const errorMessage = error.response?.data?.detail || error.message || '액션 실행 중 오류가 발생했습니다.'
      addMessage('assistant', `액션 실행 실패: ${errorMessage}`)
    } finally {
      setIsLoading(false)
      setSelectedActionIndex(null)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[2fr,1fr] gap-6">
      {/* Chat Panel */}
      <div className="flex flex-col bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="flex items-center gap-2 px-6 py-4 border-b border-gray-200">
          <Sparkles className="w-5 h-5 text-purple-500" />
          <h2 className="text-lg font-semibold text-gray-900">LLM Infra Assistant</h2>
          <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-600 border border-purple-100">
            MVP
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 px-6 py-4 space-y-4 overflow-y-auto max-h-[520px]">
          {messages.map((msg, idx) => {
            const isUser = msg.role === 'user'

            // LLM 응답 중 "[자동 실행 결과]" 구분
            let mainText = msg.content || ''
            let autoSection = ''
            if (!isUser && typeof msg.content === 'string') {
              const splitToken = '\n\n[자동 실행 결과]'
              const parts = msg.content.split(splitToken)
              mainText = parts[0]
              if (parts.length > 1) {
                autoSection = '[자동 실행 결과]' + parts.slice(1).join(splitToken)
              }
            }

            const hasVmData = !!msg.data?.vms && Array.isArray(msg.data.vms) && msg.data.vms.length > 0

            return (
              <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                    isUser
                      ? 'bg-blue-600 text-white rounded-br-sm whitespace-pre-wrap'
                      : 'bg-gray-100 text-gray-900 rounded-bl-sm'
                  }`}
                >
                  {/* 기본 텍스트 응답 */}
                  <div className="whitespace-pre-wrap">{mainText}</div>

                  {/* 백엔드 자동 실행 결과가 있지만 VM 데이터가 없는 경우에는 원문을 그대로 표시 */}
                  {!hasVmData && autoSection && (
                    <div className="mt-3 text-xs text-gray-700 bg-white/60 rounded-md px-3 py-2 whitespace-pre-wrap">
                      {autoSection}
                    </div>
                  )}

                  {/* VM 목록이 있는 경우: 보기 좋은 카드 + View more */}
                  {hasVmData && (
                    <div className="mt-3">
                      <VmListPreview vms={msg.data.vms} />
                    </div>
                  )}
                </div>
              </div>
            )
          })}
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Terminal className="w-4 h-4 animate-pulse" />
              <span>모델이 응답을 생성 중입니다...</span>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
          <div className="flex items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder='예: "현재 VM들 상태 요약해줘", "CPU 4코어 8GB Ubuntu VM 하나 생성해줘"'
              rows={2}
              className="flex-1 resize-none rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium shadow-sm hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
              보내기
            </button>
          </div>
        </div>
      </div>

      {/* Actions Panel */}
      <div className="flex flex-col bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="flex items-center gap-2 px-6 py-4 border-b border-gray-200">
          <Play className="w-4 h-4 text-green-500" />
          <h3 className="text-sm font-semibold text-gray-900">제안된 인프라 액션</h3>
        </div>

        <div className="flex-1 px-6 py-4 space-y-3 overflow-y-auto max-h-[520px]">
          {pendingActions.length === 0 && (
            <p className="text-sm text-gray-500">
              아직 실행 가능한 액션이 없습니다.
              <br />
              VM 조회나 생성에 대한 요청을 보내면 여기에서 제안된 액션이 표시됩니다.
            </p>
          )}

          {pendingActions.map((action, index) => (
            <div
              key={index}
              className={`border rounded-lg p-3 text-sm space-y-2 ${
                selectedActionIndex === index ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold uppercase text-gray-500">Action Type</div>
                  <div className="text-sm font-medium text-gray-900">{action.type}</div>
                </div>
                <button
                  onClick={() => handleExecuteAction(action, index)}
                  disabled={isLoading}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed"
                >
                  <Play className="w-3 h-3" />
                  실행
                </button>
              </div>

              {action.description && (
                <p className="text-xs text-gray-700 border-t border-dashed border-gray-200 pt-2">
                  {action.description}
                </p>
              )}

              {action.params && Object.keys(action.params).length > 0 && (
                <div className="text-xs text-gray-600 bg-white border border-gray-200 rounded-md px-2 py-1">
                  <div className="font-semibold mb-1">매개변수</div>
                  <dl className="space-y-0.5">
                    {Object.entries(action.params).map(([key, value]) => (
                      <div key={key} className="flex justify-between gap-2">
                        <dt className="text-gray-500">{key}</dt>
                        <dd className="text-gray-800 text-right break-all">
                          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default LlmInfraChat

// ---------------------------------------------------------------------------
// VM 목록 프리뷰 컴포넌트
// - 상위 5개만 먼저 보여주고, "View more" 버튼으로 전체 토글
// ---------------------------------------------------------------------------

function VmListPreview({ vms }) {
  const [showAll, setShowAll] = useState(false)

  const total = vms.length
  const displayVms = showAll ? vms : vms.slice(0, 5)

  return (
    <div className="bg-white/70 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-800 space-y-2">
      <div className="font-semibold text-gray-900 flex items-center justify-between">
        <span>Proxmox VM 목록 요약</span>
        <span className="text-[11px] text-gray-500">{total}개 VM</span>
      </div>

      <ul className="space-y-1">
        {displayVms.map((vm, idx) => (
          <li
            key={vm.vmid || vm.id || `${vm.node}-${idx}`}
            className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 rounded-md bg-gray-50 px-2 py-1.5"
          >
            <div className="font-medium text-[13px] text-gray-900">
              {vm.name || vm.vm_id || vm.id || '이름 없음'}
              {vm.vmid && <span className="ml-1 text-[11px] text-gray-500">#{vm.vmid}</span>}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-600">
              <span className="px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-700 border border-gray-200">
                노드: {vm.node || '-'}
              </span>
              <StatusPill status={vm.status} />
              <span>
                CPU {vm.cpu_cores ?? vm.cpu ?? '-'} · 메모리 {vm.memory_gb ?? vm.memory ?? '-'}GB
              </span>
            </div>
          </li>
        ))}
      </ul>

      {total > 5 && (
        <button
          type="button"
          onClick={() => setShowAll((prev) => !prev)}
          className="mt-1 inline-flex items-center text-[11px] font-medium text-blue-600 hover:text-blue-700"
        >
          {showAll ? '상위 5개만 보기' : `나머지 ${total - 5}개 더 보기`}
        </button>
      )}
    </div>
  )
}

function StatusPill({ status }) {
  const normalized = (status || '').toString().toLowerCase()
  const isRunning = normalized === 'running'
  const isStopped = normalized === 'stopped'

  let colorClass = 'bg-gray-100 text-gray-700 border-gray-200'
  let label = status || 'unknown'

  if (isRunning) {
    colorClass = 'bg-green-100 text-green-800 border-green-200'
  } else if (isStopped) {
    colorClass = 'bg-gray-100 text-gray-800 border-gray-300'
  }

  return (
    <span className={`px-1.5 py-0.5 rounded-full border text-[11px] font-semibold ${colorClass}`}>
      {label}
    </span>
  )
}

