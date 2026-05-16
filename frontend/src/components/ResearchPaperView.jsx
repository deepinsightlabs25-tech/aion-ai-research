/**
 * ResearchPaperView.jsx
 * Renders IEEE-style two-column research papers (compiled PDF or LaTeX fallback).
 */

import React, { useEffect, useMemo, useState } from 'react'
import { parseLatexPaper, pdfBase64ToBlobUrl } from '../lib/latexPaper'

const ResearchPaperView = ({ latex, pdfBase64, metadata = {} }) => {
  const [pdfUrl, setPdfUrl] = useState(null)

  useEffect(() => {
    if (!pdfBase64) {
      setPdfUrl(null)
      return undefined
    }
    const url = pdfBase64ToBlobUrl(pdfBase64)
    setPdfUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [pdfBase64])

  const paper = useMemo(() => parseLatexPaper(latex || '', metadata), [latex, metadata])

  if (pdfUrl) {
    return (
      <div className="research-paper-pdf">
        <iframe
          title={paper.title}
          src={pdfUrl}
          className="w-full min-h-[80vh] rounded-lg border border-ink-200 bg-ink-50"
        />
        {metadata.compile_errors?.length > 0 ? (
          <p className="mt-3 text-xs text-amber-700 font-mono">
            Compile notes: {metadata.compile_errors.slice(0, 2).join('; ')}
          </p>
        ) : null}
      </div>
    )
  }

  return (
    <article className="research-paper-latex">
      <header className="research-paper-header text-center mb-8 pb-6 border-b border-ink-200">
        <h1 className="font-display text-2xl sm:text-3xl font-bold text-ink-900 leading-tight mb-4">
          {paper.title}
        </h1>
        {paper.abstract ? (
          <div className="text-left max-w-3xl mx-auto">
            <p className="text-[11px] font-mono uppercase tracking-widest text-ink-500 mb-2 text-center">
              Abstract
            </p>
            <p className="text-sm text-ink-700 leading-relaxed italic">{paper.abstract}</p>
          </div>
        ) : null}
      </header>

      <div className="research-paper-columns text-[13px] text-ink-800 leading-relaxed">
        {paper.sections.map((section) => (
          <section key={section.title} className="break-inside-avoid mb-6">
            <h2 className="font-display text-base font-bold text-ink-900 uppercase tracking-wide mb-3 mt-2">
              {section.title}
            </h2>
            {section.subsections.map((sub, idx) => (
              <div key={`${section.title}-${idx}`} className="mb-4">
                {sub.title ? (
                  <h3 className="font-semibold text-ink-800 text-sm mb-2">{sub.title}</h3>
                ) : null}
                {sub.paragraphs.map((para, pIdx) => (
                  <p key={pIdx} className="mb-3 text-justify hyphens-auto">
                    {para}
                  </p>
                ))}
              </div>
            ))}
          </section>
        ))}
      </div>

      {metadata.pdf_compiled === false ? (
        <p className="mt-6 text-xs text-amber-700 border border-amber-200 bg-amber-50 rounded-lg px-4 py-3 font-mono">
          PDF compilation failed on the server. Showing a text preview from the LaTeX source.
        </p>
      ) : null}
    </article>
  )
}

export default ResearchPaperView
