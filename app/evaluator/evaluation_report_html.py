"""
Build a print-friendly HTML evaluation report for download from the Streamlit UI.
"""

from __future__ import annotations

import csv
import html
import io
from datetime import datetime, timezone
from typing import Any, Mapping


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _fmt_pct(value: Any, decimals: int = 2) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return _esc(value)


def _rows_table(headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = ""
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        body += f"<tr>{cells}</tr>"
    return f'<table class="data"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def build_field_scores_csv(result: Mapping[str, Any]) -> str:
    """CSV aligned columns: field, mean score %, strict pass rate %."""
    field_accuracy = result.get("field_accuracy") or {}
    field_pass_rate = result.get("field_pass_rate") or {}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Field", "Mean score %", "Strict pass rate % (score >= 80)"])
    for field, acc in sorted(field_accuracy.items(), key=lambda x: (-x[1], x[0])):
        pr = field_pass_rate.get(field)
        w.writerow(
            [
                field,
                round(float(acc), 4) if acc is not None else "",
                round(float(pr), 4) if pr is not None else "",
            ]
        )
    return buf.getvalue()


def build_evaluation_report_html(
    result: Mapping[str, Any],
    *,
    schema_name: str,
    default_result: Mapping[str, Any] | None = None,
    strict_result: Mapping[str, Any] | None = None,
    lenient_result: Mapping[str, Any] | None = None,
    thresholds_used: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Return a full HTML document suitable for browser view and print-to-PDF."""
    when = generated_at or datetime.now(timezone.utc)
    when_local = when.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    stats = result.get("stats") or {}

    summary_rows = [
        ["Schema", _esc(schema_name)],
        ["Report generated", _esc(when_local)],
        ["Overall score (weighted mean)", f"{_fmt_pct(result.get('overall_accuracy'))}%"],
        ["Strict pass rate (score ≥ 80)", f"{_fmt_pct(result.get('strict_pass_rate'))}%"],
    ]

    invoice_rows = [
        ["Extracted invoices", _esc(stats.get("total_invoices_extracted", 0))],
        ["Ground truth records", _esc(stats.get("total_ground_truth_records", 0))],
        ["Matched invoices", _esc(stats.get("total_invoices_matched", 0))],
        ["Unmatched invoices", _esc(stats.get("unmatched_extracted_count", 0))],
        ["Total field comparisons", _esc(stats.get("total_fields", 0))],
        ["Comparisons passed at ≥80", _esc(stats.get("matched_fields_strict_ge_80", 0))],
        ["Mean field score", f"{_fmt_pct(stats.get('mean_field_score'))}%"],
    ]

    scenario_rows: list[list[str]] = []
    if default_result is not None:
        scenario_rows.append(
            [
                "Default thresholds",
                f"{_fmt_pct(default_result.get('overall_accuracy'))}%",
                f"{_fmt_pct((result.get('overall_accuracy') or 0) - (default_result.get('overall_accuracy') or 0), 2)}",
            ]
        )
    scenario_rows.append(
        [
            "Your thresholds (this run)",
            f"{_fmt_pct(result.get('overall_accuracy'))}%",
            "—",
        ]
    )
    if strict_result is not None:
        scenario_rows.append(
            [
                "Strict (+10 to each threshold)",
                f"{_fmt_pct(strict_result.get('overall_accuracy'))}%",
                f"{_fmt_pct((strict_result.get('overall_accuracy') or 0) - (result.get('overall_accuracy') or 0), 2)}",
            ]
        )
    if lenient_result is not None:
        scenario_rows.append(
            [
                "Lenient (−10 to each threshold, floor 50)",
                f"{_fmt_pct(lenient_result.get('overall_accuracy'))}%",
                f"{_fmt_pct((lenient_result.get('overall_accuracy') or 0) - (result.get('overall_accuracy') or 0), 2)}",
            ]
        )

    section_accuracy = result.get("section_accuracy") or {}
    section_rows = [
        [_esc(s.replace("_", " ").title()), f"{_fmt_pct(v)}%"]
        for s, v in sorted(section_accuracy.items(), key=lambda x: x[0])
    ]

    field_accuracy = result.get("field_accuracy") or {}
    field_pass_rate = result.get("field_pass_rate") or {}
    field_rows: list[list[str]] = []
    for field, acc in sorted(field_accuracy.items(), key=lambda x: (-x[1], x[0])):
        pr = field_pass_rate.get(field)
        pr_s = f"{_fmt_pct(pr)}%" if pr is not None else "—"
        field_rows.append([_esc(field), f"{_fmt_pct(acc)}%", pr_s])

    invoice_acc = result.get("invoice_accuracy") or {}
    inv_detail_rows: list[list[str]] = []
    max_invoices = 200
    for i, (inv_id, acc) in enumerate(
        sorted(invoice_acc.items(), key=lambda x: (-x[1], str(x[0])))
    ):
        if i >= max_invoices:
            break
        inv_detail_rows.append([_esc(inv_id), f"{_fmt_pct(acc)}%"])
    invoice_note = ""
    if len(invoice_acc) > max_invoices:
        invoice_note = (
            f"<p class=\"note\">Showing first {max_invoices} of {len(invoice_acc)} "
            "invoices by score. Full per-invoice scores are in the raw JSON export.</p>"
        )

    unmatched = result.get("unmatched_extracted_ids") or []
    unmatched_html = ""
    if unmatched:
        items = "".join(f"<li>{_esc(u)}</li>" for u in unmatched[:500])
        more = ""
        if len(unmatched) > 500:
            more = f"<p class=\"note\">List truncated; {len(unmatched)} total unmatched.</p>"
        unmatched_html = (
            f"<h2>Unmatched extracted invoices</h2><ul class=\"ids\">{items}</ul>{more}"
        )

    thresholds_block = ""
    if thresholds_used:
        lines = []
        for k in sorted(thresholds_used.keys(), key=lambda x: str(x).lower()):
            lines.append(f"{_esc(k)}: {_esc(thresholds_used[k])}")
        inner = "<br>\n".join(lines)
        thresholds_block = (
            f"<details class=\"appendix\"><summary>Threshold values used (this run)</summary>"
            f"<div class=\"prewrap\">{inner}</div></details>"
        )

    css = """
    :root { --border: #d4d4d8; --head: #f4f4f5; --text: #18181b; --muted: #71717a; }
    * { box-sizing: border-box; }
    body { font-family: "Segoe UI", system-ui, -apple-system, sans-serif; color: var(--text);
           line-height: 1.45; margin: 0; padding: 2rem 1.5rem 3rem; background: #fafafa; }
    .sheet { max-width: 920px; margin: 0 auto; background: #fff; padding: 2rem 2.25rem;
             box-shadow: 0 1px 3px rgba(0,0,0,.08); border: 1px solid var(--border); }
    h1 { font-size: 1.5rem; font-weight: 600; margin: 0 0 0.25rem; letter-spacing: -0.02em; }
    .subtitle { color: var(--muted); font-size: 0.95rem; margin: 0 0 1.75rem; }
    h2 { font-size: 1.05rem; font-weight: 600; margin: 1.75rem 0 0.65rem;
         padding-bottom: 0.35rem; border-bottom: 1px solid var(--border); }
    table.data { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin: 0.5rem 0 1rem; }
    table.data th, table.data td { border: 1px solid var(--border); padding: 0.5rem 0.65rem;
                                   text-align: left; vertical-align: top; }
    table.data thead th { background: var(--head); font-weight: 600; white-space: nowrap; }
    table.data td:nth-child(n+2), table.data th:nth-child(n+2) { text-align: right; }
    table.data td:first-child, table.data th:first-child { text-align: left; }
    .note { font-size: 0.85rem; color: var(--muted); margin: 0.25rem 0 1rem; }
    ul.ids { margin: 0.25rem 0 1rem; padding-left: 1.25rem; font-size: 0.88rem; }
    details.appendix { margin-top: 2rem; font-size: 0.88rem; }
    details.appendix summary { cursor: pointer; color: var(--muted); font-weight: 500; }
    .prewrap { margin-top: 0.75rem; white-space: pre-wrap; word-break: break-word;
               font-family: ui-monospace, Consolas, monospace; font-size: 0.82rem;
               background: var(--head); padding: 1rem; border: 1px solid var(--border); }
    @media print {
      body { background: #fff; padding: 0; }
      .sheet { box-shadow: none; border: none; max-width: none; padding: 0; }
    }
    """

    scenario_headers = ["Scenario", "Overall score", "Δ vs your run"]
    section_headers = ["Section", "Accuracy"]
    field_headers = ["Field", "Mean score", "Strict pass rate (≥80)"]
    inv_headers = ["Invoice ID", "Mean score"]

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Invoice evaluation report</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>",
        '<div class="sheet">',
        "<h1>Invoice extraction evaluation report</h1>",
        f'<p class="subtitle">Structured comparison against ground truth · {_esc(schema_name)} schema</p>',
        "<h2>Summary</h2>",
        _rows_table(["Metric", "Value"], summary_rows),
        "<h2>Dataset matching</h2>",
        _rows_table(["Metric", "Value"], invoice_rows),
        "<h2>Threshold scenarios (overall accuracy)</h2>",
        _rows_table(scenario_headers, scenario_rows),
        "<p class=\"note\">Δ vs your run shows percentage points difference from the evaluation that used your threshold sliders.</p>",
        "<h2>Section accuracy</h2>",
        (
            _rows_table(section_headers, section_rows)
            if section_rows
            else "<p class=\"note\">No section accuracy computed.</p>"
        ),
        "<h2>Field scores</h2>",
        (
            _rows_table(field_headers, field_rows)
            if field_rows
            else "<p class=\"note\">No field scores available.</p>"
        ),
        "<h2>Per-invoice mean scores</h2>",
        invoice_note,
        (
            _rows_table(inv_headers, inv_detail_rows)
            if inv_detail_rows
            else "<p class=\"note\">No per-invoice scores.</p>"
        ),
        unmatched_html,
        thresholds_block,
        '<p class="note" style="margin-top:2rem;">Generated by the Invoice Evaluation System. '
        "Open this file in a browser; use Print → Save as PDF for a PDF copy.</p>",
        "</div>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)
