import os
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4, UUID
from datetime import datetime, date
import json
import csv
from fpdf import FPDF
from collections import defaultdict

app = FastAPI()

# === Persistent Data File ===
DATA_FILE = "pours.json"
LOGO_PATH = "ap_logo.png"  # Logo to include in PDF

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump([p.dict() for p in pours], f, default=str)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                data = json.load(f)
                return [Pour(**d) for d in data]
            except json.JSONDecodeError:
                return []
    return []

# === Load initial data ===
pours = load_data()
deleted_pours = []  # runtime only

# === Predefined Companies ===
PREDEFINED_COMPANIES = ["PCL", "Graham", "Bird"]
COMPANY_COLORS = {
    "PCL": "#C7A600",    # Darker Yellow for contrast
    "Graham": "#FF0000", # Red
    "Bird": "#008000"     # Green
}

# === Models ===
class Pour(BaseModel):
    id: UUID
    company: str
    area: str
    tag: str
    date: datetime
    volume_m3: float
    comment: Optional[str] = None

class PourCreate(BaseModel):
    company: str
    area: str
    tag: str
    date: datetime
    volume_m3: float
    comment: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Concrete Pour Scheduler</title></head>
    <body>
        <h1>Concrete Pour App</h1>
        <p>Status: <strong>Online ✅</strong></p>
        <p>Go to <a href='/calendar'>Calendar View</a> to submit and see entries.</p>
    </body>
    </html>
    """

@app.post("/pour/", response_model=Pour)
def submit_pour(pour_data: PourCreate):
    if pour_data.company not in PREDEFINED_COMPANIES:
        raise HTTPException(status_code=400, detail="Invalid company")
    pour = Pour(id=uuid4(), **pour_data.dict())
    pours.append(pour)
    save_data()
    return pour

@app.get("/pours/", response_model=List[Pour])
def list_pours():
    return pours

@app.get("/calendar", response_class=HTMLResponse)
def calendar_view():
    events = [
        {
            "id": str(p.id),
            "title": f"{p.company}: {p.tag} ({p.area}) - {p.volume_m3}m³" + (f" | {p.comment}" if p.comment else ""),
            "start": p.date.strftime("%Y-%m-%d"),
            "color": COMPANY_COLORS.get(p.company, "#000000")
        }
        for p in pours
    ]
    deleted_log = "".join([
        f"<li>{p.date.strftime('%Y-%m-%d')} - {p.company}: {p.tag} ({p.area}) - {p.volume_m3}m³" + (f" | {p.comment}" if p.comment else "") + "</li>"
        for p in deleted_pours[::-1]
    ])
    return f"""
    <html>
    <head>
        <title>Concrete Pour Calendar</title>
        <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.css' rel='stylesheet' />
        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.js'></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                const calendarEl = document.getElementById('calendar');
                const calendar = new FullCalendar.Calendar(calendarEl, {{
                    initialView: 'dayGridMonth',
                    validRange: {{
                        start: new Date().toISOString().split('T')[0],
                        end: new Date(Date.now() + 28 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
                    }},
                    eventContent: function(arg) {{
                        const event = arg.event;
                        const container = document.createElement('div');
                        container.innerHTML = `
                            <span>${{event.title}}</span>
                            <span style='float:right;cursor:pointer;margin-left:8px;color:white;font-weight:bold;' onclick="deletePour('${{event.id}}')">❌</span>
                        `;
                        return {{ domNodes: [container] }};
                    }},
                    dateClick: function(info) {{
                        const formHtml = `
                            <div id='popup-form' style='position:fixed;top:10%;left:10%;background:#fff;padding:20px;border:1px solid #ccc;z-index:1000;'>
                                <form method='post' action='/submit'>
                                    <input type='hidden' name='date' value='${{info.dateStr}}' />
                                    Company:
                                    <select name='company'>
                                        <option value='PCL'>PCL</option>
                                        <option value='Graham'>Graham</option>
                                        <option value='Bird'>Bird</option>
                                    </select><br>
                                    Area: <input name='area' /><br>
                                    Tag: <input name='tag' /><br>
                                    Volume: <input name='volume' type='number' step='0.1' /><br>
                                    Comment: <input name='comment' /><br>
                                    <input type='submit' value='Submit' />
                                    <button type='button' onclick='document.getElementById("popup-form").remove();'>Cancel</button>
                                </form>
                            </div>
                        `;
                        const div = document.createElement('div');
                        div.innerHTML = formHtml;
                        document.body.appendChild(div);
                    }},
                    events: {json.dumps(events)}
                }});
                calendar.render();
            }});

            function deletePour(id) {{
                if (confirm("Delete this pour?")) {{
                    fetch(`/delete/${{id}}`, {{ method: 'POST' }}).then(() => location.reload());
                }}
            }}
        </script>
    </head>
    <body>
        <h1>Concrete Pour Calendar</h1>
        <div id='calendar'></div>
        <button onclick="window.location.href='/export/pdf'">Export to PDF</button>
        <hr>
        <h2>Deleted Pour Log</h2>
        <ul>{deleted_log or '<li>No deleted pours yet.</li>'}</ul>
    </body>
    </html>
    """

@app.post("/submit")
def handle_form(company: str = Form(...), area: str = Form(...), tag: str = Form(...), date: str = Form(...), volume: float = Form(...), comment: Optional[str] = Form(None)):
    try:
        date_parsed = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    if company not in PREDEFINED_COMPANIES:
        raise HTTPException(status_code=400, detail="Invalid company")
    pour = Pour(
        id=uuid4(),
        company=company,
        area=area,
        tag=tag,
        date=date_parsed,
        volume_m3=volume,
        comment=comment
    )
    pours.append(pour)
    save_data()
    return RedirectResponse(url="/calendar", status_code=303)

@app.post("/delete/{pour_id}")
def delete_pour(pour_id: UUID):
    global pours
    found = None
    for p in pours:
        if p.id == pour_id:
            found = p
            break
    if found:
        pours.remove(found)
        deleted_pours.append(found)
        save_data()
    return {"status": "deleted"}

@app.get("/export/pdf")
def export_pdf():
    pdf = FPDF(orientation='L', unit='mm', format='A3')
    pdf.add_page()

    if os.path.exists(LOGO_PATH):
        pdf.image(LOGO_PATH, x=10, y=8, w=40)  # Top left corner

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Concrete Pour Schedule", ln=True, align='C')
    pdf.ln(20)

    headers = ["Date", "Company", "Area", "Tag", "Volume (m³)", "Comment"]
    col_widths = [40, 35, 50, 50, 30, 100]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 10, h, 1)
    pdf.ln()
    for p in sorted(pours, key=lambda x: x.date):
        row = [
            p.date.strftime("%Y-%m-%d"),
            p.company,
            p.area,
            p.tag,
            f"{p.volume_m3:.1f}",
            p.comment or ""
        ]
        for i, cell in enumerate(row):
            pdf.cell(col_widths[i], 10, cell, 1)
        pdf.ln()
    file_path = "pours_report.pdf"
    pdf.output(file_path)
    return FileResponse(path=file_path, filename="concrete_pour_schedule.pdf", media_type='application/pdf')

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
