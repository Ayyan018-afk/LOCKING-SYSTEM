"""Shared helpers for the SmartLock web app and the box API.
Both use the same SQLite file, so keep box_core.py, smartlock.py and box_api.py in one folder."""
import hmac, hashlib, os, secrets, sqlite3, time

DB = os.environ.get("SMARTLOCK_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "smartlock_v3.db"))
WINDOW = 30           # seconds; a box QR code is valid for the current and the previous window
UNLOCK_SECONDS = 8    # how long the lock stays open after a successful scan
DEVICE_KEY = os.environ.get("SMARTLOCK_DEVICE_KEY", "demo-device-key")


def _con():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def ensure_schema():
    con = _con()
    try:
        con.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
        cols = [r["name"] for r in con.execute("PRAGMA table_info(boxes)")]
        for c in (("unlock_until", "last_seen") if cols else ()):
            if c not in cols:
                con.execute(f"ALTER TABLE boxes ADD COLUMN {c} REAL DEFAULT 0")
        con.commit()
    finally:
        con.close()


def get_setting(key, default=None):
    con = _con()
    try:
        r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default
    except sqlite3.OperationalError:
        return default
    finally:
        con.close()


def set_setting(key, value):
    ensure_schema()
    con = _con()
    try:
        con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
        con.commit()
    finally:
        con.close()


def _secret():
    s = get_setting("box_secret")
    if not s:
        ensure_schema()
        con = _con()
        try:
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('box_secret',?)", (secrets.token_hex(16),))
            con.commit()
        finally:
            con.close()
        s = get_setting("box_secret")
    return s


def base_url():
    return get_setting("base_url", os.environ.get("SMARTLOCK_URL", "http://localhost:8501/portal")).rstrip("/")


def code_for(box_id, t=None):
    w = int((t or time.time()) // WINDOW)
    return hmac.new(_secret().encode(), f"{box_id}:{w}".encode(), hashlib.sha256).hexdigest()[:8].upper()


def valid_code(box_id, code):
    now = time.time()
    return any(hmac.compare_digest(str(code).upper(), code_for(box_id, now - k * WINDOW)) for k in (0, 1))


def request_unlock(box_id):
    con = _con()
    try:
        con.execute("UPDATE boxes SET unlock_until=? WHERE id=?", (time.time() + 15, box_id))
        con.commit()
    finally:
        con.close()


def consume_unlock(box_id):
    """True exactly once per pending unlock request (used by the box device)."""
    con = _con()
    try:
        cur = con.execute("UPDATE boxes SET unlock_until=0 WHERE id=? AND unlock_until>?", (box_id, time.time()))
        con.commit()
        return cur.rowcount == 1
    finally:
        con.close()


def touch(box_id):
    con = _con()
    try:
        con.execute("UPDATE boxes SET last_seen=? WHERE id=?", (time.time(), box_id))
        con.commit()
    finally:
        con.close()


def oled_view(box_id):
    """What the box screen should show right now (None if the box does not exist)."""
    con = _con()
    try:
        b = con.execute("SELECT * FROM boxes WHERE id=?", (box_id,)).fetchone()
        o = con.execute("SELECT status FROM orders WHERE box_id=? AND status IN ('Out for delivery','In box') ORDER BY id LIMIT 1",
                        (box_id,)).fetchone() if b else None
    finally:
        con.close()
    if not b:
        return None
    if b["status"] == "blocked":
        return {"mode": "text", "text": "OUT OF SERVICE"}
    if o:
        code = code_for(box_id)
        drop = o["status"] == "Out for delivery"
        return {"mode": "qr", "action": "DROP" if drop else "PICK", "text": "RIDER: SCAN TO DROP" if drop else "SCAN TO COLLECT",
                "payload": f"{base_url()}?box={box_id}&c={code}", "code": code, "expires_in": WINDOW - int(time.time()) % WINDOW}
    return {"mode": "text", "text": {"free": "AVAILABLE", "reserved": "RESERVED", "occupied": "IN USE"}.get(b["status"], b["status"].upper())}
