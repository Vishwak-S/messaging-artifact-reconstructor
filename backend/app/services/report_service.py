"""
Forensic report generation service.

Generates PDF, CSV, JSON, and HTML reports.
All reports clearly distinguish observed evidence from derived information.
"""
import csv
import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    AuditEvent, Case, Conversation, Evidence, Message, Report
)


def _gen_report_id() -> str:
    return f"RPT-{str(uuid.uuid4())[:10].upper()}"


def _get_case_data(db: Session, case_id: str):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    evidence_list = db.query(Evidence).filter(Evidence.case_id == case_id).all()
    conversations = db.query(Conversation).filter(Conversation.case_id == case_id).all()
    messages = db.query(Message).filter(Message.case_id == case_id).order_by(Message.timestamp).all()
    audit = db.query(AuditEvent).filter(AuditEvent.case_id == case_id).order_by(AuditEvent.timestamp).all()
    return case, evidence_list, conversations, messages, audit


def generate_report(db: Session, case_id: str, fmt: str, include_raw: bool = False) -> Report:
    case, evidence_list, conversations, messages, audit = _get_case_data(db, case_id)
    if not case:
        raise ValueError(f"Case {case_id} not found.")

    report_id = _gen_report_id()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{report_id}_{case_id}_{ts}.{fmt}"
    out_path = Path(settings.REPORTS_DIR) / filename

    if fmt == "json":
        _gen_json(out_path, case, evidence_list, conversations, messages, audit, include_raw)
    elif fmt == "csv":
        _gen_csv(out_path, messages)
    elif fmt == "html":
        _gen_html(out_path, case, evidence_list, conversations, messages, audit)
    elif fmt == "pdf":
        _gen_pdf(out_path, case, evidence_list, conversations, messages, audit)
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    size = out_path.stat().st_size if out_path.exists() else 0

    rpt = Report(
        report_id=report_id,
        case_id=case_id,
        format=fmt,
        file_path=str(out_path),
        generated_at=datetime.utcnow(),
        file_size_bytes=size,
    )
    db.add(rpt)
    db.add(AuditEvent(case_id=case_id, evidence_id=None,
                      action="REPORT_GENERATED",
                      description=f"Report {report_id} ({fmt}) generated."))
    db.commit()
    db.refresh(rpt)
    return rpt


# ── JSON ─────────────────────────────────────────────────────────────────────

