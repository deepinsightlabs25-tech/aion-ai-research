"""LangGraph node factories for the lg_workflow_agent workflow."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Send

from .prompts import (
    AGGREGATOR_PROMPT,
    CITATION_PROMPT,
    CLASSIFIER_PROMPT,
    DATA_COLLECTION_PROMPT,
    LATEST_NEWS_COLLECTION_PROMPT,
    REPORT_FINALIZER_PROMPT,
    REWRITE_NOTE_TEMPLATE,
    STATISTICS_PROMPT,
    TASK_GENERATOR_PROMPT,
    VALIDATOR_PROMPT,
    WEB_RESEARCH_PROMPT,
    WRITER_PROMPT,
)
from .chart_generator import generate_charts_for_report
from .state import WorkflowState
from .sub_agents import build_role_runners
from .tools import extract_urls, validate_urls

# Map of role -> sub-agent system prompt.
ROLE_PROMPTS: dict[str, str] = {
    # deep_research roles
    "data_collection": DATA_COLLECTION_PROMPT,
    "statistics": STATISTICS_PROMPT,
    "citation": CITATION_PROMPT,
    # non-deep roles
    "web_research": WEB_RESEARCH_PROMPT,
    "latest_news_collection": LATEST_NEWS_COLLECTION_PROMPT,
}

# Roles available per query type.
ROLES_BY_TYPE: dict[str, list[str]] = {
    "deep_research": ["data_collection", "statistics", "citation"],
    "blog": ["web_research", "latest_news_collection"],
    "comparative": ["web_research", "latest_news_collection"],
    "summary": ["web_research", "latest_news_collection"],
}

MAX_REWRITES = 2


# Phrases that indicate the LLM is leaking tool/process meta-commentary.
# Any paragraph containing one of these (case-insensitive) is dropped from
# the final draft as a defensive post-processing step.
_LEAKAGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfetch_trends\b",
        r"\bthink_tool\b",
        r"\bsub[- ]?agent(s)?\b",
        r"\btool (limitation|failure|error|did not|was unable|could not)\b",
        r"\bdue to (tool|api|model) (limitation|constraint|issue|error)",
        r"\bcould not be (fully )?(gathered|obtained|retrieved|completed|determined)\b",
        r"\b(was|were) unable to (retrieve|gather|obtain|access)\b",
        r"\bno (data|results|information) (was|were) (returned|available|found)\b",
        r"\binsufficient data (was|is) available\b",
        r"\bas an ai\b",
        r"\bbased on the (information|data) provided\b",
        r"\bthe tool did not (yield|return|provide)\b",
        r"\bcomprehensive overview .* could not\b",
    )
)


def _sanitize_report(text: str) -> str:
    """Strip paragraphs that leak tool/process meta-commentary.

    Acts as a defense-in-depth filter on top of the writer prompt. Removes any
    paragraph (separated by blank lines) that matches a known leakage pattern.
    Preserves headings and inline citations untouched.
    """
    if not text:
        return text
    paragraphs = re.split(r"(\n\s*\n)", text)  # keep separators
    out: list[str] = []
    for chunk in paragraphs:
        if chunk.strip().startswith(("#", "-", "*", "[", "|")):
            # Preserve headings, list items, references, and tables verbatim.
            out.append(chunk)
            continue
        if any(p.search(chunk) for p in _LEAKAGE_PATTERNS):
            continue
        out.append(chunk)
    cleaned = "".join(out)
    # Collapse 3+ blank lines that may result from removed paragraphs.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or text  # never return empty


# --------------------------- helpers ---------------------------------------


def _safe_json_load(text: str) -> dict:
    """Load JSON from an LLM response, tolerating ```json fences."""
    if not text:
        return {}
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # Try to extract first JSON object
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}


def _persist(db, task_id: str, stage: str, payload: Any) -> None:
    """Best-effort persistence of an intermediate stage to Qdrant."""
    if db is None or not task_id:
        return
    try:
        snippet = payload if isinstance(payload, str) else json.dumps(payload, default=str)[:8000]
        db.update_intermediate_report(task_id, f"[{stage}]\n{snippet}")
    except Exception:
        # Persistence is best-effort; never break the workflow.
        pass


# --------------------------- node factories --------------------------------


def create_node_classifier(llm, db):
    """Classify the user query into a research mode."""

    # Performance optimization: Query classification cache
    QUERY_TYPE_CACHE = {
        "trends": "summary",
        "latest": "summary",
        "news": "summary",
        "compare": "comparative",
        "vs": "comparative",
        "versus": "comparative",
        "difference": "comparative",
        "research": "deep_research",
        "study": "deep_research",
        "analysis": "deep_research",
        "blog": "blog",
        "article": "blog",
        "guide": "blog",
    }

    def node_classifier(state: WorkflowState):
        query_lower = state["query"].lower()

        # Quick cache lookup before LLM call (saves 3-5 seconds)
        for keyword, qtype in QUERY_TYPE_CACHE.items():
            if keyword in query_lower:
                out = {
                    "query_type": qtype,
                    "classification_rationale": f"cached match: '{keyword}'",
                }
                _persist(db, state.get("task_id", ""), "classify", out)
                return out

        # Fallback to LLM classification
        prompt = CLASSIFIER_PROMPT.format(query=state["query"])
        response = llm.invoke(prompt)
        parsed = _safe_json_load(getattr(response, "content", "") or "")

        qtype = parsed.get("query_type", "summary")
        if qtype not in ROLES_BY_TYPE:
            qtype = "summary"

        out = {
            "query_type": qtype,
            "classification_rationale": parsed.get("rationale", ""),
        }
        _persist(db, state.get("task_id", ""), "classify", out)
        return out

    return node_classifier


def create_node_task_generator(llm, db):
    """Decompose the query into role-tagged sub-tasks."""

    def node_task_generator(state: WorkflowState):
        qtype = state.get("query_type", "summary")
        query = state["query"]

        # Performance optimization: Smart sub-agent selection based on query complexity
        query_word_count = len(query.split())

        # Very short queries (< 5 words) - use minimal agents (saves 10-15s)
        if query_word_count < 5 and qtype in ["summary", "blog"]:
            roles = ["web_research"]  # Just 1 agent
        # Short queries (< 8 words) - use reduced agents (saves 5-10s)
        elif query_word_count < 8 and qtype == "summary":
            roles = ["web_research", "latest_news_collection"]  # Just 2 agents
        else:
            # Normal/complex queries - use all agents (production default)
            roles = ROLES_BY_TYPE[qtype]

        prompt = TASK_GENERATOR_PROMPT.format(
            query=query,
            query_type=qtype,
            roles="\n".join(f"- {r}" for r in roles),
        )
        response = llm.invoke(prompt)
        parsed = _safe_json_load(getattr(response, "content", "") or "")

        raw = parsed.get("subtasks", []) if isinstance(parsed, dict) else []
        subtasks: list[dict[str, Any]] = []
        for i, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            if role not in roles:
                role = roles[0]
            subtasks.append(
                {
                    "id": item.get("id", f"s{i}"),
                    "role": role,
                    "task": item.get("task", state["query"]),
                    "status": "pending",
                }
            )

        # Fallback: ensure at least one task per available role.
        if not subtasks:
            subtasks = [
                {"id": f"s{i}", "role": role, "task": state["query"], "status": "pending"}
                for i, role in enumerate(roles, start=1)
            ]

        # Build worker payloads for fan-out.
        payloads = [
            {
                "task_id": state.get("task_id", ""),
                "query": state["query"],
                "subtask_id": st["id"],
                "role": st["role"],
                "task": st["task"],
            }
            for st in subtasks
        ]

        _persist(db, state.get("task_id", ""), "task_generation",
                 {"subtasks": subtasks})

        return {"subtasks": subtasks, "worker_payloads": payloads}

    return node_task_generator


def create_assign_workers():
    """Conditional fan-out: dispatch each payload to the matching role node."""

    role_to_node = {
        "data_collection": "data_collection_agent",
        "statistics": "statistics_agent",
        "citation": "citation_agent",
        "web_research": "web_research_agent",
        "latest_news_collection": "latest_news_collection_agent",
    }

    def assign(state: WorkflowState):
        sends = []
        for payload in state.get("worker_payloads", []):
            target = role_to_node.get(payload.get("role"))
            if target:
                sends.append(Send(target, payload))
        return sends

    return assign


def create_role_nodes(llm):
    """Return one node-callable per specialized sub-agent role.

    Sub-agents are built **once** here (at graph-build time) via
    :func:`sub_agents.build_role_runners`. The returned runners are
    lightweight callables that simply invoke the pre-built agents.
    """
    return build_role_runners(llm)


def create_node_aggregator(llm, db):
    """Consolidate sub-agent outputs into a structured aggregated object."""

    def node_aggregator(state: WorkflowState):
        outputs = state.get("worker_outputs", [])
        rendered = "\n\n".join(
            f"### {o.get('role', '?')} :: {o.get('subtask_id', '?')}\n"
            f"Task: {o.get('task', '')}\n\n{o.get('output', '')}"
            for o in outputs
        ) or "(no outputs)"

        prompt = AGGREGATOR_PROMPT.format(
            query=state.get("query", ""),
            query_type=state.get("query_type", ""),
            outputs=rendered,
        )
        response = llm.invoke(prompt)
        parsed = _safe_json_load(getattr(response, "content", "") or "")

        # Sanity defaults.
        if not isinstance(parsed, dict) or "sections" not in parsed:
            parsed = {
                "metadata": {
                    "query": state.get("query", ""),
                    "query_type": state.get("query_type", ""),
                    "num_sources": 0,
                },
                "sections": [{"title": "Findings", "content": rendered}],
                "references": [],
            }

        _persist(db, state.get("task_id", ""), "aggregation", parsed)
        return {"aggregated": parsed}

    return node_aggregator


def create_node_writer(llm, db):
    """Produce the final markdown report from the aggregated structure."""

    def node_writer(state: WorkflowState):
        aggregated = state.get("aggregated", {})
        invalid_refs = state.get("invalid_references", [])
        rewrite_note = ""
        if invalid_refs:
            rewrite_note = REWRITE_NOTE_TEMPLATE.format(
                invalid_refs="\n".join(f"- {u}" for u in invalid_refs)
            )

        prompt = WRITER_PROMPT.format(
            aggregated=json.dumps(aggregated, indent=2, default=str),
            rewrite_note=rewrite_note,
        )
        response = llm.invoke(
            [SystemMessage(content="You write professional markdown reports."),
             HumanMessage(content=prompt)]
        )
        draft = response.content if isinstance(response.content, str) else str(response.content)
        draft = _sanitize_report(draft)

        _persist(db, state.get("task_id", ""), "draft", draft)
        # Reset invalid refs after applying them in a rewrite pass.
        return {"draft_report": draft, "invalid_references": []}

    return node_writer


def _build_reference_snippets(
    aggregated: dict[str, Any],
    draft: str,
    radius: int = 220,
) -> list[dict[str, Any]]:
    """For each reference build {id, url, title, snippet} for relevance scoring.

    The snippet is the surrounding text of the first occurrence of the inline
    [n] citation in the report; falls back to the section content or the
    reference title if no inline marker is found.
    """
    refs = aggregated.get("references", []) or []
    sections = aggregated.get("sections", []) or []
    full_text = draft or "\n\n".join(
        s.get("content", "") for s in sections if isinstance(s, dict)
    )

    out: list[dict[str, Any]] = []
    for r in refs:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        url = r.get("url", "")
        title = r.get("title", "")
        snippet = ""
        if rid is not None and full_text:
            marker = f"[{rid}]"
            idx = full_text.find(marker)
            if idx != -1:
                start = max(0, idx - radius)
                end = min(len(full_text), idx + len(marker) + radius)
                snippet = full_text[start:end].strip()
        if not snippet:
            # Fallback: any section that mentions the URL or title.
            for s in sections:
                content = s.get("content", "") if isinstance(s, dict) else ""
                if (url and url in content) or (title and title in content):
                    snippet = content[:radius * 2]
                    break
        if not snippet:
            snippet = title or url
        out.append(
            {
                "id": rid,
                "url": url,
                "title": title,
                "snippet": snippet,
            }
        )
    return out


def create_node_validator(llm, db):
    """Validate references on TWO axes:

    1. URL reachability — HEAD/GET against each URL (broken links rejected).
    2. LLM relevance — does the URL+snippet support the query intention/subtasks?
    Any reference failing either check goes into ``invalid_references`` and
    triggers a writer rewrite (capped by ``MAX_REWRITES``).
    """

    def node_validator(state: WorkflowState):
        draft = state.get("draft_report", "")
        aggregated = state.get("aggregated", {}) or {}
        query = state.get("query", "")
        query_type = state.get("query_type", "")
        subtasks = state.get("subtasks", []) or []

        # Performance optimization: Skip validation for simple queries (saves 5-10s)
        # Production-safe: Only skip if query is genuinely simple AND short
        if query_type in ["summary", "blog"] and len(query.split()) < 6 and len(draft) < 2000:
            _persist(db, state.get("task_id", ""), "validator",
                     {"status": "SKIPPED", "reason": "simple query optimization"})
            return {
                "validation_feedback": "VALID",
                "invalid_references": [],
            }

        references = _build_reference_snippets(aggregated, draft)

        # If the aggregator produced no structured refs, fall back to URLs in the draft.
        if not references:
            for i, url in enumerate(extract_urls(draft), start=1):
                references.append(
                    {"id": i, "url": url, "title": "", "snippet": draft[:400]}
                )

        iterations = state.get("rewrite_iterations", 0)
        task_id = state.get("task_id", "")

        if not references:
            _persist(db, task_id, "validation", {"status": "VALID", "checked": 0})
            return {
                "final_report": draft,
                "validation_feedback": "VALID (no references)",
                "invalid_references": [],
            }

        # ---- 1. URL reachability ------------------------------------------------
        all_urls = [r["url"] for r in references if r.get("url")]
        reach = validate_urls(all_urls) if all_urls else {}
        broken = [u for u, ok in reach.items() if not ok]

        # Only ask the LLM to evaluate references whose URL is reachable; broken
        # ones are already invalid.
        live_refs = [r for r in references if reach.get(r.get("url", ""), False)]

        # ---- 2. LLM relevance ---------------------------------------------------
        irrelevant: list[str] = []
        verdict_log: list[dict[str, Any]] = []
        llm_error: str | None = None

        if live_refs:
            subtasks_rendered = "\n".join(
                f"- [{st.get('role', '?')}] {st.get('task', '')}" for st in subtasks
            ) or "(none)"
            refs_rendered = json.dumps(live_refs, indent=2, default=str)[:8000]
            prompt = VALIDATOR_PROMPT.format(
                query=query,
                query_type=query_type,
                subtasks=subtasks_rendered,
                references=refs_rendered,
            )
            try:
                response = llm.invoke(prompt)
                parsed = _safe_json_load(getattr(response, "content", "") or "")
                verdicts = parsed.get("verdicts", []) if isinstance(parsed, dict) else []
                for v in verdicts:
                    if not isinstance(v, dict):
                        continue
                    verdict_log.append(v)
                    if v.get("relevant") is False and v.get("url"):
                        irrelevant.append(v["url"])
            except Exception as exc:
                llm_error = str(exc)

        # Combined invalid set (broken + irrelevant), de-duplicated, order-preserving.
        seen: set[str] = set()
        invalid: list[str] = []
        for u in broken + irrelevant:
            if u and u not in seen:
                seen.add(u)
                invalid.append(u)

        # ---- Decision -----------------------------------------------------------
        if not invalid:
            _persist(db, task_id, "validation", {
                "status": "VALID",
                "checked": len(references),
                "verdicts": verdict_log,
                "llm_error": llm_error,
            })
            return {
                "final_report": draft,
                "validation_feedback": "VALID" + (
                    f" (validator LLM error: {llm_error})" if llm_error else ""
                ),
                "invalid_references": [],
            }

        if iterations >= MAX_REWRITES:
            cleaned = draft
            for u in invalid:
                cleaned = cleaned.replace(u, "[invalid link removed]")
            _persist(db, task_id, "validation", {
                "status": "FORCED_FINISH",
                "broken": broken,
                "irrelevant": irrelevant,
                "verdicts": verdict_log,
            })
            return {
                "final_report": cleaned,
                "validation_feedback": f"FORCED_FINISH after {iterations} rewrites",
                "invalid_references": [],
            }

        _persist(db, task_id, "validation", {
            "status": "INVALID_REFS",
            "broken": broken,
            "irrelevant": irrelevant,
            "verdicts": verdict_log,
        })
        return {
            "validation_feedback": (
                f"INVALID_REFS: {len(broken)} broken, {len(irrelevant)} irrelevant"
            ),
            "invalid_references": invalid,
            "rewrite_iterations": iterations + 1,
        }

    return node_validator


def create_validation_route():
    def route(state: WorkflowState):
        return "valid" if state.get("validation_feedback") == "VALID" or state.get("final_report") else "rewrite"
    return route


def create_node_report_finalizer(llm, db):
    """Enrich the validated report with auto-generated charts, graphs and images.

    This node:
    1. Sends the final report + aggregated data to the LLM to identify
       data points suitable for visualisation.
    2. Renders charts via matplotlib into base64 PNG images.
    3. Embeds them as inline ``![caption](data:image/png;…)`` in the report.
    """

    def node_report_finalizer(state: WorkflowState):
        report = state.get("final_report") or state.get("draft_report") or ""
        aggregated = state.get("aggregated", {})
        query_type = state.get("query_type", "summary")

        if not report:
            return {}

        # Performance optimization: Skip chart generation for very short/simple reports (saves 2-5s)
        # Production-safe: Only skip if report is genuinely too short and no statistics
        if query_type == "summary" and len(report) < 800 and "statistics" not in report.lower():
            _persist(db, state.get("task_id", ""), "report_finalizer",
                     {"status": "SKIPPED", "reason": "report too short for charts"})
            return {}

        # Ask the LLM to produce chart specifications and an enhanced report
        # with {{CHART:<index>}} placement markers.
        prompt = REPORT_FINALIZER_PROMPT.format(
            report=report,
            aggregated=json.dumps(aggregated, indent=2, default=str)[:12000],
        )
        try:
            response = llm.invoke(
                [SystemMessage(content="You are a data-visualisation specialist. Return STRICT JSON only."),
                 HumanMessage(content=prompt)]
            )
            parsed = _safe_json_load(getattr(response, "content", "") or "")
        except Exception:
            # If the LLM call fails, pass through the report unchanged.
            _persist(db, state.get("task_id", ""), "report_finalizer",
                     {"status": "LLM_ERROR"})
            return {}

        chart_specs = parsed.get("chart_specs", []) if isinstance(parsed, dict) else []
        enhanced_report = parsed.get("enhanced_report", report) if isinstance(parsed, dict) else report

        # Render chart images
        rendered_images: list[dict[str, str]] = []
        if chart_specs:
            rendered_images = generate_charts_for_report(chart_specs)

        # Replace {{CHART:<index>}} markers with embedded images
        final_visual_report = enhanced_report
        for i, img in enumerate(rendered_images):
            marker = f"{{{{CHART:{i}}}}}"
            md_image = f"\n\n![{img['caption']}]({img['data_uri']})\n\n"
            final_visual_report = final_visual_report.replace(marker, md_image)

        # Clean up any unreplaced markers (if chart rendering failed for some)
        final_visual_report = re.sub(r"\{\{CHART:\d+\}\}", "", final_visual_report)
        # Collapse excessive blank lines
        final_visual_report = re.sub(r"\n{3,}", "\n\n", final_visual_report).strip()

        _persist(db, state.get("task_id", ""), "report_finalizer", {
            "charts_requested": len(chart_specs),
            "charts_rendered": len(rendered_images),
        })

        return {
            "final_report": final_visual_report,
            "chart_specs": chart_specs,
            "report_images": rendered_images,
        }

    return node_report_finalizer


def create_node_cleanup(db):
    """Persist the final report against the original query, then drop intermediates."""

    def node_cleanup(state: WorkflowState):
        final_report = state.get("final_report") or state.get("draft_report") or ""
        query = state.get("query", "")
        task_id = state.get("task_id", "")

        # Persist the finished report keyed by the original query (best-effort).
        if db is not None and query and final_report:
            try:
                db.save_report(query, final_report)
            except Exception:
                pass

        # Drop intermediate per-task artifacts.
        if db is not None and task_id:
            try:
                db.cleanup_task_data(task_id)
            except Exception:
                pass

        if not state.get("final_report"):
            return {"final_report": final_report or "No Report Generated"}
        return {}

    return node_cleanup