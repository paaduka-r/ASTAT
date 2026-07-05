"""
Generates a self-contained HTML report from graded ASTAT results.
Opens in any browser — no dependencies, no server needed.
"""

from pathlib import Path
from typing import Any

OUTPUT_PATH = Path(__file__).parent.parent / "output" / "results.html"

GRADE_COLORS = {
    "Pass":                  ("#1a7a1a", "#d4edda"),   # dark green text, light green bg
    "False Positive":        ("#7a6a00", "#fff3cd"),   # amber
    "Silent Failure":        ("#7a3a00", "#ffe0b2"),   # orange
    "Verifiable Hallucination": ("#7a0000", "#ffd7d7"), # red
    "Refusal":               ("#444444", "#e8e8e8"),   # grey
    "Ungraded":              ("#888888", "#f5f5f5"),   # light grey
    "Error":                 ("#0000aa", "#e8e8ff"),   # blue — API error, not a grading result
}

CLASSIFICATIONS = [
    "Pass", "False Positive", "Silent Failure",
    "Verifiable Hallucination", "Refusal", "Ungraded",
]


def _badge(cls: str) -> str:
    fg, bg = GRADE_COLORS.get(cls, ("#333", "#eee"))
    return (
        f'<span style="background:{bg};color:{fg};padding:3px 8px;'
        f'border-radius:12px;font-size:12px;font-weight:600;'
        f'white-space:nowrap">{cls}</span>'
    )


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "—"
    p = round(100 * n / total)
    _, bg = GRADE_COLORS.get("Pass", ("#000", "#d4edda"))
    intensity = int(p * 1.8)
    color = f"rgb({255 - intensity}, {180 + intensity // 3}, {255 - intensity})" if p < 60 else "#d4edda"
    return f'<span style="background:{color};padding:2px 6px;border-radius:4px">{n}/{total} ({p}%)</span>'


def _pass_stats(rows: list[dict], subject: str | None = None) -> tuple[int, int]:
    filtered = [r for r in rows if subject is None or r["subject"] == subject]
    passed = sum(1 for r in filtered if r.get("classification") == "Pass")
    return passed, len(filtered)


def _cell(text: str, max_len: int = 120) -> str:
    text = str(text or "").strip()
    if len(text) <= max_len:
        return f'<span>{_esc(text)}</span>'
    short = _esc(text[:max_len])
    full = _esc(text)
    uid = abs(hash(text)) % 999999
    return (
        f'<span class="short-{uid}">{short}… '
        f'<a href="#" onclick="document.querySelector(\'.short-{uid}\').style.display=\'none\';'
        f'document.querySelector(\'.full-{uid}\').style.display=\'inline\';return false;" '
        f'style="font-size:11px;color:#0066cc">[more]</a></span>'
        f'<span class="full-{uid}" style="display:none">{full} '
        f'<a href="#" onclick="document.querySelector(\'.full-{uid}\').style.display=\'none\';'
        f'document.querySelector(\'.short-{uid}\').style.display=\'inline\';return false;" '
        f'style="font-size:11px;color:#0066cc">[less]</a></span>'
    )


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;")
                .replace("\n", "<br>"))


