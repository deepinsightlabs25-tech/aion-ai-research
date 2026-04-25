/**
 * components/Loader.jsx
 * Animated skeleton + status messages shown during AI generation.
 * Cycles through messages to keep the user engaged during the wait.
 */

import React, { useState, useEffect } from 'react'

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

// ─── Component ────────────────────────────────────────────────────────────────
function formatStepName(rawStep) {
  const clean = String(rawStep || '').trim()
  if (!clean) return 'Working'
  return clean
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

const Loader = ({ statusHint, steps = [] }) => {
  const [msgIndex, setMsgIndex] = useState(0)
  const recentSteps = Array.isArray(steps) ? steps.slice(-4) : []

  // Cycle through loading messages every 3.5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % MESSAGES.length)
    }, 3500)
    return () => clearInterval(interval)
  }, [])

  return (
    <section className="w-full max-w-3xl mx-auto animate-fade-up">
      <div className="mb-8 flex items-center gap-4 p-4 bg-white border border-ink-200 rounded-xl shadow-sm">
        <div className="relative flex-shrink-0">
          <div className="w-2.5 h-2.5 bg-brand-600 rounded-full" />
          <div className="absolute inset-0 w-2.5 h-2.5 bg-brand-600 rounded-full animate-ping opacity-60" />
        </div>

        <div className="flex-1 min-w-0">
          <p
            key={msgIndex}
            className="text-ink-800 font-body text-sm font-semibold truncate animate-fade-up"
          >
            {MESSAGES[msgIndex]}
          </p>
          <p className="text-ink-500 text-xs font-mono mt-0.5">
            {statusHint ? (
              <>
                <span className="text-brand-600">Server status:</span> {statusHint}
                <span className="text-ink-400"> · </span>
              </>
            ) : null}
            This may take several minutes for deep research
          </p>
        </div>

        <div className="flex-shrink-0">
          <svg
            className="animate-spin text-brand-500/70"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeOpacity="0.2" />
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
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

      {recentSteps.length > 0 && (
        <div className="mt-6 rounded-2xl border border-ink-200 bg-white p-5 shadow-sm">
          <div className="mb-3 text-[11px] uppercase tracking-wider font-mono text-ink-500">
            Live agent steps
          </div>
          <ul className="space-y-2.5">
            {recentSteps.map((item, index) => (
              <li key={`${item.step || 'step'}-${index}`} className="text-sm text-ink-300">
                <span className="text-brand-700 font-semibold">{formatStepName(item.step)}</span>
                {item.content ? (
                  <span className="text-ink-600 ml-2">
                    {String(item.content).slice(0, 100)}
                    {String(item.content).length > 100 ? '…' : ''}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default Loader
