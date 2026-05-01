/**
 * components/ResearchResult.jsx
 * Renders the AI-generated research paper in a polished, readable format.
 * Provides copy-to-clipboard, PDF download, and back navigation.
 */

import React, { useState, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// react-markdown v9 strips `data:` URIs from image src by default, which
// removes the inline base64 charts/images produced by the report_finalizer
// node on the backend. Allow `data:image/...` while still blocking other
// potentially unsafe schemes (javascript:, vbscript:, file:, etc.).
const safeUrlTransform = (url) => {
  if (typeof url !== 'string') return ''
  if (/^data:image\/(png|jpe?g|gif|webp|svg\+xml|bmp);/i.test(url)) {
    return url
  }
  if (/^(https?:|mailto:|tel:|#|\/|\.\/|\.\.\/)/i.test(url)) {
    return url
  }
  return ''
}

// ─── Icons ────────────────────────────────────────────────────────────────────
const CopyIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
)
const CheckIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)
const DownloadIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
)
const ArrowLeftIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="19" y1="12" x2="5" y2="12" />
    <polyline points="12 19 5 12 12 5" />
  </svg>
)
const PrintIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 6 2 18 2 18 9" />
    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
    <rect x="6" y="14" width="12" height="8" />
  </svg>
)

// ─── Action Button ─────────────────────────────────────────────────────────────
const ActionButton = ({ onClick, icon, label, variant = 'ghost' }) => (
  <button
    onClick={onClick}
    className={`
      flex items-center gap-2 text-xs font-medium font-body px-3.5 py-2 rounded-lg
      transition-all duration-200 border
      ${variant === 'primary'
        ? 'bg-brand-50 border-brand-200 text-brand-700 hover:bg-brand-100 hover:border-brand-300'
        : 'bg-white border-ink-200 text-ink-600 hover:bg-ink-100 hover:text-ink-900 hover:border-ink-300'
      }
    `}
  >
    {icon}
    {label}
  </button>
)

// ─── Component ────────────────────────────────────────────────────────────────
const ResearchResult = ({ content, topic, taskId, steps = [], onBack }) => {
  const [copied, setCopied] = useState(false)
  const paperRef = useRef(null)

  // ── Copy to clipboard ────────────────────────────────────────
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      // Fallback for older browsers
      const el = document.createElement('textarea')
      el.value = content
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    }
  }

  // ── Download as .md file ─
  const handleDownloadMd = () => {
    const fallbackName = `${topic.slice(0, 50).replace(/[^a-z0-9]/gi, '_').toLowerCase()}_research.md`
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fallbackName
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Print / Save as PDF: only #research-pdf-root is visible (@media print in index.css)
  const handlePrint = () => {
    window.print()
  }

  // ── Word count ───────────────────────────────────────────────
  const wordCount = content.trim().split(/\s+/).length
  const completedStepCount = Array.isArray(steps) ? steps.length : 0

  return (
    <section className="w-full max-w-3xl mx-auto animate-fade-up">
      <div className="flex items-center justify-between gap-4 mb-6 flex-wrap">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-ink-600 hover:text-ink-900 text-sm font-medium transition-colors duration-200 group"
        >
          <span className="group-hover:-translate-x-0.5 transition-transform duration-200">
            <ArrowLeftIcon />
          </span>
          New Research
        </button>

        <div className="flex items-center gap-2 flex-wrap">
          <ActionButton
            onClick={handleCopy}
            icon={copied ? <CheckIcon /> : <CopyIcon />}
            label={copied ? 'Copied!' : 'Copy'}
            variant={copied ? 'primary' : 'ghost'}
          />
          <ActionButton
            onClick={handleDownloadMd}
            icon={<DownloadIcon />}
            label="Download .md"
          />
          <ActionButton
            onClick={handlePrint}
            icon={<PrintIcon />}
            label="Save PDF"
          />
        </div>
      </div>

      <div
        id="research-pdf-root"
        ref={paperRef}
        className="research-pdf-root bg-white border border-ink-200 rounded-2xl overflow-hidden shadow-xl shadow-ink-100/70"
      >
        <div className="print:hidden px-8 pt-8 pb-6 border-b border-ink-200">
          <div className="flex items-center gap-2 text-ink-500 font-mono text-[11px] uppercase tracking-widest mb-3">
            <span className="w-4 h-px bg-brand-500/30" />
            Research Paper
            <span className="w-4 h-px bg-brand-500/30" />
          </div>
          <h2 className="font-display text-2xl font-bold text-ink-900 leading-snug">
            {topic}
          </h2>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-ink-500 text-xs font-mono">
            <span>~{wordCount.toLocaleString()} words</span>
            <span className="text-ink-300 hidden sm:inline">·</span>
            <span>Generated by AI Research Agent</span>
            <span className="text-ink-300 hidden sm:inline">·</span>
            <span>{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
            {taskId ? (
              <>
                <span className="text-ink-300 hidden sm:inline">·</span>
                <span title={taskId}>Task {taskId.slice(0, 8)}…</span>
              </>
            ) : null}
            {completedStepCount > 0 ? (
              <>
                <span className="text-ink-300 hidden sm:inline">·</span>
                <span>{completedStepCount} streamed steps</span>
              </>
            ) : null}
          </div>
        </div>

        <div className="px-8 py-8">
          <div className="research-prose">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              urlTransform={safeUrlTransform}
            >
              {content}
            </ReactMarkdown>
          </div>
        </div>

        <div className="print:hidden px-8 py-5 border-t border-ink-200 flex items-center justify-between">
          <span className="text-ink-500 text-xs font-mono">
            AI-generated content · Verify with primary sources
          </span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-ink-500 hover:text-brand-700 text-xs font-mono transition-colors duration-200"
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
            {copied ? 'Copied' : 'Copy all'}
          </button>
        </div>
      </div>

      <div className="mt-8 text-center">
        <button
          onClick={onBack}
          className="btn-primary inline-flex items-center gap-2.5 text-sm"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Generate Another Research
        </button>
      </div>
    </section>
  )
}

export default ResearchResult