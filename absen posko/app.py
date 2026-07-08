import os
import random
import string
from datetime import date, datetime

import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-key")

DB_CONFIG = {
    "host": os.getenv("MYSQLHOST"),
    "port": int(os.getenv("MYSQLPORT")),
    "user": os.getenv("MYSQLUSER"),
    "password": os.getenv("MYSQLPASSWORD"),
    "database": os.getenv("MYSQLDATABASE"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


def get_db():
    if "db" not in g:
        g.db = pymysql.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def make_token(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def today_str():
    return date.today().isoformat()


def now_time_str():
    return datetime.now().strftime("%H:%M:%S")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scan")
def scan_page():
    return render_template("scan.html")


@app.route("/api/members", methods=["GET"])
def list_members():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT name FROM members ORDER BY name ASC")
        rows = cur.fetchall()
    return jsonify([r["name"] for r in rows])


@app.route("/api/members", methods=["POST"])
def add_member():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Nama tidak boleh kosong"}), 400
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT IGNORE INTO members (name) VALUES (%s)", (name,)
        )
    return jsonify({"ok": True, "name": name})


@app.route("/api/members/<name>", methods=["DELETE"])
def delete_member(name):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM members WHERE name = %s", (name,))
    return jsonify({"ok": True})


@app.route("/api/settings", methods=["GET"])
def get_settings():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT cutoff_time FROM settings WHERE id = 1")
        row = cur.fetchone()
    cutoff = str(row["cutoff_time"]) if row else "07:00:00"
    return jsonify({"cutoff_time": cutoff[:5]})


@app.route("/api/settings", methods=["PUT"])
def update_settings():
    body = request.get_json(force=True)
    cutoff = body.get("cutoff_time", "07:00")
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE settings SET cutoff_time = %s WHERE id = 1", (cutoff,)
        )
    return jsonify({"ok": True})


@app.route("/api/session/today", methods=["GET"])
def session_today():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT session_date, token, is_open FROM sessions WHERE session_date = %s",
            (today_str(),),
        )
        row = cur.fetchone()
    if not row:
        return jsonify(None)
    return jsonify(
        {
            "date": row["session_date"].isoformat(),
            "token": row["token"],
            "open": bool(row["is_open"]),
        }
    )


@app.route("/api/session/new", methods=["POST"])
def session_new():
    token = make_token()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sessions (session_date, token, is_open)
            VALUES (%s, %s, TRUE)
            ON DUPLICATE KEY UPDATE token = VALUES(token), is_open = TRUE
            """,
            (today_str(), token),
        )
    return jsonify({"date": today_str(), "token": token, "open": True})


@app.route("/api/session/close", methods=["POST"])
def session_close():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE sessions SET is_open = FALSE WHERE session_date = %s",
            (today_str(),),
        )
    return jsonify({"ok": True})


def compute_status(cutoff_time):
    now = datetime.now().strftime("%H:%M:%S")
    return "tepat" if now <= cutoff_time else "telat"


@app.route("/api/checkin", methods=["POST"])
def checkin():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    token = body.get("token")
    session_date = body.get("session_date")
    photo = body.get("photo")
    if not name or not token or not session_date:
        return jsonify({"error": "Data tidak lengkap"}), 400

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT token, is_open FROM sessions WHERE session_date = %s",
            (session_date,),
        )
        sess = cur.fetchone()
        if not sess or sess["token"] != token:
            return jsonify({"error": "Kode QR tidak valid"}), 400
        if not sess["is_open"]:
            return jsonify({"error": "Sesi absensi sudah ditutup"}), 400
        if session_date != today_str():
            return jsonify({"error": "Kode QR sudah tidak berlaku"}), 400

        cur.execute(
            "SELECT time_in, status FROM attendance WHERE member_name = %s AND session_date = %s",
            (name, session_date),
        )
        existing = cur.fetchone()
        if existing:
            return jsonify(
                {
                    "already": True,
                    "time": str(existing["time_in"])[:5],
                    "status": existing["status"],
                }
            )

        cur.execute("SELECT cutoff_time FROM settings WHERE id = 1")
        cutoff = str(cur.fetchone()["cutoff_time"])
        status = compute_status(cutoff)
        time_in = now_time_str()
        cur.execute(
            """
            INSERT INTO attendance (member_name, session_date, time_in, status, photo)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, session_date, time_in, status, photo),
        )
    return jsonify({"already": False, "time": time_in[:5], "status": status})


@app.route("/api/checkin/manual", methods=["POST"])
def checkin_manual():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Nama tidak boleh kosong"}), 400
    session_date = today_str()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT time_in, status FROM attendance WHERE member_name = %s AND session_date = %s",
            (name, session_date),
        )
        existing = cur.fetchone()
        if existing:
            return jsonify(
                {
                    "already": True,
                    "time": str(existing["time_in"])[:5],
                    "status": existing["status"],
                }
            )
        time_in = now_time_str()
        cur.execute(
            """
            INSERT INTO attendance (member_name, session_date, time_in, status)
            VALUES (%s, %s, %s, 'manual')
            """,
            (name, session_date, time_in),
        )
    return jsonify({"already": False, "time": time_in[:5], "status": "manual"})


@app.route("/api/attendance", methods=["GET"])
def attendance_by_date():
    qdate = request.args.get("date", today_str())
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT member_name AS name, time_in AS time, status, photo
            FROM attendance WHERE session_date = %s ORDER BY time_in ASC
            """,
            (qdate,),
        )
        rows = cur.fetchall()
    for r in rows:
        r["time"] = str(r["time"])[:5]
    return jsonify(rows)


@app.route("/api/dates", methods=["GET"])
def distinct_dates():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT session_date FROM attendance ORDER BY session_date DESC"
        )
        rows = cur.fetchall()
    return jsonify([r["session_date"].isoformat() for r in rows])


@app.route("/api/reset", methods=["DELETE"])
def reset_all():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM attendance")
        cur.execute("DELETE FROM sessions")
        cur.execute("DELETE FROM members")
        cur.execute("UPDATE settings SET cutoff_time = '07:00:00' WHERE id = 1")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
