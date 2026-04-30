/**
 * components/Loader.jsx
 * Animated skeleton + status messages shown during AI generation.
 * Cycles through messages to keep the user engaged during the wait.
 */

import React, { useState, useEffect } from 'react'
import { parseStepNodeId, SUBAGENT_IDS } from '../lib/workflowGraph'

// ─── Loading messages that cycle every few seconds ───────────────────────────
const MESSAGES = [
  'Analyzing your research topic…',
  'Gathering relevant information…',
  'Structuring the research framework…',
  'Synthesizing key insights…',
  'Drafting comprehensive sections…',
  'Reviewing and refining content…',
  'Almost ready — finalizing your paper…',
]

// ─── Skeleton line widths (visual variety) ────────────────────────────────────
const SKELETON_LINES = [
  ['w-2/5', 'mb-6'], // h2 heading
  ['w-full', 'mb-2'],
  ['w-full', 'mb-2'],
  ['w-4/5', 'mb-6'],
  ['w-1/3', 'mb-4'], // h3 heading
  ['w-full', 'mb-2'],
  ['w-full', 'mb-2'],
  ['w-3/4', 'mb-6'],
  ['w-2/5', 'mb-4'], // h2 heading
  ['w-full', 'mb-2'],
  ['w-full', 'mb-2'],
  ['w-5/6', 'mb-2'],
  ['w-full', 'mb-2'],
  ['w-2/3', 'mb-6'],
]

// ─── Agent activity: human titles + what each step is doing ───────────────────
const ACTIVITY_TITLE_BY_NODE = {
  classifier: 'Classifier',
  task_generator: 'Task Generator',
  aggregator: 'Aggregator',
  writer: 'Writer',
  validator: 'Validator',
  cleanup: 'Cleanup',
}

const ACTIVITY_DETAIL_BY_NODE = {
  classifier: 'Understanding user intention and Planning',
  task_generator: 'Assembling and Calling Agents',
  aggregator: 'Consolidating Information',
  writer: 'Generating Report',
  validator: 'Checking and refining report',
}

function formatFallbackStepTitle(rawStep) {
  const clean = String(rawStep || '').trim()
  if (!clean) return 'Working'
  return clean
    .replace(/^step:\s*/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

/** e.g. web_research_agent → "Web Research Expert" */
function agentNodeToExpertTitle(nodeId) {
  const base = String(nodeId || '').replace(/_agent$/i, '')
  const words = base.split('_').filter(Boolean)
  if (words.length === 0) return 'Expert'
  const titled = words
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
  return `${titled} Expert`
}

function activityLabelsFromStep(rawStep) {
  const nodeId = parseStepNodeId(rawStep)
  if (!nodeId) {
    return { title: formatFallbackStepTitle(rawStep), detail: null }
  }

  if (ACTIVITY_TITLE_BY_NODE[nodeId]) {
    return {
      title: ACTIVITY_TITLE_BY_NODE[nodeId],
      detail: ACTIVITY_DETAIL_BY_NODE[nodeId] ?? null,
    }
  }

  if (SUBAGENT_IDS.includes(nodeId) || nodeId.endsWith('_agent')) {
    return { title: agentNodeToExpertTitle(nodeId), detail: null }
  }

  return { title: formatFallbackStepTitle(rawStep), detail: null }
}

const Loader = ({ statusHint, steps = [] }) => {
  const [msgIndex, setMsgIndex] = useState(0)
  const stepList = Array.isArray(steps) ? steps : []
  const latestStep = stepList.length > 0 ? stepList[stepList.length - 1] : null
  const latestLabels = latestStep ? activityLabelsFromStep(latestStep.step) : null

  // Cycle through loading messages when agent steps are not yet available
  useEffect(() => {
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % MESSAGES.length)
    }, 3500)
    return () => clearInterval(interval)
  }, [])

  const hasAgentCopy = Boolean(
    latestLabels && (latestLabels.detail || latestLabels.title),
  )

  return (
    <section className="w-full max-w-3xl mx-auto animate-fade-up">
      <div className="mb-6 rounded-2xl border border-ink-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-start gap-4 p-4 sm:p-5 bg-gradient-to-br from-white to-brand-50/40">
          <div className="relative flex-shrink-0 mt-1">
            <div className="w-2.5 h-2.5 bg-brand-600 rounded-full" />
            <div className="absolute inset-0 w-2.5 h-2.5 bg-brand-600 rounded-full animate-ping opacity-60" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1.5">
                {hasAgentCopy ? (
                  <p
                    key={String(latestStep?.step)}
                    className="text-ink-900 font-body text-sm font-semibold leading-snug"
                  >
                    {latestLabels.detail || latestLabels.title}
                  </p>
                ) : (
                  <p
                    key={statusHint ? `hint-${statusHint}` : `msg-${msgIndex}`}
                    className="text-ink-900 font-body text-sm font-semibold leading-snug animate-fade-up"
                  >
                    {statusHint || MESSAGES[msgIndex]}
                  </p>
                )}
                <p className="processing-footnote text-ink-500 text-xs leading-relaxed inline-flex flex-wrap items-baseline gap-0">
                  <span>Deep research can take several minutes</span>
                  <span className="processing-footnote__dots font-mono tracking-tight" aria-hidden>
                    <span>.</span>
                    <span>.</span>
                    <span>.</span>
                  </span>
                </p>
              </div>
              <div className="flex-shrink-0 pt-0.5">
                <svg
                  className="animate-spin text-brand-500/70"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden
                >
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeOpacity="0.2" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white border border-ink-200 rounded-2xl p-8 space-y-1 shadow-xl shadow-ink-100/70">
        <div className="skeleton h-3 w-20 rounded-full mb-2 opacity-60" />
        <div className="skeleton h-7 w-3/4 rounded-md mb-1" />
        <div className="skeleton h-7 w-1/2 rounded-md mb-8" />

        {SKELETON_LINES.map(([ width, spacing ], i) => (
          <div
            key={i}
            className={`skeleton h-3.5 ${width} ${spacing} rounded-full`}
            style={{ opacity: 0.5 - i * 0.01, animationDelay: `${i * 80}ms` }}
          />
        ))}
      </div>
    </section>
  )
}

export default Loader
