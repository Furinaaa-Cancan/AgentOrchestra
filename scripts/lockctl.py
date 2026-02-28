#!/usr/bin/env python3
"""SQLite-based file lock manager for multi-agent collaboration."""

from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import time
from typing import Any


def connect(db_path: pathlib.Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS locks (
            file_path TEXT PRIMARY KEY,
            owner_task TEXT NOT NULL,
            lock_version INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            renewed_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def cleanup_expired(conn: sqlite3.Connection, now_ts: int) -> int:
    cur = conn.execute("DELETE FROM locks WHERE expires_at <= ?", (now_ts,))
    return cur.rowcount


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "file_path": row["file_path"],
        "owner_task": row["owner_task"],
        "lock_version": row["lock_version"],
        "created_at": row["created_at"],
        "renewed_at": row["renewed_at"],
        "expires_at": row["expires_at"],
    }


def command_acquire(args: argparse.Namespace) -> int:
    now_ts = int(time.time())
    expires_at = now_ts + args.ttl_sec

    with connect(pathlib.Path(args.db)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cleanup_expired(conn, now_ts)
        row = conn.execute("SELECT * FROM locks WHERE file_path = ?", (args.file_path,)).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO locks(file_path, owner_task, lock_version, created_at, renewed_at, expires_at)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (args.file_path, args.task_id, now_ts, now_ts, expires_at),
            )
            conn.commit()
            print(json.dumps({"status": "acquired", "lock_version": 1}, ensure_ascii=True))
            return 0

        if row["owner_task"] == args.task_id:
            next_version = int(row["lock_version"]) + 1
            conn.execute(
                """
                UPDATE locks
                SET lock_version = ?, renewed_at = ?, expires_at = ?
                WHERE file_path = ? AND owner_task = ?
                """,
                (next_version, now_ts, expires_at, args.file_path, args.task_id),
            )
            conn.commit()
            print(json.dumps({"status": "renewed_by_owner", "lock_version": next_version}, ensure_ascii=True))
            return 0

        conn.rollback()
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "holder": row["owner_task"],
                    "expires_at": row["expires_at"],
                },
                ensure_ascii=True,
            ),
            file=sys.stderr,
        )
        return 1


def command_renew(args: argparse.Namespace) -> int:
    now_ts = int(time.time())
    expires_at = now_ts + args.ttl_sec

    with connect(pathlib.Path(args.db)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cleanup_expired(conn, now_ts)
        row = conn.execute("SELECT * FROM locks WHERE file_path = ?", (args.file_path,)).fetchone()

        if row is None:
            conn.rollback()
            print("ERROR: lock not found", file=sys.stderr)
            return 1
        if row["owner_task"] != args.task_id:
            conn.rollback()
            print("ERROR: lock is owned by another task", file=sys.stderr)
            return 1

        next_version = int(row["lock_version"]) + 1
        conn.execute(
            """
            UPDATE locks
            SET lock_version = ?, renewed_at = ?, expires_at = ?
            WHERE file_path = ? AND owner_task = ?
            """,
            (next_version, now_ts, expires_at, args.file_path, args.task_id),
        )
        conn.commit()

    print(json.dumps({"status": "renewed", "lock_version": next_version}, ensure_ascii=True))
    return 0


def command_release(args: argparse.Namespace) -> int:
    now_ts = int(time.time())
    with connect(pathlib.Path(args.db)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cleanup_expired(conn, now_ts)
        row = conn.execute("SELECT * FROM locks WHERE file_path = ?", (args.file_path,)).fetchone()
        if row is None:
            conn.rollback()
            print(
                "ERROR: lock not found (already released, expired, or using a different DB path)",
                file=sys.stderr,
            )
            return 1
        if row["owner_task"] != args.task_id:
            conn.rollback()
            print(
                f"ERROR: lock is owned by '{row['owner_task']}', not '{args.task_id}'",
                file=sys.stderr,
            )
            return 1

        cur = conn.execute("DELETE FROM locks WHERE file_path = ? AND owner_task = ?", (args.file_path, args.task_id))
        conn.commit()
        if cur.rowcount == 0:
            print("ERROR: lock delete failed unexpectedly", file=sys.stderr)
            return 1

    print(json.dumps({"status": "released"}, ensure_ascii=True))
    return 0


def command_list(args: argparse.Namespace) -> int:
    now_ts = int(time.time())
    with connect(pathlib.Path(args.db)) as conn:
        cleanup_expired(conn, now_ts)
        rows = conn.execute("SELECT * FROM locks ORDER BY file_path ASC").fetchall()

    payload = [row_to_dict(row) for row in rows]
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SQLite lock manager for strict multi-agent editing")
    parser.add_argument("--db", default="runtime/locks.db", help="Path to sqlite DB")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("acquire", help="Acquire or renew lock for owner task")
    p.add_argument("--task-id", required=True, help="Task ID holding the lock")
    p.add_argument("--file-path", required=True, help="File path to lock")
    p.add_argument("--ttl-sec", type=int, default=120, help="Lock TTL seconds")
    p.set_defaults(func=command_acquire)

    p = sub.add_parser("renew", help="Renew lock held by same task")
    p.add_argument("--task-id", required=True, help="Task ID holding the lock")
    p.add_argument("--file-path", required=True, help="File path to lock")
    p.add_argument("--ttl-sec", type=int, default=120, help="Lock TTL seconds")
    p.set_defaults(func=command_renew)

    p = sub.add_parser("release", help="Release lock held by task")
    p.add_argument("--task-id", required=True, help="Task ID holding the lock")
    p.add_argument("--file-path", required=True, help="File path to unlock")
    p.set_defaults(func=command_release)

    p = sub.add_parser("list", help="List active locks")
    p.set_defaults(func=command_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "ttl_sec") and args.ttl_sec <= 0:
        print("ERROR: ttl-sec must be > 0", file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
