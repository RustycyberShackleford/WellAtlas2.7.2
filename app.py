import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, abort
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "wellatlas.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB

# -------- DB helpers --------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            job_number TEXT,
            customer TEXT,
            description TEXT,
            latitude REAL,
            longitude REAL,
            deleted INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            filename TEXT,
            caption TEXT,
            created_at TEXT,
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            body TEXT,
            created_at TEXT,
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('header_title', 'WellAtlas by Henry Suden')")
    conn.commit()
    conn.close()

def get_setting(key, default=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()

# -------- Routes --------
@app.route("/")
def index():
    header_title = get_setting("header_title", "WellAtlas by Henry Suden")
    return render_template("index.html", header_title=header_title)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        title = request.form.get("header_title", "").strip() or "WellAtlas by Henry Suden"
        set_setting("header_title", title)
        flash("Header updated.", "success")
        return redirect(url_for("settings"))
    header_title = get_setting("header_title", "WellAtlas by Henry Suden")
    return render_template("settings.html", header_title=header_title)

@app.route("/api/sites")
def api_sites():
    q = (request.args.get("q") or "").strip()
    conn = get_db()
    c = conn.cursor()
    if q:
        like = f"%{q}%"
        c.execute(
            "SELECT * FROM sites WHERE deleted=0 AND (name LIKE ? OR job_number LIKE ? OR customer LIKE ? OR description LIKE ?) ORDER BY datetime(created_at) DESC",
            (like, like, like, like),
        )
    else:
        c.execute("SELECT * FROM sites WHERE deleted=0 ORDER BY datetime(created_at) DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route("/sites/create", methods=["POST"])
def create_site():
    name = (request.form.get("name") or "").strip() or "Untitled Site"
    job_number = (request.form.get("job_number") or "").strip()
    customer = (request.form.get("customer") or "").strip()
    description = (request.form.get("description") or "").strip()
    try:
        lat = float(request.form.get("latitude") or 0.0)
        lon = float(request.form.get("longitude") or 0.0)
    except ValueError:
        lat, lon = 0.0, 0.0
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sites (name, job_number, customer, description, latitude, longitude, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, job_number, customer, description, lat, lon, datetime.utcnow().isoformat()),
    )
    conn.commit()
    site_id = c.lastrowid
    conn.close()
    flash("Site created.", "success")
    return redirect(url_for("site_detail", site_id=site_id))

@app.route("/sites/<int:site_id>")
def site_detail(site_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM sites WHERE id=?", (site_id,))
    site = c.fetchone()
    if not site:
        flash("Site not found.", "danger")
        return redirect(url_for("index"))
    c.execute("SELECT * FROM photos WHERE site_id=? ORDER BY datetime(created_at) DESC", (site_id,))
    photos = c.fetchall()
    c.execute("SELECT * FROM notes WHERE site_id=? ORDER BY datetime(created_at) DESC", (site_id,))
    notes = c.fetchall()
    conn.close()
    header_title = get_setting("header_title", "WellAtlas by Henry Suden")
    return render_template("site_detail.html", site=site, photos=photos, notes=notes, header_title=header_title)

@app.route("/sites/<int:site_id>/edit", methods=["POST"])
def edit_site(site_id: int):
    name = (request.form.get("name") or "").strip() or "Untitled Site"
    job_number = (request.form.get("job_number") or "").strip()
    customer = (request.form.get("customer") or "").strip()
    description = (request.form.get("description") or "").strip()
    try:
        lat = float(request.form.get("latitude") or 0.0)
        lon = float(request.form.get("longitude") or 0.0)
    except ValueError:
        lat, lon = 0.0, 0.0
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE sites SET name=?, job_number=?, customer=?, description=?, latitude=?, longitude=? WHERE id=?",
        (name, job_number, customer, description, lat, lon, site_id),
    )
    conn.commit()
    conn.close()
    flash("Site updated.", "success")
    return redirect(url_for("site_detail", site_id=site_id))

@app.route("/sites/<int:site_id>/delete", methods=["POST"])
def delete_site(site_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE sites SET deleted=1 WHERE id=?", (site_id,))
    conn.commit()
    conn.close()
    flash("Site moved to Deleted Sites.", "info")
    return redirect(url_for("index"))

@app.route("/deleted")
def deleted_sites():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM sites WHERE deleted=1 ORDER BY datetime(created_at) DESC")
    sites = c.fetchall()
    conn.close()
    header_title = get_setting("header_title", "WellAtlas by Henry Suden")
    return render_template("deleted_sites.html", sites=sites, header_title=header_title)

@app.route("/sites/<int:site_id>/restore", methods=["POST"])
def restore_site(site_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE sites SET deleted=0 WHERE id=?", (site_id,))
    conn.commit()
    conn.close()
    flash("Site restored.", "success")
    return redirect(url_for("deleted_sites"))

# ---- Photos ----
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(fname: str) -> bool:
    return "." in fname and fname.rsplit(".", 1)[1].lower() in ALLOWED_EXT

@app.route("/sites/<int:site_id>/upload", methods=["POST"])
def upload_photo(site_id: int):
    file = request.files.get("photo")
    caption = (request.form.get("caption") or "").strip()
    if not file or file.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("site_detail", site_id=site_id))
    if not allowed_file(file.filename):
        flash("Unsupported file type.", "danger")
        return redirect(url_for("site_detail", site_id=site_id))
    fname = secure_filename(file.filename)
    base, ext = os.path.splitext(fname)
    uniq = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    fname = f"{base}_{uniq}{ext}"
    file.save(os.path.join(UPLOAD_DIR, fname))

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO photos (site_id, filename, caption, created_at) VALUES (?, ?, ?, ?)",
        (site_id, fname, caption, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    flash("Photo uploaded.", "success")
    return redirect(url_for("site_detail", site_id=site_id))

@app.route("/uploads/<path:filename>")
def serve_upload(filename: str):
    return send_from_directory(UPLOAD_DIR, filename)

# ---- Notes ----
@app.route("/sites/<int:site_id>/note", methods=["POST"])
def add_note(site_id: int):
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Note is empty.", "warning")
        return redirect(url_for("site_detail", site_id=site_id))
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO notes (site_id, body, created_at) VALUES (?, ?, ?)",
        (site_id, body, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    flash("Note added.", "success")
    return redirect(url_for("site_detail", site_id=site_id))

# ---- KML Import ----
from xml.etree import ElementTree as ET

@app.route("/import/kml", methods=["POST"])
def import_kml():
    file = request.files.get("kmlfile")
    if not file or file.filename == "":
        flash("No KML file selected.", "warning")
        return redirect(url_for("index"))
    content = file.read()
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        flash("Invalid KML file.", "danger")
        return redirect(url_for("index"))
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    placemarks = root.findall(".//kml:Placemark", ns)
    imported = 0
    conn = get_db()
    c = conn.cursor()
    for pm in placemarks:
        name_el = pm.find("kml:name", ns)
        name = (name_el.text.strip() if (name_el is not None and name_el.text) else "Imported Placemark")
        coord_el = pm.find(".//kml:coordinates", ns)
        if coord_el is None or not coord_el.text:
            continue
        coords = coord_el.text.strip().split()[0].split(",")
        try:
            lon = float(coords[0]); lat = float(coords[1])
        except Exception:
            continue
        c.execute(
            "INSERT INTO sites (name, job_number, customer, description, latitude, longitude, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, "", "", "Imported from KML", lat, lon, datetime.utcnow().isoformat()),
        )
        imported += 1
    conn.commit()
    conn.close()
    flash(f"Imported {imported} placemark(s).", "success")
    return redirect(url_for("index"))

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Not Found"), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
