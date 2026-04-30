/**
 * Mirrors backend LangGraph in lg_workflow_agent/graph.py
 * Step payloads use shape: { step: "step: <node_id>", content, ... }
 */

export const SUBAGENT_IDS = [
  'data_collection_agent',
  'statistics_agent',
  'citation_agent',
  'web_research_agent',
  'latest_news_collection_agent',
]

/** Single size for every workflow node (SVG units) — keeps the graph visually even */
const BOX = { w: 54, h: 34, rx: 10 }

/** @type {Record<string, { x: number, y: number, label: string, w: number, h: number, rx: number }>} */
export const NODE_LAYOUT = {
  __start__: { x: 150, y: 18, label: 'Start', ...BOX },
  classifier: { x: 150, y: 58, label: 'Classify', ...BOX },
  task_generator: { x: 150, y: 108, label: 'Tasks', ...BOX },
  data_collection_agent: { x: 30, y: 172, label: 'Data', ...BOX },
  statistics_agent: { x: 90, y: 172, label: 'Stats', ...BOX },
  citation_agent: { x: 150, y: 172, label: 'Cite', ...BOX },
  web_research_agent: { x: 210, y: 172, label: 'Web', ...BOX },
  latest_news_collection_agent: { x: 270, y: 172, label: 'News', ...BOX },
  aggregator: { x: 150, y: 238, label: 'Merge', ...BOX },
  writer: { x: 150, y: 298, label: 'Write', ...BOX },
  validator: { x: 150, y: 358, label: 'Check', ...BOX },
  cleanup: { x: 150, y: 418, label: 'Save', ...BOX },
  __end__: { x: 150, y: 478, label: 'Done', ...BOX },
}

/**
 * @param {unknown} rawStepField
 * @returns {string|null} backend node id or null
 */
export function parseStepNodeId(rawStepField) {
  const s = String(rawStepField ?? '').trim()
  if (!s) return null
  const m = s.match(/^step:\s*(.+)$/i)
  const id = (m ? m[1] : s).trim()
  if (!id) return null
  return id
}

/**
 * @param {Array<{ step?: string }>} steps
 * @returns {{ activeId: string | null, visited: Set<string>, sequence: string[] }}
 */
export function getWorkflowGraphState(steps) {
  const sequence = []
  const list = Array.isArray(steps) ? steps : []
  for (const item of list) {
    const id = parseStepNodeId(item?.step)
    if (id) sequence.push(id)
  }
  const activeId = sequence.length ? sequence[sequence.length - 1] : null
  const visited = new Set(sequence)
  return { activeId, visited, sequence }
}

/**
 * Directed edges for drawing (matches workflow topology).
 * @type {Array<{ from: string, to: string, kind?: 'rewrite' }>}
 */
export const WORKFLOW_EDGES = [
  { from: '__start__', to: 'classifier' },
  { from: 'classifier', to: 'task_generator' },
  ...SUBAGENT_IDS.map((id) => ({ from: 'task_generator', to: id })),
  ...SUBAGENT_IDS.map((id) => ({ from: id, to: 'aggregator' })),
  { from: 'aggregator', to: 'writer' },
  { from: 'writer', to: 'validator' },
  { from: 'validator', to: 'writer', kind: 'rewrite' },
  { from: 'validator', to: 'cleanup' },
  { from: 'cleanup', to: '__end__' },
]
