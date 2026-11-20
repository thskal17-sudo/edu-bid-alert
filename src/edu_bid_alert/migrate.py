"""울산 강사 공고 수집기(ulsan-shcool-public-company)의 DB 에서 수주 알리미 기록만 옮겨 온다.

수주 알리미는 2026-11 까지 울산 저장소 state 브랜치의 postings.db 안 camp_bids·camp_runs 표에 기록했다.
이 저장소의 첫 실행 때 그 두 표만 새 DB(data/bids.db)로 옮겨, 이미 메일로 알린 공고를 다시 보내지 않게 한다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .camp import CampStore

TABLES = ("camp_bids", "camp_runs")


def import_old(old_db: Path | str, new_db: Path | str) -> dict[str, int]:
    """old_db 의 camp_bids·camp_runs 를 new_db 로 복사한다 (이미 있는 공고번호는 그대로 둠). 표별 옮긴 건수."""
    CampStore(new_db).close()  # 새 DB 에 표(최신 칸 포함)를 만든다
    conn = sqlite3.connect(new_db)
    try:
        conn.execute("ATTACH DATABASE ? AS old", (str(old_db),))
        old_tables = {r[0] for r in conn.execute("SELECT name FROM old.sqlite_master WHERE type = 'table'")}
        moved: dict[str, int] = {}
        for table in TABLES:
            if table not in old_tables:
                moved[table] = 0
                continue
            new_cols = [r[1] for r in conn.execute(f"PRAGMA main.table_info({table})")]
            old_cols = {r[1] for r in conn.execute(f"PRAGMA old.table_info({table})")}
            cols = ", ".join(c for c in new_cols if c in old_cols)
            verb = "INSERT OR IGNORE" if table == "camp_bids" else "INSERT"
            before = conn.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()[0]
            conn.execute(f"{verb} INTO main.{table} ({cols}) SELECT {cols} FROM old.{table}")
            moved[table] = conn.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()[0] - before
        conn.commit()
        conn.execute("DETACH DATABASE old")
        return moved
    finally:
        conn.close()
