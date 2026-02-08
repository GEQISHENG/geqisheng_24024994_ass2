import os
from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras

app = Flask(__name__)

def get_db_conn():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is missing in Render Environment Variables")
    return psycopg2.connect(db_url, sslmode="require")

def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id BIGSERIAL PRIMARY KEY,
            device_id TEXT NOT NULL,
            ts TIMESTAMPTZ NOT NULL,

            temperature_c DOUBLE PRECISION,
            humidity_pct DOUBLE PRECISION,
            pressure_hpa DOUBLE PRECISION,
            cpu_temp_c DOUBLE PRECISION,
            raw_temp_c DOUBLE PRECISION,

            target_c DOUBLE PRECISION,
            fan_on BOOLEAN
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def require_api_key():
    api_key = os.environ.get("CLOUD_API_KEY", "").strip()
    if not api_key:
        return False, (jsonify({"error": "CLOUD_API_KEY not set on server"}), 500)
    client_key = request.headers.get("X-API-KEY", "").strip()
    if client_key != api_key:
        return False, (jsonify({"error": "Unauthorized"}), 401)
    return True, None

@app.route("/")
def home():
    return (
        "<h2>Cloud API is running</h2>"
        "<ul>"
        "<li><a href='/api/health'>/api/health</a></li>"
        "<li><a href='/api/latest'>/api/latest</a></li>"
        "<li><a href='/api/readings'>/api/readings</a></li>"
        "</ul>"
    )

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

def save_payload(data):
    device_id = data.get("device_id")
    ts = data.get("ts")
    if not device_id or not ts:
        return jsonify({"error": "device_id and ts are required"}), 400

    row = {
        "device_id": device_id,
        "ts": ts,
        "temperature_c": data.get("temperature_c"),
        "humidity_pct": data.get("humidity_pct"),
        "pressure_hpa": data.get("pressure_hpa"),
        "cpu_temp_c": data.get("cpu_temp_c"),
        "raw_temp_c": data.get("raw_temp_c"),
        "target_c": data.get("target_c"),
        "fan_on": data.get("fan_on"),
    }

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO readings
        (device_id, ts, temperature_c, humidity_pct, pressure_hpa, cpu_temp_c, raw_temp_c, target_c, fan_on)
        VALUES
        (%(device_id)s, %(ts)s, %(temperature_c)s, %(humidity_pct)s, %(pressure_hpa)s, %(cpu_temp_c)s, %(raw_temp_c)s, %(target_c)s, %(fan_on)s)
        """,
        row
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "saved"})

@app.route("/api/push", methods=["POST"])
def push():
    ok, resp = require_api_key()
    if not ok:
        return resp

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        return save_payload(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 兼容旧路径：/api/ingest
@app.route("/api/ingest", methods=["POST"])
def ingest():
    return push()

@app.route("/api/latest")
def latest():
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 1;")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"status": "empty", "message": "No readings yet"})
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/readings")
def readings():
    limit = request.args.get("limit", "50")
    try:
        limit_n = max(1, min(500, int(limit)))
    except:
        limit_n = 50

    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT %s;", (limit_n,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"count": len(rows), "items": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 重要：Render/gunicorn 启动时也要建表
try:
    if os.environ.get("DATABASE_URL", "").strip():
        init_db()
except Exception as e:
    print(f"[WARN] init_db skipped/failed: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
