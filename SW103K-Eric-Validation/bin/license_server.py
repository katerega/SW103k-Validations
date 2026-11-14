#!/usr/bin/env python3

import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("NSR_LICENSE_HOST", "127.0.0.1")
PORT = int(os.environ.get("NSR_LICENSE_PORT", "18080"))
DB_FILE = os.environ.get("NSR_LICENSE_DB", "licenses.db")

FREE_TRIAL_DAYS = 5
DEFAULT_MAX_DEVICES = 3


# ============================================================
# DATABASE
# ============================================================

db_lock = threading.Lock()


def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = db()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                customer_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                license_key TEXT NOT NULL UNIQUE,

                status TEXT NOT NULL,

                issued_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,

                max_devices INTEGER NOT NULL DEFAULT 3,

                bandwidth_reduction INTEGER NOT NULL DEFAULT 1,
                storage_reduction INTEGER NOT NULL DEFAULT 1,

                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_customer
            ON licenses(customer_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_device
            ON licenses(customer_id, device_id)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                event_time INTEGER NOT NULL,

                event TEXT NOT NULL,

                customer_id TEXT,
                device_id TEXT,
                license_key TEXT,

                details TEXT
            )
        """)

        conn.commit()
        conn.close()


def now_ts():
    return int(datetime.now(timezone.utc).timestamp())


def iso_time(ts):
    if not ts:
        return None

    return datetime.fromtimestamp(
        ts,
        timezone.utc
    ).isoformat()


def generate_license_key():
    return "NSR-" + secrets.token_hex(16).upper()


def audit(
    event,
    customer_id=None,
    device_id=None,
    license_key=None,
    details=None
):
    with db_lock:
        conn = db()

        conn.execute("""
            INSERT INTO audit_log
            (
                event_time,
                event,
                customer_id,
                device_id,
                license_key,
                details
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            now_ts(),
            event,
            customer_id,
            device_id,
            license_key,
            details
        ))

        conn.commit()
        conn.close()


# ============================================================
# LICENSE HELPERS
# ============================================================

def count_devices(customer_id):
    conn = db()

    row = conn.execute("""
        SELECT COUNT(DISTINCT device_id) AS count
        FROM licenses
        WHERE customer_id = ?
          AND status IN ('free', 'paid')
    """, (customer_id,)).fetchone()

    conn.close()

    return int(row["count"])


