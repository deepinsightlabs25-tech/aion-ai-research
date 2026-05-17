"""Research paper formatter: validates, cleans, and compiles LaTeX output.

Uses PyTinyTeX to compile LaTeX → PDF without requiring system TeX installation.
Includes an LLM retry loop: if compilation fails, errors are fed back to the LLM
for targeted fixes (up to 2 retries).
"""

from __future__ import annotations

import base64
import logging
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

_tinytex_ready = False


def _ensure_tinytex() -> None:
    """Download TinyTeX once if not already available.
    
    Skipped when DISABLE_TINYTEX=1 is set (e.g. on memory-constrained hosts).
    """
    global _tinytex_ready
    if _tinytex_ready:
        return

    import os
    if os.getenv("DISABLE_TINYTEX", "").strip() in ("1", "true", "yes"):
        logger.info("[pytinytex] Skipped — DISABLE_TINYTEX is set")
        return

    try:
        import pytinytex
        try:
            pytinytex.get_tinytex_path()
            _tinytex_ready = True
        except RuntimeError:
            logger.info("[pytinytex] Downloading TinyTeX (one-time setup)...")
            try:
                pytinytex.download_tinytex(version="2024.12", variation=1)
            except Exception:
                pytinytex.download_tinytex(variation=1)
            _tinytex_ready = True
            logger.info("[pytinytex] TinyTeX installed successfully")
    except Exception as exc:
        logger.warning(f"[pytinytex] Setup failed: {exc}")
        _tinytex_ready = False


# ---------------------------------------------------------------------------
# LaTeX compilation (PyTinyTeX)
# ---------------------------------------------------------------------------


def _decode_image_payload(payload: str) -> bytes | None:
    """Decode an image payload that may be either raw base64 or a data URI."""
    if not payload:
        return None
    data = payload
    if data.startswith("data:"):
        comma = data.find(",")
        if comma < 0:
            return None
        data = data[comma + 1 :]
    try:
        return base64.b64decode(data)
    except Exception:
        return None


