"""울산 저장소 DB 에서 수주 알리미 기록 옮기기."""
import sqlite3

from edu_bid_alert.__main__ import main
from edu_bid_alert.camp import CampStore
from edu_bid_alert.migrate import import_old


def old_db(path):
    """울산 postings.db 모양: 강사 공고 표 + 9월 모양 camp_bids(source·topic 칸 없음) + camp_runs."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE postings (id INTEGER PRIMARY KEY, title TEXT);
        INSERT INTO postings (title) VALUES ('울산 강사 공고');
        CREATE TABLE camp_bids (bid_no TEXT PRIMARY KEY, bid_ord TEXT, title TEXT NOT NULL, org TEXT,
            demand_org TEXT, posted_at TEXT, close_at TEXT, price INTEGER, price_label TEXT, method TEXT,
            regions TEXT, tier TEXT, notice_kind TEXT, url TEXT, first_seen_at TEXT NOT NULL, reported_at TEXT);
        INSERT INTO camp_bids (bid_no, title, tier, first_seen_at, reported_at)
            VALUES ('R1', '진로캠프 운영', '바로지원', '2026-11-01T02:23:00+09:00', '2026-11-01T02:30:00+09:00');
        INSERT INTO camp_bids (bid_no, title, tier, first_seen_at)
            VALUES ('S2B-9', '창업교육 운영', '검토', '2026-11-19T13:17:00+09:00');
        CREATE TABLE camp_runs (run_at TEXT NOT NULL, scanned INTEGER, matched INTEGER, new INTEGER,
            calls INTEGER, errors INTEGER, diag TEXT);
        INSERT INTO camp_runs VALUES ('2026-11-19T13:17:00+09:00', 10, 2, 1, 3, 0, '{}');
    """)
    conn.commit()
    conn.close()


def test_import_moves_only_bid_tables_and_keeps_reported(tmp_path):
    old = tmp_path / "postings.db"
    new = tmp_path / "bids.db"
    old_db(old)
    assert import_old(old, new) == {"camp_bids": 2, "camp_runs": 1}

    conn = sqlite3.connect(new)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"camp_bids", "camp_runs"}  # 강사 공고 표는 옮기지 않음
    rows = dict(conn.execute("SELECT bid_no, reported_at FROM camp_bids"))
    assert rows == {"R1": "2026-11-01T02:30:00+09:00", "S2B-9": None}
    conn.close()

    # 이미 알린 공고는 다시 메일 대상이 아니다
    store = CampStore(new)
    assert [b.bid_no for b in store.unreported()] == ["S2B-9"]
    store.close()


def test_import_twice_does_not_duplicate_bids(tmp_path):
    old = tmp_path / "postings.db"
    new = tmp_path / "bids.db"
    old_db(old)
    import_old(old, new)
    assert import_old(old, new)["camp_bids"] == 0


def test_import_from_db_without_bid_tables(tmp_path, capsys):
    old = tmp_path / "postings.db"
    sqlite3.connect(old).executescript("CREATE TABLE postings (id INTEGER);")
    assert main(["import-old", str(old), "--db", str(tmp_path / "bids.db")]) == 0
    assert "camp_bids 0건" in capsys.readouterr().out