def _gen_json(path, case, evidence_list, conversations, messages, audit, include_raw):
    data = {
        "report_type": "forensic_evidence_report",
        "generated_at": datetime.utcnow().isoformat(),
        "disclaimer": (
            "This report is generated from forensic analysis of digital artifacts. "
            "All information is derived from the source databases. "
            "Interpretations are derived; raw values are preserved."
        ),
        "case": {
            "case_id": case.case_id,
            "name": case.name,
            "investigator": case.investigator,
            "status": case.status,
            "created_at": case.created_at.isoformat(),
        },
        "evidence": [
            {
                "evidence_id": e.evidence_id,
                "filename": e.original_filename,
                "sha256": e.sha256_hash,
                "size_bytes": e.original_size_bytes,
                "imported": e.import_timestamp.isoformat(),
                "app_detected": e.app_detected,
                "confidence": e.detection_confidence,
            }
            for e in evidence_list
        ],
        "conversations": [
            {
                "conv_id": c.conv_id,
                "display_name": c.display_name,
                "application": c.application,
                "message_count": c.message_count,
                "is_group": c.is_group,
            }
            for c in conversations
        ],
        "messages": [
            _msg_to_dict(m, include_raw) for m in messages
        ],
        "chain_of_custody": [
            {
                "timestamp": a.timestamp.isoformat(),
                "action": a.action,
                "description": a.description,
            }
            for a in audit
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ── CSV ───────────────────────────────────────────────────────────────────────

def _gen_csv(path, messages):
    fieldnames = [
        "message_id", "application", "conversation_id", "sender", "recipient",
        "timestamp", "timestamp_original", "message_type", "message_text",
        "direction", "status", "evidence_status", "source_database",
        "source_table", "source_record", "parser_version",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for m in messages:
            writer.writerow({
                "message_id": m.message_id,
                "application": m.application,
                "conversation_id": m.conv_id,
                "sender": m.sender,
                "recipient": m.recipient,
                "timestamp": m.timestamp.isoformat() if m.timestamp else "",
                "timestamp_original": m.timestamp_original,
                "message_type": m.message_type,
                "message_text": m.message_text,
                "direction": m.direction,
                "status": m.status,
                "evidence_status": m.evidence_status,
                "source_database": m.source_database,
                "source_table": m.source_table,
                "source_record": m.source_record,
                "parser_version": m.parser_version,
            })


# ── HTML ──────────────────────────────────────────────────────────────────────

def _gen_html(path, case, evidence_list, conversations, messages, audit):
    rows = ""
    for m in messages[:2000]:
        ts = m.timestamp.strftime("%Y-%m-%d %H:%M:%S") if m.timestamp else "Unknown"
        text = (m.message_text or "")[:200]
        rows += (
            f"<tr><td>{ts}</td><td>{m.application}</td>"
            f"<td>{m.sender or ''}</td><td>{text}</td>"
            f"<td><span class='badge'>{m.evidence_status}</span></td>"
            f"<td>{m.source_record}</td></tr>\n"
        )

    ev_rows = ""
    for e in evidence_list:
        ev_rows += (
            f"<tr><td>{e.original_filename}</td><td>{e.sha256_hash}</td>"
            f"<td>{e.app_detected}</td><td>{e.import_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Forensic Report — {case.case_id}</title>
<style>
  body {{ font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 2rem; }}
  h1,h2 {{ color: #58a6ff; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
  th,td {{ border: 1px solid #30363d; padding: 6px 10px; font-size: 12px; text-align: left; }}
  th {{ background: #161b22; color: #8b949e; }}
  .badge {{ background: #1f6feb; padding: 2px 6px; border-radius: 4px; font-size: 10px; }}
  .disclaimer {{ background: #161b22; border-left: 4px solid #f85149; padding: 1rem; margin-bottom: 1rem; }}
</style>
</head>
<body>
<h1>Forensic Evidence Report</h1>
<div class="disclaimer">
<strong>DISCLAIMER:</strong> This report presents information derived from digital forensic analysis.
All timestamps and sender attributions are derived from database records.
This report does not constitute legal attribution without further investigation.
</div>
<h2>Case Information</h2>
<table><tr><th>Field</th><th>Value</th></tr>
<tr><td>Case ID</td><td>{case.case_id}</td></tr>
<tr><td>Name</td><td>{case.name}</td></tr>
<tr><td>Investigator</td><td>{case.investigator or 'N/A'}</td></tr>
<tr><td>Status</td><td>{case.status}</td></tr>
<tr><td>Created</td><td>{case.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
<tr><td>Report Generated</td><td>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</td></tr>
</table>
<h2>Evidence Files</h2>
<table>
<tr><th>Filename</th><th>SHA-256</th><th>Application</th><th>Imported</th></tr>
{ev_rows}
</table>
<h2>Extracted Messages ({len(messages)} total)</h2>
<table>
<tr><th>Timestamp</th><th>App</th><th>Sender</th><th>Message</th><th>Status</th><th>Record ID</th></tr>
{rows}
</table>
</body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ── PDF ───────────────────────────────────────────────────────────────────────

def _gen_pdf(path, case, evidence_list, conversations, messages, audit):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        )

        doc = SimpleDocTemplate(str(path), pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle("title", parent=styles["Title"],
                                     textColor=colors.HexColor("#1a5276"),
                                     fontSize=18, spaceAfter=12)
        h2_style = ParagraphStyle("h2", parent=styles["Heading2"],
                                  textColor=colors.HexColor("#1a5276"))
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8)
        warn_style = ParagraphStyle("warn", parent=styles["Normal"],
                                    textColor=colors.red, fontSize=9,
                                    borderPad=4, backColor=colors.lightyellow)

        story.append(Paragraph("FORENSIC EVIDENCE REPORT", title_style))
        story.append(Paragraph(
            "DISCLAIMER: Information in this report is derived from digital forensic analysis "
            "of SQLite database artifacts. All timestamps and sender fields are obtained from "
            "database records. This report does not constitute legal attribution.",
            warn_style
        ))
        story.append(Spacer(1, 0.5*cm))

        # Case info
        story.append(Paragraph("Case Information", h2_style))
        case_data = [
            ["Field", "Value"],
            ["Case ID", case.case_id],
            ["Case Name", case.name],
            ["Investigator", case.investigator or "N/A"],
            ["Status", case.status],
            ["Created", case.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")],
            ["Report Generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")],
        ]
        t = Table(case_data, colWidths=[5*cm, 12*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eaf4fb")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        # Evidence
        story.append(Paragraph("Evidence Files", h2_style))
        ev_data = [["Filename", "SHA-256", "Application", "Confidence", "Imported"]]
        for e in evidence_list:
            ev_data.append([
                e.original_filename[:40],
                (e.sha256_hash or "N/A")[:16] + "...",
                e.app_detected or "Unknown",
                e.detection_confidence or "N/A",
                e.import_timestamp.strftime("%Y-%m-%d"),
            ])
        t = Table(ev_data, colWidths=[4*cm, 3.5*cm, 3*cm, 2.5*cm, 3*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        # Messages
        story.append(PageBreak())
        story.append(Paragraph(f"Extracted Messages (Total: {len(messages)})", h2_style))
        msg_data = [["Timestamp", "App", "Sender", "Message", "Type", "Record"]]
        for m in messages[:500]:
            ts = m.timestamp.strftime("%Y-%m-%d %H:%M") if m.timestamp else "Unknown"
            text = (m.message_text or "")[:60]
            msg_data.append([ts, m.application or "", (m.sender or "")[:20],
                             text, m.message_type, m.source_record or ""])
        t = Table(msg_data, colWidths=[3.5*cm, 2.5*cm, 3*cm, 5*cm, 2*cm, 2*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ]))
        story.append(t)

        # Chain of custody
        story.append(PageBreak())
        story.append(Paragraph("Chain of Custody Log", h2_style))
        coc_data = [["Timestamp", "Action", "Description"]]
        for a in audit:
            coc_data.append([
                a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                a.action,
                (a.description or "")[:80],
            ])
        t = Table(coc_data, colWidths=[4*cm, 4*cm, 10*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ]))
        story.append(t)

        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(
            "Limitations: This report was generated by the Messaging App Artifact Reconstructor. "
            "Analysis is limited to accessible database records. Deleted records may not be fully recovered. "
            "Timezone information may be unavailable. This tool does not perform device acquisition.",
            small
        ))

        doc.build(story)

    except ImportError:
        # Fallback: write a plain text file if ReportLab is not installed
        with open(str(path), "w", encoding="utf-8") as f:
            f.write(f"FORENSIC REPORT — {case.case_id}\n")
            f.write("=" * 60 + "\n")
            f.write("ReportLab not installed. Install with: pip install reportlab\n")


def _msg_to_dict(m, include_raw: bool) -> dict:
    d = {
        "message_id": m.message_id,
        "application": m.application,
        "conversation_id": m.conv_id,
        "sender": m.sender,
        "recipient": m.recipient,
        "timestamp": m.timestamp.isoformat() if m.timestamp else None,
        "timestamp_original": m.timestamp_original,
        "timezone": m.timezone_info,
        "message_type": m.message_type,
        "message_text": m.message_text,
        "direction": m.direction,
        "status": m.status,
        "evidence_status": m.evidence_status,
        "source_database": m.source_database,
        "source_table": m.source_table,
        "source_record": m.source_record,
        "parser_version": m.parser_version,
    }
    if include_raw:
        d["raw_record"] = m.raw_record
    return d