def generate_html_report(results: dict[str, list[dict]], path: Path = OUTPUT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    model_names = list(results.keys())
    all_subjects = sorted({r["subject"] for rows in results.values() for r in rows})
    all_rows = {m: {r["question_id"]: r for r in rows} for m, rows in results.items()}
    all_qids = [r["question_id"] for r in results[model_names[0]]]  # preserve question order

    # ── Summary table ────────────────────────────────────────────────────────
    summary_rows = ""
    for subject in all_subjects:
        cells = "".join(
            f"<td style='text-align:center'>{_pct(*_pass_stats(results[m], subject))}</td>"
            for m in model_names
        )
        summary_rows += f"<tr><td><b>{_esc(subject)}</b></td>{cells}</tr>\n"

    overall_cells = "".join(
        f"<td style='text-align:center'>{_pct(*_pass_stats(results[m]))}</td>"
        for m in model_names
    )
    summary_rows += f"<tr style='border-top:2px solid #ccc'><td><b>OVERALL</b></td>{overall_cells}</tr>\n"

    model_headers = "".join(f"<th>{_esc(m)}</th>" for m in model_names)

    # ── Legend ───────────────────────────────────────────────────────────────
    legend = " &nbsp; ".join(_badge(c) for c in CLASSIFICATIONS)

    # ── Detail table ─────────────────────────────────────────────────────────
    detail_rows = ""
    for qid in all_qids:
        first = next(iter(all_rows.values()))[qid]
        subject = first.get("subject", "")
        question = first.get("question", "")
        ground_truth = first.get("ground_truth", "")

        model_cells = ""
        for m in model_names:
            row = all_rows[m].get(qid, {})
            cls = row.get("classification", "")
            response = row.get("response", "")
            reasoning = row.get("reasoning", "")
            kpc = row.get("key_point_coverage")
            _, bg = GRADE_COLORS.get(cls, ("#000", "#fff"))

            kpc_str = f'<div style="font-size:11px;color:#555;margin-top:4px">Coverage: {kpc:.0%}</div>' if kpc is not None else ""
            model_cells += (
                f'<td style="background:{bg};vertical-align:top;padding:8px;min-width:240px">'
                f'{_badge(cls)}'
                f'<div style="margin-top:6px;font-size:13px">{_cell(response, 200)}</div>'
                f'<div style="margin-top:4px;font-size:11px;color:#555;font-style:italic">{_esc(reasoning)}</div>'
                f'{kpc_str}'
                f'</td>'
            )

        detail_rows += (
            f'<tr>'
            f'<td style="vertical-align:top;padding:8px;font-size:12px;color:#555;white-space:nowrap">{_esc(subject)}</td>'
            f'<td style="vertical-align:top;padding:8px;font-size:13px;max-width:260px">{_cell(question, 150)}</td>'
            f'<td style="vertical-align:top;padding:8px;font-size:12px;color:#444;max-width:200px">{_cell(ground_truth, 120)}</td>'
            f'{model_cells}'
            f'</tr>\n'
        )

    model_detail_headers = "".join(f'<th style="min-width:240px">{_esc(m)}</th>' for m in model_names)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASTAT Benchmark Results</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #f4f6f9; color: #1a1a1a; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 26px; font-weight: 700; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
  .card {{ background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.12);
           padding: 20px; margin-bottom: 24px; }}
  h2 {{ font-size: 16px; font-weight: 600; margin-bottom: 14px; color: #333; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
  th {{ background: #2c3e50; color: #fff; padding: 10px 12px; text-align: left;
        position: sticky; top: 0; z-index: 2; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #eee; vertical-align: top; }}
  tr:hover td {{ background: rgba(0,0,0,.02); }}
  .detail-wrap {{ overflow-x: auto; }}
  .filter-bar {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; align-items:center; }}
  .filter-bar select, .filter-bar input {{
    padding: 6px 10px; border: 1px solid #ccc; border-radius:6px; font-size:13px;
  }}
  .filter-bar label {{ font-size:13px; color:#555; }}
</style>
</head>
<body>
<div class="container">

  <h1>ASTAT Benchmark Results</h1>
  <p class="subtitle">Are you Smarter than a 12th Grader? — Model comparison across {len(all_qids)} questions</p>

  <div class="card">
    <h2>Pass Rate Summary</h2>
    <table>
      <thead><tr><th>Subject</th>{model_headers}</tr></thead>
      <tbody>{summary_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Legend</h2>
    <p style="font-size:13px">{legend}</p>
  </div>

  <div class="card">
    <h2>Detailed Results</h2>
    <div class="filter-bar">
      <label>Filter subject:</label>
      <select id="subjectFilter" onchange="filterTable()">
        <option value="">All subjects</option>
        {"".join(f'<option value="{s}">{s}</option>' for s in all_subjects)}
      </select>
      <label>Search question:</label>
      <input id="searchBox" type="text" placeholder="type to search…" oninput="filterTable()" style="width:220px">
    </div>
    <div class="detail-wrap">
      <table id="detailTable">
        <thead>
          <tr>
            <th>Subject</th>
            <th>Question</th>
            <th>Golden Answer</th>
            {model_detail_headers}
          </tr>
        </thead>
        <tbody>{detail_rows}</tbody>
      </table>
    </div>
  </div>

</div>
<script>
function filterTable() {{
  const sub = document.getElementById('subjectFilter').value.toLowerCase();
  const q   = document.getElementById('searchBox').value.toLowerCase();
  document.querySelectorAll('#detailTable tbody tr').forEach(row => {{
    const cells = row.querySelectorAll('td');
    const subMatch = !sub || cells[0].textContent.toLowerCase().includes(sub);
    const qMatch   = !q   || cells[1].textContent.toLowerCase().includes(q);
    row.style.display = (subMatch && qMatch) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")
    return path
