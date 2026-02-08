import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import psycopg2
import psycopg2.extras

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# Login config (set these in Render Environment)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
APP_USER = os.environ.get("APP_USER", "geqisheng")
APP_PASS = os.environ.get("APP_PASS", "gqs123")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def get_db_conn():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL is missing in Render Environment Variables")
    return psycopg2.connect(db_url, sslmode="require")


def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id SERIAL PRIMARY KEY,
            device_id TEXT NOT NULL,
            ts TIMESTAMPTZ NOT NULL,
            temperature_c DOUBLE PRECISION,
            humidity_pct DOUBLE PRECISION,
            pressure_hpa DOUBLE PRECISION,
            cpu_temp_c DOUBLE PRECISION,
            raw_temp_c DOUBLE PRECISION,
            target_c DOUBLE PRECISION NOT NULL DEFAULT 25.0,
            fan_on BOOLEAN NOT NULL DEFAULT FALSE
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


# Ensure table exists under gunicorn on Render
try:
    if os.environ.get("DATABASE_URL", ""):
        init_db()
except Exception as e:
    print("init_db failed:", e)


# ------------------------
# Auth pages
# ------------------------
@app.get("/login")
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html", error=None)


@app.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()

    if username == APP_USER and password == APP_PASS:
        session["logged_in"] = True
        nxt = request.args.get("next") or "/"
        return redirect(nxt)

    return render_template("login.html", error="Invalid username or password.")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------
# Dashboard (protected)
# ------------------------
@app.get("/")
@login_required
def dashboard():
    return render_template("index.html")


# ------------------------
# APIs
# ------------------------
@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


# ingest is for Raspberry Pi uploader (API key protected, not login)
@app.post("/api/ingest")
def ingest():
    api_key = os.environ.get("CLOUD_API_KEY", "")
    client_key = request.headers.get("X-API-KEY", "")

    if not api_key:
        return jsonify({"error": "CLOUD_API_KEY not set on server"}), 500
    if client_key != api_key:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    device_id = data.get("device_id")
    ts = data.get("ts")
    if not device_id or not ts:
        return jsonify({"error": "device_id and ts are required"}), 400

    temperature_c = data.get("temperature_c")
    humidity_pct = data.get("humidity_pct")
    pressure_hpa = data.get("pressure_hpa")
    cpu_temp_c = data.get("cpu_temp_c")
    raw_temp_c = data.get("raw_temp_c")

    target_c = data.get("target_c", 25.0)
    fan_on = bool(data.get("fan_on", False))

    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO readings
            (device_id, ts, temperature_c, humidity_pct, pressure_hpa, cpu_temp_c, raw_temp_c, target_c, fan_on)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            device_id, ts,
            temperature_c, humidity_pct, pressure_hpa,
            cpu_temp_c, raw_temp_c,
            target_c, fan_on
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# latest/history should be protected because the webpage uses them
@app.get("/api/latest")
@login_required
def latest():
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT *
            FROM readings
            ORDER BY id DESC
            LIMIT 1;
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return jsonify({"status": "empty", "message": "No readings yet"})
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/history")
@login_required
def history():
    try:
        limit = int(request.args.get("limit", "30"))
        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200

        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT *
            FROM readings
            ORDER BY id DESC
            LIMIT %s;
        """, (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
