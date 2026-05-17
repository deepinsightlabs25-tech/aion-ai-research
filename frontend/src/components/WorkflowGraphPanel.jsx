/**
 * Live LangGraph-style visualization; node highlights follow streamed /status steps.
 */

import React, { useMemo } from 'react'
import {
  NODE_LAYOUT,
  SUBAGENT_IDS,
  WORKFLOW_EDGES,
  getWorkflowGraphState,
} from '../lib/workflowGraph'

const VB = { w: 300, h: 510 }

function humanizeId(id) {
  if (!id) return ''
  if (id === '__start__') return 'Start'
  if (id === '__end__') return 'Done'
  return String(id)
    .replace(/_agent$/i, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function edgePath(fromId, toId, kind) {
  const a = NODE_LAYOUT[fromId]
  const b = NODE_LAYOUT[toId]
  if (!a || !b) return ''
  const x1 = a.x
  const y1 = a.y
  const x2 = b.x
  const y2 = b.y

  if (kind === 'rewrite') {
    // Validator (below) → Writer (above); curve outward to suggest a rewrite loop.
    const mid = (y1 + y2) / 2
    return `M ${x1} ${y1} C ${x1 + 88} ${mid} ${x2 + 88} ${mid} ${x2} ${y2}`
  }

  return `M ${x1} ${y1} L ${x2} ${y2}`
}

function WorkflowGraphPanel({ steps = [], className = '' }) {
  const { activeId, visited, sequence } = useMemo(() => getWorkflowGraphState(steps), [steps])
  const anyProgress = sequence.length > 0
  const prevId = sequence.length >= 2 ? sequence[sequence.length - 2] : null

  /** Only nodes that have run or are running — no dimmed “future” graph */
  const visibleIds = useMemo(() => {
    const s = new Set(visited)
    if (anyProgress) s.add('__start__')
    if (s.has('cleanup')) s.add('__end__')
    return s
  }, [visited, anyProgress])

  const activeLabel = activeId ? humanizeId(activeId) : 'Waiting…'

  /** Only one incoming edge is “live” for the current step (writer has two possible inputs). */
  const edgeIsHot = (from, to, kind) => {
    if (!activeId || to !== activeId) return false
    if (activeId === 'writer') {
      if (prevId === 'validator') return kind === 'rewrite' && from === 'validator'
      return from === 'aggregator' && !kind
    }
    if (activeId === 'aggregator' && prevId && SUBAGENT_IDS.includes(prevId)) {
      return from === prevId
    }
    return true
  }

  return (
    <aside
      className={`
        rounded-2xl border border-ink-200 bg-white shadow-lg shadow-ink-100/80 overflow-hidden
        wf-graph-panel
        ${className}
      `}
      aria-label={`Workflow graph. Current step: ${activeLabel}`}
    >
      <div className="px-4 py-3 border-b border-ink-100 bg-gradient-to-r from-brand-50/90 to-white">
        {/* <p className="text-[11px] uppercase tracking-wider font-mono text-ink-500">
          LangGraph · Live
        </p> */}
        <p className="text-sm font-semibold text-ink-900 mt-0.5 truncate" title={activeLabel}>
          {activeId ? (
            <>
              <span className="text-brand-700">Active:</span> {activeLabel}
            </>
          ) : (
            <span className="text-ink-500 font-normal">Connecting to agent…</span>
          )}
        </p>
      </div>

      <div className="p-3 sm:p-4 bg-gradient-to-b from-ink-50/40 to-white">
        <svg
          viewBox={`0 0 ${VB.w} ${VB.h}`}
          className="w-full h-auto block select-none"
          role="img"
          aria-hidden
        >
          <defs>
            <filter id="wf-glow" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="2.5" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* edges (only between visible nodes) */}
          <g className="wf-edges">
            {WORKFLOW_EDGES.map(({ from, to, kind }, i) => {
              if (!visibleIds.has(from) || !visibleIds.has(to)) return null
              const d = edgePath(from, to, kind)
              if (!d) return null
              const fromSeen =
                from === '__start__' ? anyProgress : visited.has(from)
              const toSeen = visited.has(to)
              const traversed = fromSeen && toSeen && kind !== 'rewrite'
              const rewriteUsed = kind === 'rewrite' && visited.has('validator') && visited.has('writer')
              const hot = edgeIsHot(from, to, kind)

              let stroke = '#e2e8f0'
              let strokeW = 1.25
              let opacity = 0.5
              if (kind === 'rewrite') {
                stroke = '#cbd5e1'
                strokeW = 1.1
                opacity = 0.4
              }
              if (traversed || rewriteUsed) {
                stroke = '#a5b4fc'
                opacity = 0.88
              }
              if (hot) {
                stroke = '#6366f1'
                strokeW = 2.4
                opacity = 1
              }

              return (
                <path
                  key={`${from}-${to}-${i}`}
                  d={d}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={strokeW}
                  strokeLinecap="round"
                  strokeDasharray={kind === 'rewrite' ? '5 6' : hot ? '10 14' : undefined}
                  opacity={opacity}
                  className={hot ? 'wf-edge--flow' : ''}
                  style={{
                    transition: 'stroke 0.35s ease, opacity 0.35s ease, stroke-width 0.35s ease',
                  }}
                />
              )
            })}
          </g>

          {/* nodes (only visited / active; future steps stay hidden) */}
          <g>
            {Object.entries(NODE_LAYOUT)
              .filter(([id]) => visibleIds.has(id))
              .map(([id, cfg]) => {
              const { x, y, label, w, h, rx } = cfg
              const isActive = id === activeId
              const passedStart = id === '__start__' && anyProgress
              const isDone =
                !isActive && (visited.has(id) || passedStart || id === '__end__')

              let fill = '#f8fafc'
              let stroke = '#e2e8f0'
              let textCls = 'fill-ink-400'
              if (id === '__start__' || id === '__end__') {
                fill = '#f1f5f9'
              }
              if (isDone) {
                fill = '#eef2ff'
                stroke = '#a5b4fc'
                textCls = 'fill-ink-600'
              }
              if (isActive) {
                fill = '#4f46e5'
                stroke = '#4338ca'
                textCls = 'fill-white'
              }

              const dw = isActive ? 3 : 0
              const dh = isActive ? 3 : 0
              const rw = w + dw
              const rh = h + dh
              const rectX = x - rw / 2
              const rectY = y - rh / 2
              const fontSize = h <= 30 ? 8.5 : 9.5
              const filter = isActive ? 'url(#wf-glow)' : undefined
              const pingPad = 6
              const pingRx = rx + 4

              return (
                <g
                  key={id}
                  className="transition-all duration-300"
                >
                  <rect
                    x={rectX}
                    y={rectY}
                    width={rw}
                    height={rh}
                    rx={rx}
                    ry={rx}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={isActive ? 2.25 : 1.5}
                    filter={filter}
                    className={isActive ? 'wf-node-active' : ''}
                  />
                  {isActive ? (
                    <rect
                      x={rectX - pingPad}
                      y={rectY - pingPad}
                      width={rw + pingPad * 2}
                      height={rh + pingPad * 2}
                      rx={pingRx}
                      ry={pingRx}
                      fill="none"
                      stroke="#818cf8"
                      strokeWidth="1"
                      opacity="0.45"
                      className="animate-ping wf-ping-ring"
                      style={{ animationDuration: '2.2s' }}
                    />
                  ) : null}
                  <text
                    x={x}
                    y={y + fontSize * 0.35}
                    textAnchor="middle"
                    className={`font-mono font-semibold ${textCls}`}
                    style={{
                      fontSize: `${fontSize}px`,
                      pointerEvents: 'none',
                    }}
                  >
                    {label}
                  </text>
                </g>
              )
            })}
          </g>
        </svg>

        {/* <p className="mt-3 text-[11px] text-ink-500 leading-relaxed font-mono border-t border-ink-100 pt-3">
          Only steps that have finished or are running are shown; the rest stay hidden until the
          workflow reaches them.
        </p> */}
      </div>
    </aside>
  )
}

export default WorkflowGraphPanel
