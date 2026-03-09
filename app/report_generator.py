"""
report_generator.py — Excel and PDF export for HR Hiring Bot
"""

import io
from datetime import datetime
from typing import List, Dict


# ─── Excel Export ─────────────────────────────────────────────────────────────

def export_to_excel(results: List[Dict]) -> bytes:
    """
    Convert a list of candidate result dicts to a formatted Excel workbook.
    Returns raw bytes suitable for st.download_button().
    """
    import openpyxl
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side, GradientFill
    )
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Candidate Results"

    # ── Styles ────────────────────────────────────────────────────────────────
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="4F46E5")  # Indigo
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    accept_fill = PatternFill("solid", fgColor="D1FAE5")   # green
    reject_fill = PatternFill("solid", fgColor="FEE2E2")   # red
    alt_fill = PatternFill("solid", fgColor="F8FAFC")      # light grey

    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # ── Title row ─────────────────────────────────────────────────────────────
    ws.merge_cells("A1:K1")
    title_cell = ws["A1"]
    title_cell.value = f"HR Hiring Bot — Candidate Report   ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    title_cell.font = Font(name="Calibri", bold=True, size=14, color="1E293B")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    title_cell.fill = PatternFill("solid", fgColor="EEF2FF")
    ws.row_dimensions[1].height = 30

    # ── Header row ────────────────────────────────────────────────────────────
    headers = ["Rank", "Name", "Email", "Mobile", "Final Score",
               "Status", "Experience", "Education", "Skills", "Source", "Processed At"]
    col_widths = [6, 22, 28, 14, 12, 12, 12, 20, 40, 10, 18]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=2, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[2].height = 22

    # ── Data rows ─────────────────────────────────────────────────────────────
    for row_idx, candidate in enumerate(results, start=3):
        score = candidate.get("Final Score", candidate.get("score", 0)) or 0
        status = candidate.get("Status", "✅ Accepted" if score >= 6.5 else "❌ Rejected")
        is_accepted = score >= 6.5

        row_fill = accept_fill if is_accepted else reject_fill if not is_accepted else alt_fill
        if row_idx % 2 == 0 and "Accepted" not in str(status) and "Rejected" not in str(status):
            row_fill = alt_fill

        data = [
            candidate.get("Rank", row_idx - 2),
            candidate.get("Name", "N/A"),
            candidate.get("Email", "N/A"),
            candidate.get("Mobile", "N/A"),
            round(float(score), 2),
            "Accepted" if is_accepted else "Rejected",
            candidate.get("Experience", "N/A"),
            candidate.get("Education", candidate.get("education", "N/A")),
            candidate.get("Skills", candidate.get("skills", "")),
            candidate.get("Source", candidate.get("source", "N/A")),
            candidate.get("Processed At", candidate.get("created_at", "")),
        ]

        for col_idx, value in enumerate(data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = border
            if col_idx in (1, 5, 6):
                cell.alignment = center
            else:
                cell.alignment = left

            # Row background based on accept/reject
            if col_idx == 6:
                cell.fill = accept_fill if is_accepted else reject_fill
                cell.font = Font(
                    bold=True,
                    color="065F46" if is_accepted else "991B1B"
                )
            elif row_idx % 2 == 0:
                cell.fill = alt_fill

    # ── Freeze header rows ────────────────────────────────────────────────────
    ws.freeze_panes = "A3"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─── PDF Export ───────────────────────────────────────────────────────────────

def export_to_pdf(results: List[Dict]) -> bytes:
    """
    Convert a list of candidate result dicts to a styled PDF report.
    Returns raw bytes suitable for st.download_button().
    """
    from fpdf import FPDF

    class HRReport(FPDF):
        def header(self):
            self.set_fill_color(79, 70, 229)   # Indigo
            self.rect(0, 0, 210, 18, "F")
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(255, 255, 255)
            self.set_y(4)
            self.cell(0, 10, "HR Hiring Bot — Candidate Report", align="C")
            self.set_text_color(0, 0, 0)
            self.ln(16)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 116, 139)
            self.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}   |   Page {self.page_no()}", align="C")

    pdf = HRReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Summary line
    total = len(results)
    accepted_count = sum(1 for r in results if float(r.get("Final Score", r.get("score", 0)) or 0) >= 6.5)
    avg_score = sum(float(r.get("Final Score", r.get("score", 0)) or 0) for r in results) / total if total else 0

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(0, 7, f"Total Candidates: {total}   |   Accepted: {accepted_count}   |   Average Score: {avg_score:.2f}/10", align="C")
    pdf.ln(8)

    # Table header
    col_labels = ["#", "Name", "Email", "Score", "Status", "Experience", "Skills"]
    col_widths  = [10,  38,    52,     18,     22,     20,          30]

    pdf.set_fill_color(79, 70, 229)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    for label, w in zip(col_labels, col_widths):
        pdf.cell(w, 8, label, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for i, cand in enumerate(results):
        score = float(cand.get("Final Score", cand.get("score", 0)) or 0)
        is_accepted = score >= 6.5

        if i % 2 == 0:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.set_text_color(30, 41, 59)

        row_data = [
            str(cand.get("Rank", i + 1)),
            str(cand.get("Name", "N/A"))[:22],
            str(cand.get("Email", "N/A"))[:30],
            f"{score:.2f}",
            "Accepted" if is_accepted else "Rejected",
            str(cand.get("Experience", "N/A"))[:12],
            str(cand.get("Skills", cand.get("skills", "")))[:25],
        ]

        # Colour code the Status cell
        y_before = pdf.get_y()
        for j, (value, w) in enumerate(zip(row_data, col_widths)):
            x = pdf.get_x()
            if j == 4:  # Status column
                if is_accepted:
                    pdf.set_text_color(6, 95, 70)
                else:
                    pdf.set_text_color(153, 27, 27)
            else:
                pdf.set_text_color(30, 41, 59)
            pdf.cell(w, 7, value, border=1, align="C" if j in (0, 3, 4) else "L", fill=(j != 4))
        pdf.ln()

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