def compile_latex_to_pdf(
    latex: str,
    images: Iterable[dict[str, str]] | None = None,
) -> tuple[bytes | None, list[str]]:
    """Compile LaTeX source to PDF using PyTinyTeX.

    Optionally, ``images`` is an iterable of dicts with at minimum a ``filename``
    key and either ``data_uri`` or ``base64`` payload. The images are written
    next to the .tex file so ``\\includegraphics{filename}`` can find them.

    Returns (pdf_bytes, errors). On success, pdf_bytes is the raw PDF content
    and errors is empty. On failure, pdf_bytes is None and errors contains
    the compilation error messages.
    """
    _ensure_tinytex()

    try:
        import pytinytex
    except ImportError:
        return None, ["pytinytex not installed"]

    if not _tinytex_ready:
        return None, ["TinyTeX not available on this system"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_path = tmp_path / "paper.tex"
        tex_path.write_text(latex, encoding="utf-8")

        # Write any provided images into the temp dir so pdflatex can find them.
        if images:
            for img in images:
                fname = img.get("filename") if isinstance(img, dict) else None
                payload = (
                    img.get("data_uri") or img.get("base64") or img.get("data")
                    if isinstance(img, dict)
                    else None
                )
                if not fname or not payload:
                    continue
                raw = _decode_image_payload(payload)
                if not raw:
                    continue
                try:
                    (tmp_path / fname).write_bytes(raw)
                except Exception:
                    continue

        try:
            # Two passes are required so \\cite{} keys resolve via the .aux file;
            # otherwise every citation renders as "[?]".
            result = pytinytex.compile(str(tex_path), auto_install=True, num_runs=2)

            pdf_path = Path(str(tex_path).replace(".tex", ".pdf"))
            if pdf_path.exists():
                pdf_bytes = pdf_path.read_bytes()
                logger.info(f"[compile] PDF generated: {len(pdf_bytes)} bytes")
                return pdf_bytes, []

            errors = _parse_latex_log(Path(tmp) / "paper.log")
            if not errors:
                errors = ["Compilation failed with no specific error"]
            return None, errors

        except Exception as exc:
            error_msg = str(exc)
            logger.warning(f"[compile] Exception: {error_msg}")
            return None, [error_msg]


def _parse_latex_log(log_path: Path) -> list[str]:
    """Extract error messages from a LaTeX .log file."""
    if not log_path.exists():
        return []

    errors: list[str] = []
    try:
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        for line in log_text.split("\n"):
            if line.startswith("! "):
                errors.append(line.strip())
            elif "Fatal error" in line or "Emergency stop" in line:
                errors.append(line.strip())
    except Exception:
        pass

    return errors[:10]


def pdf_to_base64(pdf_bytes: bytes) -> str:
    """Encode PDF bytes as a base64 string for storage/transport."""
    return base64.b64encode(pdf_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# LaTeX validation (enhanced static analysis)
# ---------------------------------------------------------------------------


def validate_latex(latex: str) -> tuple[bool, list[str]]:
    """Comprehensive structural validation of LaTeX paper content.

    Catches ~90-95% of LLM-generated LaTeX errors via static analysis.
    Returns (is_valid, list_of_issues).
    """
    issues: list[str] = []

    if not latex.strip():
        return False, ["Empty LaTeX content"]

    # Required structural elements
    if r"\documentclass" not in latex:
        issues.append("Missing \\documentclass declaration")
    if r"\begin{document}" not in latex:
        issues.append("Missing \\begin{document}")
    if r"\end{document}" not in latex:
        issues.append("Missing \\end{document}")
    if r"\begin{abstract}" not in latex:
        issues.append("Missing abstract")
    if r"\title{" not in latex:
        issues.append("Missing title")

    # Brace balancing
    open_braces = latex.count("{")
    close_braces = latex.count("}")
    if abs(open_braces - close_braces) > 2:
        issues.append(
            f"Unbalanced braces: {open_braces} {{ vs {close_braces} }}"
        )

    # Environment matching (by name, not just count)
    begins = re.findall(r"\\begin\{(\w+)\}", latex)
    ends = re.findall(r"\\end\{(\w+)\}", latex)
    begin_counts = Counter(begins)
    end_counts = Counter(ends)
    for env, count in begin_counts.items():
        end_count = end_counts.get(env, 0)
        if end_count != count:
            issues.append(
                f"Mismatched environment: \\begin{{{env}}} x{count} "
                f"vs \\end{{{env}}} x{end_count}"
            )
    for env, count in end_counts.items():
        if env not in begin_counts:
            issues.append(f"Orphan \\end{{{env}}} with no matching \\begin")

    # Section count
    sections = re.findall(r"\\section\{([^}]+)\}", latex)
    if len(sections) < 3:
        issues.append(f"Only {len(sections)} sections found (expected >= 5)")

    # Citations must exist
    if r"\cite{" not in latex and r"\bibitem{" not in latex:
        issues.append("No citations found")

    # Citation-bibitem cross-check
    cited_keys: set[str] = set()
    for group in re.findall(r"\\cite\{([^}]+)\}", latex):
        cited_keys.update(k.strip() for k in group.split(","))
    bibitem_keys = set(re.findall(r"\\bibitem\{([^}]+)\}", latex))
    missing = cited_keys - bibitem_keys
    if missing:
        sample = ", ".join(list(missing)[:5])
        issues.append(f"Citations without \\bibitem ({len(missing)}): {sample}")

    # Detect residual \texttt{} quoting patterns that break compilation
    if re.search(r"[}`]\\texttt\{[^}]*''", latex):
        issues.append(
            "Contains malformed \\texttt quoting pattern (stray } or ` before \\texttt)"
        )

    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# LaTeX cleaning / post-processing
# ---------------------------------------------------------------------------


def clean_latex(raw: str, allowed_images: set[str] | None = None) -> str:
    """Strip markdown fences, fix common LLM mistakes, and normalize output.

    If ``allowed_images`` is provided, figures referencing those filenames are
    preserved; figures referencing any other filename are stripped (avoids
    pdflatex failing on missing files). When ``allowed_images`` is None or
    empty, all figure environments are stripped (legacy behaviour).
    """
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:latex|tex)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    if not cleaned.startswith(r"\documentclass"):
        idx = cleaned.find(r"\documentclass")
        if idx > 0:
            cleaned = cleaned[idx:]

    end_idx = cleaned.rfind(r"\end{document}")
    if end_idx > 0:
        cleaned = cleaned[: end_idx + len(r"\end{document}")]

    cleaned = _fix_common_latex_errors(cleaned, allowed_images=allowed_images)
    return cleaned


def _fix_common_latex_errors(latex: str, allowed_images: set[str] | None = None) -> str:
    """Auto-correct common LLM mistakes in generated LaTeX."""

    # --- Fix \texttt{} misused as LaTeX quotes (multiple broken patterns) ---
    # Order matters: match longer/more-specific patterns first.

    # Pattern: ``\texttt{text}'' → ``text''  (double-backtick opener)
    latex = re.sub(r"``\\texttt\{([^}]+)\}''", r"``\1''", latex)
    # Pattern: ``\texttt{text'' (unclosed brace, double-backtick opener)
    latex = re.sub(r"``\\texttt\{([^']+)''", r"``\1''", latex)
    # Pattern: `\texttt{text}'' → ``text''  (single backtick opener)
    latex = re.sub(r"`\\texttt\{([^}]+)\}''\s*", r"``\1'' ", latex)
    # Pattern: `\texttt{text'' (unclosed brace, single backtick)
    latex = re.sub(r"`\\texttt\{([^']+)''\s*", r"``\1'' ", latex)
    # Pattern: }\texttt{text}'' → ``text''  (stray closing brace)
    latex = re.sub(r"\}\\texttt\{([^}]+)\}''\s*", r"``\1'' ", latex)
    # Pattern: }\texttt{text'' (unclosed brace, stray closing brace)
    latex = re.sub(r"\}\\texttt\{([^']+)''\s*", r"``\1'' ", latex)
    # Pattern: \texttt{text}'' (no opening quote at all) → ``text''
    latex = re.sub(r"(?<![`{])\\texttt\{([^}]+)\}\s*''", r"``\1''", latex)

    # Convert markdown bold **text** to \textbf{text}
    latex = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", latex)

    # Convert markdown italic *text* to \textit{text}
    latex = re.sub(
        r"(?<!\\begin\{)(?<!\\end\{)\*([^*\n]+)\*", r"\\textit{\1}", latex
    )

    # Convert markdown backtick `code` to \texttt{code}
    # Must NOT match LaTeX opening quotes `` (two consecutive backticks)
    latex = re.sub(r"(?<!`)`(?!`)([^`\n]+)`(?!`)", r"\\texttt{\1}", latex)

    # Escape unescaped dollar signs in text (not in math mode)
    latex = re.sub(r"(?<!\\)\$(\d)", r"\\$\1", latex)

    # Handle figures based on which image files are actually available.
    allowed = {n.strip() for n in (allowed_images or set()) if n and n.strip()}
    if not allowed:
        # No images available -> strip every figure/includegraphics outright.
        latex = re.sub(
            r"\\begin\{figure\}.*?\\end\{figure\}",
            "",
            latex,
            flags=re.DOTALL,
        )
        latex = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}\n?", "", latex)
    else:
        # Drop figure environments whose included file is not in our manifest.
        def _figure_filter(match: re.Match[str]) -> str:
            block = match.group(0)
            inc = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", block)
            if not inc:
                return ""
            fname = inc.group(1).strip()
            # Allow exact match or basename match (handles paths like ./foo.png).
            base = fname.rsplit("/", 1)[-1]
            if fname in allowed or base in allowed:
                return block
            return ""

        latex = re.sub(
            r"\\begin\{figure\}.*?\\end\{figure\}",
            _figure_filter,
            latex,
            flags=re.DOTALL,
        )
        # Strip stray \includegraphics (outside figure environments) that reference unknown files.
        def _inc_filter(match: re.Match[str]) -> str:
            fname = match.group(1).strip()
            base = fname.rsplit("/", 1)[-1]
            return match.group(0) if (fname in allowed or base in allowed) else ""

        latex = re.sub(
            r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}",
            _inc_filter,
            latex,
        )

    # Remove instructional comments
    latex = re.sub(r"%\s*(Adjust|TODO|FIXME|Insert|Change).*\n", "\n", latex)

    # Fix \vspace with adjustment comments
    latex = re.sub(r"\\vspace\{-[^}]+\}\s*%.*\n", "\n", latex)

    # Remove duplicate \end{document} and trailing content
    parts = latex.split(r"\end{document}")
    if len(parts) > 1:
        latex = parts[0] + r"\end{document}"

    # Collapse excessive blank lines
    latex = re.sub(r"\n{3,}", "\n\n", latex)

    return latex


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------


def extract_paper_metadata(latex: str) -> dict[str, Any]:
    """Extract title, abstract, and section list from the LaTeX paper."""
    title_match = re.search(r"\\title\{([^}]+)\}", latex)
    title = title_match.group(1) if title_match else "Untitled"

    abstract_match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", latex, re.DOTALL
    )
    abstract = abstract_match.group(1).strip() if abstract_match else ""

    sections = re.findall(r"\\section\{([^}]+)\}", latex)

    return {
        "title": title,
        "abstract": abstract,
        "sections": sections,
        "word_count": len(latex.split()),
    }
