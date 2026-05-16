/**
 * pages/Home.jsx
 * Main page that orchestrates the three states:
 *   idle → loading → result (or error)
 * Manages all API interaction and scroll behavior.
 */

import React, { useState, useRef, useEffect } from 'react'
import TopicInput      from '../components/TopicInput'
import Loader             from '../components/Loader'
import WorkflowGraphPanel from '../components/WorkflowGraphPanel'
import ResearchResult     from '../components/ResearchResult'
import { runResearchQuery } from '../services/api'

// ─── App States ───────────────────────────────────────────────────────────────
const STATE = {
  IDLE:    'idle',
  LOADING: 'loading',
  RESULT:  'result',
  ERROR:   'error',
}

// ─── Error Banner ─────────────────────────────────────────────────────────────
const ErrorBanner = ({ message, onRetry }) => (
  <div className="w-full max-w-3xl mx-auto animate-fade-up">
    <div className="bg-white border border-red-200 rounded-2xl p-8 text-center shadow-lg shadow-red-100/60">
      <div className="w-12 h-12 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-red-500">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h3 className="font-display text-xl font-semibold text-ink-900 mb-2">
        Something went wrong
      </h3>
      <p className="text-ink-600 text-sm leading-relaxed mb-6 max-w-md mx-auto">
        {message}
      </p>
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 text-sm font-medium text-red-600 border border-red-200 bg-white hover:bg-red-50 rounded-lg px-5 py-2.5 transition-all duration-200"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 .49-4.95" />
        </svg>
        Try Again
      </button>
    </div>
  </div>
)

// ─── Component ────────────────────────────────────────────────────────────────
const Home = ({ isAuthenticated, onRequireLogin }) => {
  const [appState, setAppState] = useState(STATE.IDLE)
  const [research, setResearch] = useState(null)   // { topic, content, taskId?, steps? }
  const [errorMsg, setErrorMsg] = useState('')
  const [jobStatus, setJobStatus] = useState('')
  const [progressSteps, setProgressSteps] = useState([])

  const resultRef  = useRef(null)
  const topInputRef = useRef(null)
  const abortRef = useRef(null)

  // Auto-scroll to result section when it appears
  useEffect(() => {
    if (appState === STATE.LOADING || appState === STATE.RESULT || appState === STATE.ERROR) {
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    }
  }, [appState])

  // ── Submit handler ──────────────────────────────────────────
  const handleSubmit = async (topic) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setAppState(STATE.LOADING)
    setErrorMsg('')
    setResearch(null)
    setJobStatus('Submitting…')
    setProgressSteps([])

    try {
      const data = await runResearchQuery(topic, {
        signal: controller.signal,
        onProgress: ({ status, steps }) => {
          const label = String(status || '').replace(/_/g, ' ')
          setJobStatus(label ? label.charAt(0).toUpperCase() + label.slice(1) : '')
          setProgressSteps(Array.isArray(steps) ? steps : [])
        },
      })

      if (!data?.content) {
        throw new Error('No content returned from the server. Please try again.')
      }

      setResearch({
        topic,
        content: data.content,
        researchPaper: data.researchPaper ?? null,
        taskId: data.taskId ?? null,
        steps: data.steps ?? [],
      })
      setAppState(STATE.RESULT)
    } catch (err) {
      if (err?.name === 'AbortError') return
      setErrorMsg(err.message || 'Failed to generate research. Please check your connection and try again.')
      setAppState(STATE.ERROR)
    } finally {
      setJobStatus('')
    }
  }

  // ── Reset to idle (back button) ─────────────────────────────
  const handleReset = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setAppState(STATE.IDLE)
    setResearch(null)
    setErrorMsg('')
    setJobStatus('')
    setProgressSteps([])
    setTimeout(() => {
      topInputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
  }

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  return (
    <main className="min-h-screen pt-16">
      <section
        ref={topInputRef}
        className={`
          flex flex-col items-center justify-center px-4 transition-all duration-500
          ${appState === STATE.IDLE
            ? 'min-h-[92vh] pb-24'
            : 'pt-12 pb-10 min-h-0'
          }
        `}
      >
        <div
          className="pointer-events-none fixed top-0 left-1/2 -translate-x-1/2 w-[720px] h-[320px] opacity-70"
          style={{
            background: 'radial-gradient(ellipse at center top, rgba(79,70,229,0.18) 0%, transparent 72%)',
          }}
        />

        <TopicInput
          onSubmit={handleSubmit}
          isLoading={appState === STATE.LOADING}
          isAuthenticated={isAuthenticated}
          onRequireLogin={onRequireLogin}
        />
      </section>

      {appState !== STATE.IDLE && (
        <section
          ref={resultRef}
          className="px-4 pb-24 flex flex-col items-center"
        >
          <div className="w-full max-w-7xl mb-12 flex items-center gap-4">
            <div className="flex-1 h-px bg-ink-200" />
            <span className="text-ink-500 font-mono text-[11px] uppercase tracking-wider">
              {appState === STATE.LOADING ? '' : appState === STATE.RESULT ? 'Result' : 'Error'}
            </span>
            <div className="flex-1 h-px bg-ink-200" />
          </div>

          {appState === STATE.LOADING && (
            <div className="w-full max-w-6xl xl:max-w-7xl mx-auto flex flex-col lg:flex-row gap-8 lg:gap-10 items-stretch justify-center animate-fade-up">
              <div className="flex-1 min-w-0 w-full max-w-3xl lg:mx-0 mx-auto">
                <Loader statusHint={jobStatus} steps={progressSteps} />
              </div>
              <WorkflowGraphPanel
                steps={progressSteps}
                className="w-full max-w-md lg:max-w-[380px] mx-auto lg:mx-0 lg:sticky lg:top-24 lg:self-start shrink-0"
              />
            </div>
          )}

          {appState === STATE.RESULT && research && (
            <ResearchResult
              content={research.content}
              researchPaper={research.researchPaper}
              topic={research.topic}
              taskId={research.taskId}
              steps={research.steps}
              onBack={handleReset}
            />
          )}

          {appState === STATE.ERROR && (
            <ErrorBanner message={errorMsg} onRetry={handleReset} />
          )}
        </section>
      )}

      {appState === STATE.IDLE && (
        <footer className="text-center pb-10 text-ink-500 text-xs font-mono">
          Built for modern research workflows
        </footer>
      )}
    </main>
  )
}

export default Home
