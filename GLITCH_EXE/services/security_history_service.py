from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class SecurityHistoryService:
    """
    Persistent SQLite history for GLITCH.EXE Phase 3.
    """

    def __init__(
        self,
        db_path=None
    ):

        if db_path is None:

            base_dir = (
                Path(
                    __file__
                )
                .resolve()
                .parent
                .parent
            )

            data_dir = (
                base_dir
                / "data"
            )

            data_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            db_path = (
                data_dir
                / "security_history.db"
            )

        self.db_path = Path(
            db_path
        )

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self._initialize()

        self._ensure_columns()

    def _connect(
        self
    ):

        connection = sqlite3.connect(
            str(
                self.db_path
            ),
            timeout=5
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        connection.execute(
            "PRAGMA synchronous=NORMAL"
        )

        return connection

    def _initialize(
        self
    ):

        with self._connect() as connection:

            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_key TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT,
                    process_name TEXT,
                    process_path TEXT,
                    risk_score INTEGER NOT NULL DEFAULT 0,
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS active_findings (
                    finding_key TEXT PRIMARY KEY,
                    finding_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    process_name TEXT,
                    process_path TEXT,
                    risk_score INTEGER NOT NULL DEFAULT 0,
                    reasons_json TEXT NOT NULL DEFAULT '[]',
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    resolution_note TEXT,
                    resolved_at REAL
                );

                CREATE TABLE IF NOT EXISTS process_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_at REAL NOT NULL,
                    pid INTEGER,
                    process_name TEXT,
                    process_path TEXT,
                    connections INTEGER NOT NULL DEFAULT 0,
                    external_connections INTEGER NOT NULL DEFAULT 0,
                    listening_sockets INTEGER NOT NULL DEFAULT 0,
                    risk_level TEXT NOT NULL DEFAULT 'NORMAL',
                    risk_score INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_key TEXT NOT NULL UNIQUE,
                    observed_at REAL NOT NULL,
                    target TEXT,
                    file_name TEXT,
                    path TEXT,
                    risk_level TEXT,
                    risk_score INTEGER NOT NULL DEFAULT 0,
                    suspicious INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def _ensure_columns(
        self
    ):
        """
        Safe schema migration for databases created
        before PID support was added.
        """

        with self._connect() as connection:

            columns = {
                row[
                    "name"
                ]
                for row
                in connection.execute(
                    (
                        "PRAGMA "
                        "table_info(active_findings)"
                    )
                ).fetchall()
            }

            if "pid" not in columns:

                connection.execute(
                    (
                        "ALTER TABLE active_findings "
                        "ADD COLUMN pid INTEGER"
                    )
                )

    @staticmethod
    def _text(
        value
    ):

        return str(
            value
            or ""
        ).strip()

    def _finding_key(
        self,
        item
    ):

        name = self._text(
            item.get(
                "name"
            )
        ).lower()

        path = self._text(
            item.get(
                "exe"
            )
        ).lower()

        reasons = [
            self._text(
                reason
            ).lower()
            for reason
            in (
                item.get(
                    "risk_reasons"
                )
                or []
            )
        ]

        return "|".join(
            [
                "PROCESS",
                name,
                path,
                ",".join(
                    sorted(
                        reasons
                    )
                ),
            ]
        )

    def record_process_snapshot(
        self,
        processes
    ):

        now = time.time()

        rows = []

        for item in processes:

            rows.append(
                (
                    now,

                    item.get(
                        "pid"
                    ),

                    self._text(
                        item.get(
                            "name"
                        )
                    ),

                    self._text(
                        item.get(
                            "exe"
                        )
                    ),

                    int(
                        item.get(
                            "connections",
                            0
                        )
                        or 0
                    ),

                    int(
                        item.get(
                            "external",
                            0
                        )
                        or 0
                    ),

                    int(
                        item.get(
                            "listening",
                            0
                        )
                        or 0
                    ),

                    self._text(
                        item.get(
                            "risk_level",
                            "NORMAL"
                        )
                    ).upper(),

                    int(
                        item.get(
                            "risk_score",
                            0
                        )
                        or 0
                    ),
                )
            )

        if not rows:
            return

        with self._connect() as connection:

            connection.executemany(
                """
                INSERT INTO process_observations (
                    observed_at,
                    pid,
                    process_name,
                    process_path,
                    connections,
                    external_connections,
                    listening_sockets,
                    risk_level,
                    risk_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )

            # Keep database size under control.

            connection.execute(
                """
                DELETE FROM process_observations
                WHERE id NOT IN (
                    SELECT id
                    FROM process_observations
                    ORDER BY observed_at DESC
                    LIMIT 5000
                )
                """
            )

    def record_anomaly_findings(
        self,
        findings
    ):

        now = time.time()

        with self._connect() as connection:

            for item in findings:

                key = self._finding_key(
                    item
                )

                severity = self._text(
                    item.get(
                        "risk_level",
                        "REVIEW"
                    )
                ).upper()

                process_name = self._text(
                    item.get(
                        "name"
                    )
                )

                process_path = self._text(
                    item.get(
                        "exe"
                    )
                )

                score = int(
                    item.get(
                        "risk_score",
                        0
                    )
                    or 0
                )

                reasons = list(
                    item.get(
                        "risk_reasons"
                    )
                    or []
                )

                existing = connection.execute(
                    """
                    SELECT first_seen
                    FROM active_findings
                    WHERE finding_key = ?
                    """,
                    (
                        key,
                    )
                ).fetchone()

                first_seen = (
                    float(
                        existing[
                            "first_seen"
                        ]
                    )
                    if existing
                    else now
                )

                connection.execute(
                    """
                    INSERT INTO active_findings (
                        finding_key,
                        finding_type,
                        severity,
                        process_name,
                        process_path,
                        pid,
                        risk_score,
                        reasons_json,
                        first_seen,
                        last_seen,
                        status
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, 'ACTIVE'
                    )

                    ON CONFLICT(finding_key)

                    DO UPDATE SET
                        severity =
                            excluded.severity,

                        process_name =
                            excluded.process_name,

                        process_path =
                            excluded.process_path,

                        pid =
                            excluded.pid,

                        risk_score =
                            excluded.risk_score,

                        reasons_json =
                            excluded.reasons_json,

                        last_seen =
                            excluded.last_seen,

                        status =
                            'ACTIVE',

                        resolution_note =
                            NULL,

                        resolved_at =
                            NULL
                    """,
                    (
                        key,

                        "PROCESS_ANOMALY",

                        severity,

                        process_name,

                        process_path,

                        item.get(
                            "pid"
                        ),

                        score,

                        json.dumps(
                            reasons
                        ),

                        first_seen,

                        now,
                    )
                )

                # Only create the original anomaly event
                # once.

                if not existing:

                    connection.execute(
                        """
                        INSERT INTO security_events (
                            event_key,
                            event_type,
                            severity,
                            title,
                            details,
                            process_name,
                            process_path,
                            risk_score,
                            first_seen,
                            last_seen
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?
                        )
                        """,
                        (
                            key,

                            "PROCESS_ANOMALY",

                            severity,

                            (
                                f"{severity} "
                                "process anomaly"
                            ),

                            " | ".join(
                                reasons
                            ),

                            process_name,

                            process_path,

                            score,

                            now,

                            now,
                        )
                    )

    def get_active_findings(
        self,
        limit=20
    ):

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    finding_key,
                    finding_type,
                    severity,
                    process_name,
                    process_path,
                    pid,
                    risk_score,
                    reasons_json,
                    first_seen,
                    last_seen,
                    status

                FROM active_findings

                WHERE status = 'ACTIVE'

                ORDER BY
                    risk_score DESC,
                    last_seen DESC

                LIMIT ?
                """,
                (
                    int(
                        limit
                    ),
                )
            ).fetchall()

        output = []

        for row in rows:

            item = dict(
                row
            )

            try:

                item[
                    "reasons"
                ] = json.loads(
                    item.pop(
                        "reasons_json"
                    )
                    or "[]"
                )

            except Exception:

                item[
                    "reasons"
                ] = []

            output.append(
                item
            )

        return output

    def active_count(
        self
    ):

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM active_findings
                WHERE status = 'ACTIVE'
                """
            ).fetchone()

        return int(
            row[
                "count"
            ]
            if row
            else 0
        )

    def resolve_finding(
        self,
        finding_key,
        note=""
    ):

        now = time.time()

        with self._connect() as connection:

            connection.execute(
                """
                UPDATE active_findings

                SET
                    status = 'RESOLVED',
                    resolution_note = ?,
                    resolved_at = ?

                WHERE finding_key = ?
                """,
                (
                    self._text(
                        note
                    ),
                    now,
                    finding_key,
                )
            )

            changed = (
                connection.total_changes
                > 0
            )

        return bool(
            changed
        )

    def record_control_event(
        self,
        action,
        finding,
        success,
        details=""
    ):

        now = time.time()

        severity = self._text(
            finding.get(
                "severity",
                "INFO"
            )
        ).upper()

        process_name = self._text(
            finding.get(
                "process_name"
            )
        )

        process_path = self._text(
            finding.get(
                "process_path"
            )
        )

        score = int(
            finding.get(
                "risk_score",
                0
            )
            or 0
        )

        event_key = (
            f"ACTION|{action}|"
            f"{process_name}|{now}"
        )

        title = (
            f"{action} "
            + (
                "SUCCEEDED"
                if success
                else "FAILED"
            )
        )

        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO security_events (
                    event_key,
                    event_type,
                    severity,
                    title,
                    details,
                    process_name,
                    process_path,
                    risk_score,
                    first_seen,
                    last_seen
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    event_key,

                    "SECURITY_ACTION",

                    severity,

                    title,

                    self._text(
                        details
                    ),

                    process_name,

                    process_path,

                    score,

                    now,

                    now,
                )
            )

    def recent_events(
        self,
        limit=25
    ):

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    event_type,
                    severity,
                    title,
                    details,
                    process_name,
                    process_path,
                    risk_score,
                    first_seen,
                    last_seen

                FROM security_events

                ORDER BY
                    last_seen DESC

                LIMIT ?
                """,
                (
                    int(
                        limit
                    ),
                )
            ).fetchall()

        return [
            dict(
                row
            )
            for row
            in rows
        ]

    def record_scan_results(
        self,
        target,
        results
    ):

        now = time.time()

        with self._connect() as connection:

            for result in results or []:

                path = self._text(
                    getattr(
                        result,
                        "path",
                        ""
                    )
                )

                file_name = self._text(
                    getattr(
                        result,
                        "file_name",
                        ""
                    )
                )

                risk_level = self._text(
                    getattr(
                        result,
                        "risk_level",
                        ""
                    )
                ).upper()

                score = int(
                    getattr(
                        result,
                        "risk_score",
                        0
                    )
                    or 0
                )

                suspicious = int(
                    bool(
                        getattr(
                            result,
                            "suspicious",
                            False
                        )
                    )
                )

                key = "|".join(
                    [
                        path.lower(),
                        risk_level,
                        str(
                            score
                        ),
                    ]
                )

                connection.execute(
                    """
                    INSERT OR IGNORE
                    INTO scan_history (
                        scan_key,
                        observed_at,
                        target,
                        file_name,
                        path,
                        risk_level,
                        risk_score,
                        suspicious
                    )
                    VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?
                    )
                    """,
                    (
                        key,

                        now,

                        self._text(
                            target
                        ),

                        file_name,

                        path,

                        risk_level,

                        score,

                        suspicious,
                    )
                )