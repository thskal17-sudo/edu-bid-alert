"""수집 대상 사이트 진단 도구 (GitHub Actions '사이트 진단 (probe)' 에서 실행).

새 기관 게시판을 config/camp.yaml 에 넣기 전에, 해외(GitHub) 서버에서 접속되는지·robots.txt·목록 구조를 본다.

사용법:
    python scripts/probe.py --url URL ...                 # 게시판 파서를 돌려 몇 건을 어떻게 읽는지 + 메뉴 링크
    python scripts/probe.py --url-file scripts/probe_urls_agency.txt
    python scripts/probe.py --url URL --raw 3000 --raw-from 단어   # 본문 HTML 일부
    python scripts/probe.py --url URL --grep '입찰|용역' [--follow-js]
    python scripts/probe.py --agencies                    # 지금 설정으로 기관 입찰 시험 수집 (임시 DB, 메일 없음)
    --direct: 국내 중계(KR_PROXY_URL)를 쓰지 않고 바로 접속
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from edu_bid_alert.board import _pick_rows, parse_board  # noqa: E402
from edu_bid_alert.http import Http  # noqa: E402
from edu_bid_alert.models import today_kst  # noqa: E402

HTTP = Http(min_interval=0.5, retries=0, max_seconds=40)
RAW = 0
RAW_FROM = ""
GREP: re.Pattern | None = None
FOLLOW_JS = False
FORM_POST: tuple[str, dict[str, str]] | None = None  # (폼 셀렉터, 추가 값): GET 후 폼을 POST 한 응답을 본다


def clip(text: str | None, n: int = 120) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def fetch(url: str) -> requests.Response:
    print(f"  … {time.strftime('%H:%M:%S')} GET {url}", flush=True)
    try:
        return HTTP.get(url)
    except requests.HTTPError as exc:  # 진단 목적이라 4xx/5xx 응답도 그대로 보여준다
        return exc.response


def describe_anchor(a) -> str:
    parts = [f"text={clip(a.get_text(), 70)!r}"]
    if a.get("href"):
        parts.append(f"href={clip(a['href'], 160)!r}")
    if a.get("onclick"):
        parts.append(f"onclick={clip(a['onclick'], 160)!r}")
    for attr in ("data-id", "data-seq", "data-no", "data-idx", "target", "title"):
        if a.get(attr):
            parts.append(f"{attr}={clip(a[attr], 60)!r}")
    return " ".join(parts)


def js_defs(soup, code: str) -> list[str]:
    """onclick/href 의 javascript 호출에 쓰인 함수 정의를 찾아 돌려준다."""
    out = []
    scripts = "\n".join(sc.get_text() for sc in soup.find_all("script") if not sc.get("src"))
    for name in dict.fromkeys(re.findall(r"([A-Za-z_$][\w$]*)\s*\(", code or "")):
        m = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", scripts)
        if m:
            out.append(clip(scripts[m.start(): m.start() + 500], 500))
    return out


BOARD_LINK = re.compile(r"공지|채용|모집|강사|알림|소식|notice|board|bbs|Board|Bbs", re.I)


def grep_report(label: str, text: str, limit: int = 8) -> None:
    hits = list(GREP.finditer(text))
    if hits:
        print(f"  grep {label}: {len(hits)} hits")
    for m in hits[:limit]:
        print(f"    … {clip(text[max(0, m.start() - 150): m.end() + 350], 500)}")


def parse_report(label: str, url: str) -> None:
    """게시판 파서를 그대로 돌려서 몇 건을 어떻게 읽는지만 짧게 보여준다."""
    print("-" * 100)
    print(f"PARSE {label}")
    try:
        r = fetch(url)
        if FORM_POST is not None:
            from urllib.parse import urljoin

            selector, extra = FORM_POST
            form = BeautifulSoup(r.content, "lxml").select_one(selector)
            fields = {i["name"]: i.get("value", "") for i in form.find_all("input", {"type": "hidden"}) if i.get("name")}
            data = {**fields, **extra}
            action = urljoin(r.url, form.get("action") or "") or r.url
            print(f"  POST {action} data={data} cookies={list(HTTP.session.cookies.keys())}")
            r = HTTP.post(action, data=data)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR {type(exc).__name__}: {clip(str(exc), 300)}")
        return
    print(f"  status={r.status_code} bytes={len(r.content)} final={r.url}")
    if len(r.content) < 1500:
        print(f"  body: {clip(r.content.decode('utf-8', 'replace'), 1500)}")
        return
    soup = BeautifulSoup(r.content, "lxml")
    print(f"  <title>: {clip(soup.title.get_text() if soup.title else '')}")
    rows = parse_board(r.content, r.url, {}, today_kst())
    _, headers = _pick_rows(soup, None)
    print(f"  rows={len(rows)} headers={headers[:10]}")
    for row in rows[:5]:
        print(
            f"    · {clip(row.title, 70)!r} posted={row.posted} deadline={row.deadline} "
            f"org={row.org!r} label={row.label!r} detail_ok={row.detail_ok}"
        )
        print(f"      url={clip(row.url, 220)} key={clip(row.key, 60)!r}")
    if rows and not rows[0].detail_ok:
        a = next((tr.find("a") for tr in _pick_rows(soup, None)[0] if tr.find("a")), None)
        if a is not None:
            print(f"    first anchor: {describe_anchor(a)}")
            for d in js_defs(soup, (a.get("onclick") or "") + (a.get("href") or "")):
                print(f"    js: {d}")
    for form in soup.find_all("form"):
        hidden = [i.get("name") for i in form.find_all("input", {"type": "hidden"})][:12]
        if form.get("action") or hidden:
            print(f"  form id={form.get('id')!r} action={clip(form.get('action'), 100)!r} method={form.get('method')!r} hidden={hidden}")
    pages = [describe_anchor(a) for a in soup.find_all("a") if re.fullmatch(r"\s*[23]\s*(페이지)?\s*", a.get_text() or "")]
    for p in pages[:2]:
        print(f"  page: {p}")
    if pages:
        a = next(a for a in soup.find_all("a") if re.fullmatch(r"\s*2\s*(페이지)?\s*", a.get_text() or ""))
        for d in js_defs(soup, (a.get("onclick") or "") + (a.get("href") or "")):
            print(f"  page js: {d}")
    if GREP is not None:
        grep_report("page", r.content.decode("utf-8", "replace"))
        if FOLLOW_JS:
            from urllib.parse import urljoin, urlsplit

            host = urlsplit(r.url).hostname
            for sc in soup.find_all("script", src=True):
                js_url = urljoin(r.url, sc["src"])
                if urlsplit(js_url).hostname != host:
                    continue
                try:
                    js = HTTP.get(js_url).content.decode("utf-8", "replace")
                except Exception as exc:  # noqa: BLE001
                    print(f"  js {js_url}: {type(exc).__name__}")
                    continue
                grep_report(js_url, js)
    if RAW:
        html = str(soup.body or soup)
        start = max(0, html.find(RAW_FROM) - 200) if RAW_FROM and RAW_FROM in html else 0
        print(f"  raw[{start}:]: {clip(html[start:], RAW)}")
        srcs = [sc.get("src") for sc in soup.find_all("script") if sc.get("src")]
        print(f"  script src: {srcs[:15]}")
    if not rows:
        seen = set()
        for a in soup.find_all("a", href=True):
            text = clip(a.get_text(), 40)
            if BOARD_LINK.search(text + a["href"]) and a["href"] not in seen and len(seen) < 25:
                seen.add(a["href"])
                print(f"  link: {describe_anchor(a)}")


def agencies_report() -> int:
    """기관 입찰 게시판 시험 수집: 임시 DB 에 처음 실행처럼 모아 등급별로 보여준다."""
    import json
    import tempfile

    from edu_bid_alert import agency
    from edu_bid_alert.camp import CampOutcome, CampStore, load_camp_config
    from edu_bid_alert.models import now_kst

    logging.basicConfig(level=logging.INFO, format="  [%(levelname)s] %(message)s")
    cfg = load_camp_config(ROOT / "config")
    now = now_kst()
    with tempfile.TemporaryDirectory() as tmp:
        store = CampStore(Path(tmp) / "t.db")
        out, diag = CampOutcome(now=now), {}
        agency.collect_agencies(store, cfg, now, None, out, diag)
        rows = store.conn.execute("SELECT * FROM camp_bids ORDER BY tier, close_at").fetchall()
        print(f"기관 게시판 글 {out.agency_scanned}건 · 키워드 일치 {out.agency_matched}건 · 저장 {len(rows)}건"
              f" · 요청 {out.agency_calls}회")
        for name, stat in diag.get("agencies", {}).items():
            print(f"  {name}: {json.dumps(stat, ensure_ascii=False)}")
        for err in out.errors:
            print(f"  ⚠ {err}")
        for r in rows:
            print(f"  [{r['tier']}] {r['source']} | {r['title']} | 마감 {r['close_at'] or '-'}"
                  f" | {r['price'] or '-'} {r['price_label'] or ''} | {r['method'] or '-'} | {r['topic']}")
            print(f"      {r['url']}")
        store.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="수집 대상 사이트 진단")
    parser.add_argument("--url", nargs="*", default=[], help="볼 주소")
    parser.add_argument("--url-file", default=None, help="URL 목록 파일 (한 줄에 하나, # 은 주석)")
    parser.add_argument("--raw", type=int, default=0, help="본문 HTML 을 이 글자 수만큼 출력")
    parser.add_argument("--raw-from", default="", help="--raw 출력을 이 글자가 처음 나오는 곳부터 시작")
    parser.add_argument("--grep", default=None, help="HTML 에 이 정규식이 나오는 곳을 출력")
    parser.add_argument("--follow-js", action="store_true", help="--grep 을 같은 사이트의 외부 JS 파일에도 적용")
    parser.add_argument("--form-post", default=None, help="이 셀렉터의 폼을 POST 한 응답을 본다 (예: form#frm)")
    parser.add_argument("--data", default="", help="--form-post 에 더할 값 (a=1&b=2)")
    parser.add_argument("--browser-ua", action="store_true", help="봇 표시 없는 일반 브라우저 User-Agent 사용")
    parser.add_argument("--direct", action="store_true",
                        help="국내 중계(KR_PROXY_URL)를 쓰지 않고 해외(GitHub) 서버에서 바로 접속해 본다")
    parser.add_argument("--agencies", action="store_true",
                        help="config/camp.yaml 의 기관 입찰 게시판을 임시 DB 로 시험 수집해 결과만 출력 (메일·state DB 안 건드림)")
    args = parser.parse_args()
    global RAW, RAW_FROM, GREP, FOLLOW_JS, FORM_POST
    RAW, RAW_FROM, FOLLOW_JS = args.raw, args.raw_from, args.follow_js
    GREP = re.compile(args.grep) if args.grep else None
    if args.form_post:
        from urllib.parse import parse_qsl

        FORM_POST = (args.form_post, dict(parse_qsl(args.data, keep_blank_values=True)))
    if args.direct:
        HTTP.kr_proxy = None
        print("국내 중계 없이 바로 접속합니다 (--direct)")
    if args.browser_ua:
        HTTP.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
        )
    if args.agencies:
        return agencies_report()
    if args.url_file:
        for line in (ROOT / args.url_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("http"):
                args.url.append(line.split()[0])
    if not args.url:
        parser.error("--url, --url-file 또는 --agencies 중 하나가 필요합니다")
    logging.basicConfig(level=logging.WARNING, format="  [%(levelname)s] %(message)s")
    for url in args.url:
        parse_report(url, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
