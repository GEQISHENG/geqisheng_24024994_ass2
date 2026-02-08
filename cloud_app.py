import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template
import psycopg2
import psycopg2.extras


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
    API_TOKEN = os.environ.get("API_TOKEN", "").strip()

    if not DATABASE_URL:
        raise RuntimeError("Missing DATABASE_URL environment variable")

    def get_conn():
        return psycopg2.connect(DATABASE_URL, sslmode="require")

    def init_db():
        sql = """
        create table if not exists readings (
            id bigserial primary key,
            device_id text not null,
            ts timestamptz not null,
            temperature_c double precision not null,
            humidity_pct double precision not null,
            pressure_hpa double precision not null,
            cpu_temp_c double precision not null,
            raw_temp_c double precision not null,
            target_c double precision not null,
            fan_on boolean not null
        );

        create index if not exists readings_device_ts on readings(device_id, ts desc);
        """
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                conn.commit()
        finally:
            conn.close()

    init_db()

    def token_ok():
        if not API_TOKEN:
            return True
        token = request.headers.get("X-API-TOKEN", "").strip()
        return token == API_TOKEN

    @app.get("/")
    def home():
        device_id = request.args.get("device_id", "raspi-01").strip()

        conn = get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    select *
                    from readings
                    where device_id=%s
                    order by ts desc
                    limit 25
                    """,
                    (device_id,),
                )
                rows = cur.fetchall()

            latest = rows[0] if rows else None
            return render_template(
                "index.html",
                device_id=device_id,
                latest=latest,
                history=rows,
            )
        finally:
            conn.close()

    @app.get("/api/latest")
    def api_latest():
        device_id = request.args.get("device_id", "raspi-01").strip()

        conn = get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    select *
                    from readings
                    where device_id=%s
                    order by ts desc
                    limit 1
                    """,
                    (device_id,),
                )
                row = cur.fetchone()

            if not row:
                return jsonify({"ok": True, "data": None})

            return jsonify({"ok": True, "data": row})
        finally:
            conn.close()

    @app.get("/api/history")
    def api_history():
        device_id = request.args.get("device_id", "raspi-01").strip()
        limit = int(request.args.get("limit", "50"))

        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200

        conn = get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    select *
                    from readings
                    where device_id=%s
                    order by ts desc
                    limit %s
                    """,
                    (device_id, limit),
                )
                rows = cur.fetchall()

            return jsonify({"ok": True, "data": rows})
        finally:
            conn.close()

    @app.post("/api/push")
    def api_push():
        if not token_ok():
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"ok": False, "error": "missing json"}), 400

        device_id = str(payload.get("device_id", "raspi-01")).strip()

        try:
            temperature_c = float(payload["temperature_c"])
            humidity_pct = float(payload["humidity_pct"])
            pressure_hpa = float(payload["pressure_hpa"])
            cpu_temp_c = float(payload.get("cpu_temp_c", 0.0))
            raw_temp_c = float(payload.get("raw_temp_c", temperature_c))
            target_c = float(payload.get("target_c", 25.0))
            fan_on = bool(payload.get("fan_on", False))
        except Exception:
            return jsonify({"ok": False, "error": "invalid fields"}), 400

        ts = datetime.now(timezone.utc)

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into readings
                    (device_id, ts, temperature_c, humidity_pct, pressure_hpa,
                     cpu_temp_c, raw_temp_c, target_c, fan_on)
                    values
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        device_id,
                        ts,
                        temperature_c,
                        humidity_pct,
                        pressure_hpa,
                        cpu_temp_c,
                        raw_temp_c,
                        target_c,
                        fan_on,
                    ),
                )
                conn.commit()
        finally:
            conn.close()

        return jsonify({"ok": True})

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
