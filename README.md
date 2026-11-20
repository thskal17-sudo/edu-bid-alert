# 교육 입찰 알리미 (edu-bid-alert)

진로·취업·창업 캠프와 교육 운영 입찰공고를 매일 모아 **새 공고가 있을 때만** 메일을 한 통 보냅니다.
2026-11 에 울산 강사 공고 수집 저장소(`ulsan-shcool-public-company`)의 '캠프·교육 수주 공고'를 그대로 옮겨 왔습니다.

- 실행: 매일 새벽 02:23(예비 05:23)과 낮 13:17 KST (`.github/workflows/bids.yml`)
- 기록: 이 저장소 `state` 브랜치의 `bids.db` 안 `camp_bids` 표 (공고마다 한 줄, 등급·분야·마감·금액·주소)
  - Cowork 예약 작업 등 다른 곳에서 읽을 주소: `https://github.com/thskal17-sudo/edu-bid-alert/raw/state/bids.db`

## 모으는 곳

- **나라장터 용역 입찰공고** (조달청 API): 대학·공공기관·교육청의 큰 입찰
- **S2B 학교장터 견적요청·소액수의 공고** (부산·울산·경남 학교): 학교가 2천만원 이하로 사는 캠프·교육
  - 전체공개 / 부산 업체 가능 → 바로지원
  - 학교가 업체를 미리 정해 둔 견적(공급업체 선택) → 참고 (영업 대상 학교)
- **국가 산하기관 자체 입찰·공모** (`src/edu_bid_alert/agency.py`): 나라장터에 안 올리는 공고
  - ALIO 공공기관 입찰공고(모든 공공기관 모음), 한국과학창의재단(사업공고·입찰공고), 한국청년기업가정신재단(공지 중 입찰·공모)
  - `camp_bids` 에 `source='기관명'` 으로 들어감. 나라장터와 겹치는 공고(나라장터 공고번호가 있거나 제목이 같은 것)는 뺌
  - robots.txt 가 막으면 읽지 않고 메일 아래 '읽지 못한 곳'에 표시 (Crawl-delay 도 지킴)
  - 한국고용정보원은 robots.txt 가 입찰 목록을 막아서 읽지 않음

## 분야·등급

- 분야: 공고명에 진로·취업·창업 등이 있으면 **진로·취업·창업**, 교육·방과후·늘봄·AI·코딩 등이면 **[교육]**
  (키워드·제외어는 [config/camp.yaml](config/camp.yaml))
- **★ 바로지원**: 참가 가능 지역이 부산(또는 제한 없음)이고, 수의계약·S2B 견적이거나 추정가격 2,000만원 이하
- **검토**: 금액이 큰 입찰, 참가 범위를 읽지 못한 공고, **금액이나 마감을 못 읽은 기관 입찰**
- **참고**: 다른 지역 업체나 학교가 정한 업체만 낼 수 있음 (견적 기준·영업 대상으로 참고)
- 이미 알린 바로지원·검토 공고가 마감 3일 이내로 남으면 '마감임박'에 다시 보여줌
- 한 곳이 막혀도 다른 곳 공고는 알리고, 메일 아래에 읽지 못한 곳을 표시

## 필요한 설정 (Settings → Secrets and variables → Actions)

| 이름 | 내용 |
|---|---|
| `G2B_API_KEY` | 공공데이터포털 '조달청_나라장터 입찰공고정보서비스' 일반 인증키 |
| `SMTP_USER` | 보내는 Gmail 주소 |
| `SMTP_APP_PASSWORD` | Gmail 앱 비밀번호 |
| `MAIL_TO` | 받는 주소 (여러 명이면 쉼표) |
| `KR_PROXY_URL` | (선택) 국내 중계 서버. 없으면 바로 접속 |

## 울산 저장소에서 옮겨 오기 (한 번만)

1. 위 Secrets 를 등록한다 (울산 저장소와 같은 값).
2. 울산 저장소에서 캠프·교육 수주 수집을 끈다 (그 PR 을 먼저 머지 → 같은 공고가 두 번 오지 않게).
3. 이 저장소의 첫 PR 을 머지한다. 다음 예약 시각(또는 **Actions → 교육 입찰 수집 → Run workflow**)에 첫 실행.
   - 첫 실행 때 `state` 브랜치가 없으면 울산 저장소 `state` 브랜치의 `postings.db` 에서
     `camp_bids`·`camp_runs` 만 옮겨 온다 (이미 알린 공고는 다시 보내지 않음). `scripts/state_db.sh`
4. Cowork 예약 작업이 읽는 DB 주소를 위 `bids.db` 주소로 바꾼다 (표 이름 `camp_bids` 는 그대로).

## 시험·진단

- 메일 없이 실행: **Actions → 교육 입찰 수집 → Run workflow** 에서 '메일 발송' 끄기 (결과는 실행 기록 요약에)
- 메일 설정 확인: `python -m edu_bid_alert send-test-mail`
- 새 기관 게시판 넣기 전 확인: **Actions → 사이트 진단 (probe) → Run workflow**, args 에
  `--direct --url-file scripts/probe_urls_agency.txt` (접속·robots.txt·목록 구조)
- 지금 설정 그대로 기관 입찰 시험 수집: args 에 `--agencies` (메일·state DB 는 건드리지 않음)
- 테스트: `pip install -r requirements-dev.txt && python -m pytest -q`