def find_customer_device(customer_id, device_id):
    conn = db()

    row = conn.execute("""
        SELECT *
        FROM licenses
        WHERE customer_id = ?
          AND device_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (
        customer_id,
        device_id
    )).fetchone()

    conn.close()

    return row


def find_license_key(license_key):
    conn = db()

    row = conn.execute("""
        SELECT *
        FROM licenses
        WHERE license_key = ?
        LIMIT 1
    """, (license_key,)).fetchone()

    conn.close()

    return row


def create_free_license(customer_id, device_id):
    current = now_ts()
    expires = current + FREE_TRIAL_DAYS * 86400
    key = generate_license_key()

    with db_lock:
        conn = db()

        conn.execute("""
            INSERT INTO licenses
            (
                customer_id,
                device_id,
                license_key,
                status,
                issued_at,
                expires_at,
                max_devices,
                bandwidth_reduction,
                storage_reduction,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'free', ?, ?, ?, 1, 1, ?, ?)
        """, (
            customer_id,
            device_id,
            key,
            current,
            expires,
            DEFAULT_MAX_DEVICES,
            current,
            current
        ))

        conn.commit()
        conn.close()

    audit(
        "FREE_LICENSE_CREATED",
        customer_id,
        device_id,
        key,
        f"expires={iso_time(expires)}"
    )

    return find_license_key(key)


def response_from_row(row, message):
    current = now_ts()

    status = row["status"]

    # Server-side expiry enforcement.
    if status in ("free", "paid") and current >= row["expires_at"]:
        status = "expired"

        with db_lock:
            conn = db()

            conn.execute("""
                UPDATE licenses
                SET status = 'expired',
                    updated_at = ?
                WHERE id = ?
            """, (
                current,
                row["id"]
            ))

            conn.commit()
            conn.close()

        audit(
            "LICENSE_EXPIRED",
            row["customer_id"],
            row["device_id"],
            row["license_key"]
        )

    active = status in ("free", "paid")

    return {
        "status": status,
        "customer_id": row["customer_id"],
        "device_id": row["device_id"],
        "license_key": row["license_key"],
        "issued_at": row["issued_at"],
        "expires_at": row["expires_at"],
        "max_devices": row["max_devices"],
        "bandwidth_reduction": row["bandwidth_reduction"] if active else 0,
        "storage_reduction": row["storage_reduction"] if active else 0,
        "server_validated": 1,
        "message": message
    }


# ============================================================
# API
# ============================================================

def process_license_request(data):

    operation = str(
        data.get("operation", "activate")
    ).lower()

    customer_id = str(
        data.get("customer_id", "")
    ).strip()

    device_id = str(
        data.get("device_id", "")
    ).strip()

    license_key = str(
        data.get("license_key", "")
    ).strip()

    if not customer_id:
        return {
            "status": "revoked",
            "server_validated": 1,
            "message": "customer_id is required"
        }

    if not device_id:
        return {
            "status": "revoked",
            "server_validated": 1,
            "message": "device_id is required"
        }

    # --------------------------------------------------------
    # VALIDATE EXISTING LICENSE KEY
    # --------------------------------------------------------

    if license_key:

        row = find_license_key(license_key)

        if not row:
            audit(
                "INVALID_LICENSE_KEY",
                customer_id,
                device_id,
                license_key
            )

            return {
                "status": "revoked",
                "server_validated": 1,
                "message": "Invalid license key"
            }

        if row["customer_id"] != customer_id:
            audit(
                "CUSTOMER_MISMATCH",
                customer_id,
                device_id,
                license_key
            )

            return {
                "status": "revoked",
                "server_validated": 1,
                "message": "License belongs to another customer"
            }

        if row["device_id"] != device_id:
            audit(
                "DEVICE_MISMATCH",
                customer_id,
                device_id,
                license_key
            )

            return {
                "status": "revoked",
                "server_validated": 1,
                "message": "License is bound to another device"
            }

        result = response_from_row(
            row,
            "License validated successfully"
        )

        audit(
            "LICENSE_VALIDATED",
            customer_id,
            device_id,
            license_key,
            f"operation={operation}"
        )

        return result

    # --------------------------------------------------------
    # EXISTING CUSTOMER + DEVICE
    # --------------------------------------------------------

    existing = find_customer_device(
        customer_id,
        device_id
    )

    if existing:

        result = response_from_row(
            existing,
            "Existing license validated"
        )

        audit(
            "LICENSE_REVALIDATED",
            customer_id,
            device_id,
            existing["license_key"],
            f"operation={operation}"
        )

        return result

    # --------------------------------------------------------
    # FIRST-TIME CUSTOMER
    # --------------------------------------------------------

    devices = count_devices(customer_id)

    if devices >= DEFAULT_MAX_DEVICES:

        audit(
            "DEVICE_LIMIT_REACHED",
            customer_id,
            device_id
        )

        return {
            "status": "revoked",
            "server_validated": 1,
            "message": "Maximum number of devices reached"
        }

    row = create_free_license(
        customer_id,
        device_id
    )

    return response_from_row(
        row,
        f"FREE {FREE_TRIAL_DAYS}-day license activated"
    )


# ============================================================
# HTTP SERVER
# ============================================================

class LicenseHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(
            "[HTTP]",
            format % args
        )

    def send_json(self, status_code, payload):

        body = json.dumps(
            payload,
            separators=(",", ":")
        ).encode("utf-8")

        self.send_response(status_code)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.end_headers()

        self.wfile.write(body)

    def do_POST(self):

        if self.path != "/api/v1/license":

            self.send_json(
                404,
                {
                    "status": "revoked",
                    "server_validated": 1,
                    "message": "Not found"
                }
            )

            return

        try:

            content_length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

            if content_length <= 0 or content_length > 1024 * 1024:

                self.send_json(
                    400,
                    {
                        "status": "revoked",
                        "server_validated": 1,
                        "message": "Invalid request size"
                    }
                )

                return

            raw = self.rfile.read(
                content_length
            )

            data = json.loads(
                raw.decode("utf-8")
            )

            result = process_license_request(
                data
            )

            self.send_json(
                200,
                result
            )

        except Exception as e:

            print(
                "[ERROR]",
                repr(e)
            )

            self.send_json(
                500,
                {
                    "status": "revoked",
                    "server_validated": 1,
                    "message": "License server error"
                }
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    init_db()

    print("=" * 60)
    print("NSR SW103K LICENSE SERVER")
    print("=" * 60)
    print(f"Database : {DB_FILE}")
    print(f"Address  : http://{HOST}:{PORT}")
    print(f"Endpoint : http://{HOST}:{PORT}/api/v1/license")
    print(f"Trial    : {FREE_TRIAL_DAYS} days")
    print(f"Devices  : {DEFAULT_MAX_DEVICES}")
    print("=" * 60)

    server = ThreadingHTTPServer(
        (HOST, PORT),
        LicenseHandler
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:

        print("\nStopping license server...")

        server.shutdown()
