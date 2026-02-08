import os
from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras

app = Flask(__name__, template_folder="templates", static_folder="static")


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


# IMPORTANT: ensure DB/table exists under gunicorn on Render
try:
    if os.environ.get("DATABASE_URL", ""):
        init_db()
except Exception as e:
    print("init_db failed:", e)


@app.route("/")
def home():
    return """
    <h2>Temperature Management System - Cloud API</h2>
    <p>OK. Try <a href="/api/health">/api/health</a></p>
    <p>Try <a href="/api/latest">/api/latest</a></p>
    """


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/ingest", methods=["POST"])
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

    # NEW: defaults so NOT NULL constraint won't fail
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


@app.route("/api/latest")
def latest():
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT *
            FROM readings
            ORDER BY ts DESC
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
