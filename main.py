from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4, UUID
from datetime import datetime

app = FastAPI()

# === In-Memory Mock DB ===
companies = {}
pours = []

# === Predefined Companies ===
PREDEFINED_COMPANIES = ["PCL", "Graham", "Bird"]

# === Models ===
class Company(BaseModel):
    id: UUID
    name: str

class Pour(BaseModel):
    id: UUID
    company: str
    area: str
    tag: str
    date: datetime
    volume_m3: float

class PourCreate(BaseModel):
    company: str
    area: str
    tag: str
    date: datetime
    volume_m3: float

# === API Routes ===
@app.post("/pour/", response_model=Pour)
def submit_pour(pour_data: PourCreate):
    if pour_data.company not in PREDEFINED_COMPANIES:
        raise HTTPException(status_code=400, detail="Invalid company")
    pour = Pour(
        id=uuid4(),
        **pour_data.dict()
    )
    pours.append(pour)
    return pour

@app.get("/pours/", response_model=List[Pour])
def list_pours():
    return pours

@app.get("/report/")
def generate_report():
    return [
        {
            "Area": p.area,
            "Tag": p.tag,
            "Company": p.company,
            "Volume": p.volume_m3,
            "Date": p.date.strftime("%Y-%m-%d")
        }
        for p in pours
    ]

# === Simple HTML Form ===
@app.get("/submit", response_class=HTMLResponse)
def form_page():
    table_rows = "".join(
        f"<tr><td>{p.area}</td><td>{p.tag}</td><td>{p.company}</td><td>{p.volume_m3}</td><td>{p.date.strftime('%Y-%m-%d')}</td></tr>"
        for p in reversed(pours[-10:])  # Show last 10 entries
    )
    return f"""
    <html>
        <head>
            <title>Submit Concrete Pour</title>
        </head>
        <body>
            <h1>Concrete Pour Submission</h1>
            <form action="/submit" method="post">
                Company:
                <select name="company">
                    <option value="PCL">PCL</option>
                    <option value="Graham">Graham</option>
                    <option value="Bird">Bird</option>
                </select><br>
                Area: <input type="text" name="area"><br>
                Tag: <input type="text" name="tag"><br>
                Date: <input type="date" name="date"><br>
                Volume (m³): <input type="number" step="0.1" name="volume"><br>
                <input type="submit" value="Submit">
            </form>
            <p style='color: green;'>Submission successful!</p>
            <h2>Last 10 Pours</h2>
            <table border="1">
                <tr><th>Area</th><th>Tag</th><th>Company</th><th>Volume</th><th>Date</th></tr>
                {table_rows}
            </table>
        </body>
    </html>
    """

@app.post("/submit")
def handle_form(company: str = Form(...), area: str = Form(...), tag: str = Form(...), date: str = Form(...), volume: float = Form(...)):
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
        volume_m3=volume
    )
    pours.append(pour)
    return RedirectResponse(url="/submit?success=true", status_code=303)
