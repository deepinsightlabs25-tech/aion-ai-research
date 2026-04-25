import axios from 'axios'

export const DEFAULT_API_BASE_URL = 'https://ai-report-gen.onrender.com'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL,
  timeout: 120_000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

let authToken = null

export function setAuthToken(token) {
  authToken = token || null
}

export function clearAuthToken() {
  authToken = null
}

apiClient.interceptors.request.use((config) => {
  if (authToken) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${authToken}`
  }
  return config
})

function formatValidationDetail(detail) {
  if (!detail) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === 'object' && 'msg' in d) {
          const loc = Array.isArray(d.loc) ? d.loc.filter(Boolean).join('.') : ''
          return loc ? `${loc}: ${d.msg}` : d.msg
        }
        return String(d)
      })
      .filter(Boolean)
      .join('; ')
  }
  if (typeof detail === 'object') return JSON.stringify(detail)
  return String(detail)
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const raw = error.response?.data?.detail
    const formatted = formatValidationDetail(raw)
    const message =
      formatted ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred. Please try again.'
    return Promise.reject(new Error(message))
  },
)

const TERMINAL_SUCCESS = new Set(['found', 'completed', 'complete', 'done', 'success'])
const TERMINAL_FAILURE = new Set(['failed', 'error', 'cancelled', 'canceled'])
const POLL_INTERVAL_MS = 2500
const MAX_JOB_WAIT_MS = 15 * 60 * 1000

function isTerminalSuccess(status) {
  return TERMINAL_SUCCESS.has(String(status || '').toLowerCase())
}

function isTerminalFailure(status) {
  return TERMINAL_FAILURE.has(String(status || '').toLowerCase())
}

function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    let timeoutId
    const onAbort = () => {
      clearTimeout(timeoutId)
      signal?.removeEventListener('abort', onAbort)
      reject(new DOMException('Aborted', 'AbortError'))
    }

    timeoutId = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)

    if (signal) {
      if (signal.aborted) {
        clearTimeout(timeoutId)
        reject(new DOMException('Aborted', 'AbortError'))
        return
      }
      signal.addEventListener('abort', onAbort)
    }
  })
}

/**
 * Backend contract:
 * - POST /query -> { status: "found", report } or { status: "processing", task_id }
 * - GET /status?task_id=... -> { status, report, error, steps }
 */
export async function runResearchQuery(query, options = {}) {
  const { signal, onProgress } = options
  const { data: initial } = await apiClient.post('/query', { query }, { signal })
  const initialStatus = String(initial?.status || '').toLowerCase()
  const initialTaskId = initial?.task_id || null
  const initialSteps = Array.isArray(initial?.steps) ? initial.steps : []

  onProgress?.({
    taskId: initialTaskId,
    status: initialStatus || 'processing',
    steps: initialSteps,
  })

  if (initial?.error || isTerminalFailure(initialStatus)) {
    throw new Error(initial?.error || 'Research task failed.')
  }

  if (initialStatus === 'found') {
    if (!initial?.report) {
      throw new Error('Cached result found but report content is empty.')
    }
    return {
      content: initial.report,
      taskId: null,
      steps: [],
      status: initialStatus,
    }
  }

  if (!initialTaskId) {
    throw new Error('No task ID returned by the backend.')
  }

  if (initial?.report && isTerminalSuccess(initialStatus)) {
    return {
      content: initial.report,
      taskId: initialTaskId,
      steps: initialSteps,
      status: initialStatus,
    }
  }

  const startedAt = Date.now()
  while (true) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    await delay(POLL_INTERVAL_MS, signal)

    const { data: statusPayload } = await apiClient.get('/status', {
      params: { task_id: initialTaskId },
      signal,
    })

    const polledStatus = String(statusPayload?.status || '').toLowerCase()
    const polledSteps = Array.isArray(statusPayload?.steps) ? statusPayload.steps : []

    onProgress?.({
      taskId: initialTaskId,
      status: polledStatus || 'processing',
      steps: polledSteps,
    })

    if (statusPayload?.error || isTerminalFailure(polledStatus)) {
      throw new Error(statusPayload?.error || 'Research task failed.')
    }

    if (isTerminalSuccess(polledStatus)) {
      if (!statusPayload?.report) {
        throw new Error('Research completed but no report was returned.')
      }
      return {
        content: statusPayload.report,
        taskId: initialTaskId,
        steps: polledSteps,
        status: polledStatus,
      }
    }

    if (Date.now() - startedAt > MAX_JOB_WAIT_MS) {
      throw new Error('Research is taking longer than expected. Please try again.')
    }
  }
}

export async function fetchCurrentUser(signal) {
  const { data } = await apiClient.get('/auth/me', { signal })
  return data
}

export default apiClient
