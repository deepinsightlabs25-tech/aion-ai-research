"""Paper Writer node — convert deep_research reports into LaTeX papers and PDF."""

from __future__ import annotations

import json
import time
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import LATEX_FIX_PROMPT, PAPER_METADATA_PROMPT, RESEARCH_PAPER_PROMPT
from ..state import WorkflowState
from ..helpers import safe_json_load, persist
from ..paper_formatter import (
    clean_latex,
    compile_latex_to_pdf,
    extract_paper_metadata,
    pdf_to_base64,
)

logger = logging.getLogger(__name__)


def create_node_paper_writer(llm, db):
    """Convert a deep_research report into a compilable LaTeX paper and PDF.

    This node only activates for deep_research queries. It:
    1. Generates LaTeX from the finalized report via LLM
    2. Cleans common LLM mistakes
    3. Compiles to PDF using PyTinyTeX
    4. If compilation fails, feeds errors back to LLM for fixing (up to 2 retries)
    5. Returns the LaTeX source + PDF (base64) + metadata
    """

    MAX_FIX_RETRIES = 2

    def node_paper_writer(state: WorkflowState):
        t0 = time.time()
        query_type = state.get("query_type", "")

        if query_type != "deep_research":
            logger.info("[paper_writer] skipped (query_type=%s)", query_type)
            return {}

        report = state.get("final_report") or state.get("draft_report") or ""
        aggregated = state.get("aggregated", {})

        if not report:
            logger.warning("[paper_writer] no report content available")
            return {}

        # Build an image manifest from charts rendered by the report_finalizer.
        # Each entry already has a base64 PNG (data_uri); assign deterministic
        # filenames so the LLM can reference them via \includegraphics.
        report_images = state.get("report_images") or []
        paper_images: list[dict[str, str]] = []
        manifest_lines: list[str] = []
        for idx, img in enumerate(report_images):
            if not isinstance(img, dict) or not img.get("data_uri"):
                continue
            fname = f"figure_{idx + 1}.png"
            caption = (img.get("caption") or f"Figure {idx + 1}").strip()
            paper_images.append({"filename": fname, "data_uri": img["data_uri"], "caption": caption})
            manifest_lines.append(f"- {fname}: {caption}")

        if paper_images:
            image_manifest = (
                "AVAILABLE CHART IMAGES (embed each one in a \\begin{figure} "
                "environment using the EXACT filename listed, with a meaningful "
                "\\caption based on the description):\n"
                + "\n".join(manifest_lines)
            )
        else:
            image_manifest = "NO CHART IMAGES AVAILABLE. Use tables to present data instead."

        allowed_filenames = {img["filename"] for img in paper_images}

        # Step 1: Generate initial LaTeX
        prompt = RESEARCH_PAPER_PROMPT.format(
            report=report,
            aggregated=json.dumps(aggregated, indent=2, default=str)[:15000],
            image_manifest=image_manifest,
        )
        try:
            response = llm.invoke(
                [SystemMessage(content="You are an expert academic paper writer. Return complete, compilable LaTeX only."),
                 HumanMessage(content=prompt)]
            )
            raw_latex = response.content if isinstance(response.content, str) else str(response.content)
        except Exception as exc:
            logger.error(f"[paper_writer] LLM call failed: {exc}")
            persist(db, state.get("task_id", ""), "paper_writer", {"status": "LLM_ERROR", "error": str(exc)})
            return {}

        latex = clean_latex(raw_latex, allowed_images=allowed_filenames)

        # Step 2: Compile -> if errors, feed back to LLM for fixing
        pdf_bytes: bytes | None = None
        compile_errors: list[str] = []

        for attempt in range(1 + MAX_FIX_RETRIES):
            pdf_bytes, compile_errors = compile_latex_to_pdf(latex, images=paper_images)

            if pdf_bytes is not None:
                logger.info(f"[paper_writer] PDF compiled on attempt {attempt + 1}")
                break

            if attempt < MAX_FIX_RETRIES and compile_errors:
                logger.info(
                    f"[paper_writer] Attempt {attempt + 1} failed with {len(compile_errors)} errors, "
                    f"asking LLM to fix..."
                )
                fix_prompt = LATEX_FIX_PROMPT.format(
                    errors="\n".join(f"- {e}" for e in compile_errors[:8]),
                    latex=latex,
                )
                try:
                    fix_response = llm.invoke(
                        [SystemMessage(content="You are a LaTeX debugging expert. Return the complete fixed document only."),
                         HumanMessage(content=fix_prompt)]
                    )
                    fixed_raw = fix_response.content if isinstance(fix_response.content, str) else str(fix_response.content)
                    latex = clean_latex(fixed_raw, allowed_images=allowed_filenames)
                except Exception as exc:
                    logger.warning(f"[paper_writer] Fix LLM call failed: {exc}")
                    break

        # Step 3: Extract metadata
        is_valid = pdf_bytes is not None
        paper_meta = extract_paper_metadata(latex)

        venue_meta: dict[str, Any] = {}
        if paper_meta.get("title") and paper_meta.get("abstract"):
            try:
                meta_prompt = PAPER_METADATA_PROMPT.format(
                    title=paper_meta["title"],
                    abstract=paper_meta["abstract"][:500],
                )
                meta_response = llm.invoke(meta_prompt)
                venue_meta = safe_json_load(getattr(meta_response, "content", "") or "")
            except Exception:
                pass

        full_metadata = {
            **paper_meta,
            **venue_meta,
            "pdf_compiled": is_valid,
            "compile_errors": compile_errors if not is_valid else [],
        }

        # Encode PDF as base64 for transport
        pdf_base64 = pdf_to_base64(pdf_bytes) if pdf_bytes else None

        persist(db, state.get("task_id", ""), "paper_writer", {
            "status": "SUCCESS" if is_valid else "COMPILE_FAILED",
            "pdf_compiled": is_valid,
            "word_count": paper_meta.get("word_count", 0),
            "sections": paper_meta.get("sections", []),
            "compile_attempts": min(len(compile_errors) > 0 and MAX_FIX_RETRIES or 0, MAX_FIX_RETRIES) + 1,
        })

        logger.info(
            f"[paper_writer] {paper_meta.get('word_count', 0)} words, "
            f"pdf={'YES' if is_valid else 'NO'}, "
            f"errors={len(compile_errors)} | {time.time() - t0:.1f}s"
        )

        return {
            "research_paper_latex": latex,
            "research_paper_metadata": full_metadata,
            "research_paper_pdf_base64": pdf_base64,
        }

    return node_paper_writer
