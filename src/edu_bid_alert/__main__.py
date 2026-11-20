"""명령줄 실행.

    python -m edu_bid_alert camp [--no-mail] [--days N] [--recheck]  # 나라장터(G2B_API_KEY) + S2B + 기관 입찰 → 메일
    python -m edu_bid_alert send-test-mail                           # 메일 설정 확인
    python -m edu_bid_alert import-old OLD.db [--db data/bids.db]     # 울산 저장소 DB 에서 기록 옮기기 (첫 실행)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG_DIR
from .models import now_kst


def cmd_camp(args) -> int:
    from .camp import G2BError, run_camp

    try:
        out = run_camp(
            db_path=Path(args.db),
            send_mail=not args.no_mail,
            config_dir=Path(args.config),
            lookback_days=args.days,
            recheck=args.recheck,
        )
    except G2BError as exc:
        print(f"캠프·교육 수주 공고: {exc}")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::error title=캠프·교육 수주 실패::{exc}")
        return 1
    print(f"\n=== 캠프·교육 수주 공고 {out.now:%Y-%m-%d %H:%M} ===")
    print(f"나라장터 용역 공고 {out.scanned}건 · 키워드 일치 {out.matched}건 · API 호출 {out.calls}회")
    print(f"S2B 학교 용역 견적 {out.s2b_scanned}건 · 키워드 일치 {out.s2b_matched}건 · 요청 {out.s2b_calls}회")
    if out.agency_calls:
        print(f"기관 입찰 게시판 글 {out.agency_scanned}건 · 키워드 일치 {out.agency_matched}건 · 요청 {out.agency_calls}회")
    print(f"새 공고 {len(out.new)}건")
    for err in out.errors:
        print(f"  ⚠ 읽지 못함: {err}")
    if out.methods:
        print("키워드 공고의 계약방법: " + ", ".join(f"{k} {v}" for k, v in sorted(out.methods.items())))
    for b in out.new:
        close = f"{b.close_at:%m/%d %H:%M}" if b.close_at else "원문확인"
        price = f"{b.price:,}원({b.price_label})" if b.price else "-"
        tag = "[교육] " if b.topic == "교육" else ""
        print(f"  [{b.tier}] ~{close} | {b.source} | {b.demand_org or b.org} | {tag}{b.title}")
        print(f"          {b.method or '-'} | {price} | 참가지역 {b.region_text} | {b.url}")
    if out.closing_soon:
        print(f"마감임박 {len(out.closing_soon)}건")
    if out.region_errors:
        print(f"참가가능지역 조회 실패 {out.region_errors}건 ('검토'로 분류)")
    if out.mailed:
        print("메일: 발송함")
    elif args.no_mail:
        print("메일: 발송 안 함 (--no-mail)")
    else:
        print("메일: 새 공고가 없어 보내지 않음")
    if os.environ.get("GITHUB_ACTIONS") == "true":  # 실행 기록 첫 화면(요약)에 결과를 남긴다
        counts = {t: sum(1 for b in out.new if b.tier == t) for t in ("바로지원", "검토", "참고")}
        mail = "발송함" if out.mailed else "안 보냄(--no-mail)" if args.no_mail else "새 공고 없음"
        summary = (f"나라장터 {out.scanned}건 중 {out.matched}건 · S2B {out.s2b_scanned}건 중 {out.s2b_matched}건 일치"
                   f" · 기관 {out.agency_scanned}건 중 {out.agency_matched}건"
                   f" · 새 공고 {len(out.new)}건 (바로지원 {counts['바로지원']} · 검토 {counts['검토']}"
                   f" · 참고 {counts['참고']}) · 메일 {mail}")
        print(f"::notice title=캠프·교육 수주 결과::{summary}")
        lines = [f"[{b.tier}] {b.source} {b.demand_org or b.org} | {'[교육] ' if b.topic == '교육' else ''}{b.title}"
                 f" | {b.region_text}" for b in out.new[:25]]
        if lines:
            print("::notice title=새 공고 (앞 25건)::" + "%0A".join(x.replace("%", "%25") for x in lines))
        for err in out.errors:
            print(f"::warning title=읽지 못한 곳::{err}")
    return 0


def cmd_send_test_mail(args) -> int:
    from .mailer import MailConfig, build_message, send

    cfg = MailConfig.from_env()
    now = now_kst()
    msg = build_message(
        cfg,
        "[교육 입찰 알리미] 메일 설정 확인",
        f"<p>메일 설정이 정상입니다. ({now:%Y-%m-%d %H:%M} KST)</p>",
        f"메일 설정이 정상입니다. ({now:%Y-%m-%d %H:%M} KST)",
        None,
    )
    send(cfg, msg)
    print(f"테스트 메일 발송: {', '.join(cfg.to)}")
    return 0


def cmd_import_old(args) -> int:
    from .migrate import import_old

    moved = import_old(Path(args.old), Path(args.db))
    print("울산 저장소 기록 옮김: " + ", ".join(f"{t} {n}건" for t, n in moved.items()))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edu_bid_alert", description="캠프·교육 운영 입찰공고 수집 → 메일")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_DIR), help="설정 폴더 (camp.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_camp = sub.add_parser("camp", help="캠프·교육 수주 공고 수집(나라장터·S2B·기관 입찰) → 메일")
    p_camp.add_argument("--db", default="data/bids.db")
    p_camp.add_argument("--no-mail", action="store_true", help="메일을 보내지 않음 (새 공고 표시도 유지)")
    p_camp.add_argument("--days", type=int, default=None, help="최근 며칠치 공고를 볼지 (기본: config/camp.yaml)")
    p_camp.add_argument("--recheck", action="store_true", help="아직 안 알린 공고의 참가가능지역을 다시 조회")
    p_camp.set_defaults(func=cmd_camp)

    p_mail = sub.add_parser("send-test-mail", help="메일 설정 확인")
    p_mail.set_defaults(func=cmd_send_test_mail)

    p_import = sub.add_parser("import-old", help="울산 저장소 DB(postings.db)에서 camp_bids·camp_runs 옮기기")
    p_import.add_argument("old")
    p_import.add_argument("--db", default="data/bids.db")
    p_import.set_defaults(func=cmd_import_old)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    from . import logsafe

    logsafe.install()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
