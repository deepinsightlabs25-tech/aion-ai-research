/**
 * Helpers for LaTeX research papers (IEEE two-column) returned by the backend.
 */

/** True when text looks like a full LaTeX document. */
export function isLatexDocument(text) {
  if (!text || typeof text !== 'string') return false
  return /\\documentclass/.test(text.trim())
}

/** Build a blob URL for an embedded base64 PDF (caller must revoke when done). */
export function pdfBase64ToBlobUrl(base64) {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  const blob = new Blob([bytes], { type: 'application/pdf' })
  return URL.createObjectURL(blob)
}

/** Rough plain-text cleanup for LaTeX fragments shown in the HTML fallback. */
export function stripLatexMarkup(source) {
  if (!source) return ''
  let text = source
  text = text.replace(/%[^\n]*/g, '')
  text = text.replace(/\\cite\{[^}]*\}/g, '')
  text = text.replace(/\\ref\{[^}]*\}/g, '')
  text = text.replace(/\\label\{[^}]*\}/g, '')
  text = text.replace(/\\textbf\{([^}]*)\}/g, '$1')
  text = text.replace(/\\textit\{([^}]*)\}/g, '$1')
  text = text.replace(/\\emph\{([^}]*)\}/g, '$1')
  text = text.replace(/\\texttt\{([^}]*)\}/g, '$1')
  text = text.replace(/``/g, '"').replace(/''/g, '"')
  text = text.replace(/\\begin\{[^}]+\}[\s\S]*?\\end\{[^}]+\}/g, ' ')
  text = text.replace(/\\[a-zA-Z@]+\*?(\[[^\]]*\])?(\{[^}]*\})?/g, ' ')
  text = text.replace(/[{}\\]/g, ' ')
  text = text.replace(/\s+/g, ' ').trim()
  return text
}

function extractBlock(latex, envName) {
  const re = new RegExp(
    `\\\\begin\\{${envName}\\}([\\s\\S]*?)\\\\end\\{${envName}\\}`,
    'i',
  )
  const match = latex.match(re)
  return match ? match[1].trim() : ''
}

/** Parse LaTeX into structured fields for the two-column HTML fallback. */
export function parseLatexPaper(latex, metadata = {}) {
  const titleMatch = latex.match(/\\title\{([^}]+)\}/)
  const title = metadata.title || (titleMatch ? titleMatch[1] : 'Research Paper')
  const abstractRaw = extractBlock(latex, 'abstract')
  const abstract = metadata.abstract || stripLatexMarkup(abstractRaw)

  const bodyStart = latex.indexOf('\\begin{document}')
  const bodyEnd = latex.lastIndexOf('\\end{document}')
  let body = latex
  if (bodyStart >= 0 && bodyEnd > bodyStart) {
    body = latex.slice(bodyStart + '\\begin{document}'.length, bodyEnd)
  }

  body = body.replace(/\\maketitle/g, '')
  body = body.replace(/\\begin{abstract}[\s\S]*?\\end{abstract}/g, '')
  body = body.replace(/\\begin{thebibliography}[\s\S]*?\\end{thebibliography}/g, '')

  const sections = []
  const sectionParts = body.split(/(?=\\section\*?\{)/).filter(Boolean)

  for (const part of sectionParts) {
    const heading = part.match(/^\\section\*?\{([^}]+)\}/)
    if (!heading) continue
    const sectionTitle = heading[1]
    let remainder = part.slice(heading[0].length).trim()

    const subsections = []
    const subParts = remainder.split(/(?=\\subsection\*?\{)/)
    const intro = subParts[0]?.trim()

    if (intro) {
      subsections.push({ title: null, paragraphs: splitParagraphs(intro) })
    }

    for (let i = 1; i < subParts.length; i += 1) {
      const sub = subParts[i]
      const subHeading = sub.match(/^\\subsection\*?\{([^}]+)\}/)
      if (!subHeading) continue
      const subTitle = subHeading[1]
      const subBody = sub.slice(subHeading[0].length).trim()
      subsections.push({ title: subTitle, paragraphs: splitParagraphs(subBody) })
    }

    if (!subsections.length) {
      subsections.push({ title: null, paragraphs: splitParagraphs(remainder) })
    }

    sections.push({ title: sectionTitle, subsections })
  }

  if (!sections.length && metadata.sections?.length) {
    for (const name of metadata.sections) {
      sections.push({
        title: name,
        subsections: [{ title: null, paragraphs: [] }],
      })
    }
  }

  return {
    title,
    abstract,
    sections,
    wordCount: metadata.word_count || latex.split(/\s+/).filter(Boolean).length,
  }
}

function splitParagraphs(text) {
  const chunks = text
    .split(/\n\s*\n+/)
    .map((p) => stripLatexMarkup(p))
    .filter((p) => p.length > 20)
  if (chunks.length) return chunks
  const single = stripLatexMarkup(text)
  return single.length > 20 ? [single] : []
}

/** Normalize API `research_paper` payload shapes. */
export function normalizeResearchPaper(researchPaper, content) {
  if (researchPaper && typeof researchPaper === 'object') {
    return {
      latex: researchPaper.latex || '',
      pdfBase64: researchPaper.pdf_base64 || null,
      metadata: researchPaper.metadata || {},
    }
  }
  if (isLatexDocument(content)) {
    return { latex: content, pdfBase64: null, metadata: {} }
  }
  return null
}
