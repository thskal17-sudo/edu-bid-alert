#!/usr/bin/env bash
# 수집 기록(DB)을 state 브랜치에 보관·복원한다 (GitHub Actions 에서 사용).
#   bash scripts/state_db.sh restore   state 브랜치의 bids.db → data/bids.db
#                                      state 브랜치가 아직 없으면(첫 실행) 울산 저장소 기록에서 camp_bids·camp_runs 를 옮겨 옴
#   bash scripts/state_db.sh save      data/bids.db → state 브랜치 (커밋 하나로 덮어씀, GITHUB_TOKEN 필요)
set -euo pipefail
db=data/bids.db
# 수주 알리미가 2026-11 까지 기록하던 곳 (공개 저장소)
old_repo=${OLD_STATE_REPO:-https://github.com/thskal17-sudo/ulsan-shcool-public-company.git}

case "${1:-}" in
  restore)
    mkdir -p data
    # state 브랜치가 '없는' 것과 '조회 실패'를 구분한다 (조회 실패를 첫 실행으로 보면 기록을 덮어쓸 수 있음)
    set +e
    git ls-remote --exit-code origin refs/heads/state >/dev/null
    found=$?
    set -e
    if [ "$found" -eq 0 ]; then
      git fetch --depth=1 origin state
      git show FETCH_HEAD:bids.db > "$db"
      echo "기존 수집 기록 복원 ($(stat -c %s "$db") bytes)"
    elif [ "$found" -eq 2 ]; then
      echo "state 브랜치 없음: 첫 실행 → 울산 저장소 기록에서 수주 알리미 표만 옮겨 옴"
      old=$(mktemp)
      if git fetch --depth=1 "$old_repo" state && git show FETCH_HEAD:postings.db > "$old"; then
        python -m edu_bid_alert import-old "$old" --db "$db"
      else
        echo "울산 저장소 기록을 가져오지 못함: 빈 기록으로 시작 (처음 10일치 공고를 다시 알림)"
      fi
    else
      echo "state 브랜치 조회 실패 (exit $found): 기록을 덮어쓰지 않게 이번 실행을 멈춤" >&2
      exit 1
    fi
    ;;
  save)
    tmp=$(mktemp -d)
    cp "$db" "$tmp/"
    cd "$tmp"
    git init -q -b state
    git add bids.db
    git -c user.name="github-actions[bot]" \
        -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
        commit -q -m "수집 기록 $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M')"
    git push -q -f "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" state
    ;;
  *)
    echo "사용법: $0 restore|save" >&2
    exit 2
    ;;
esac
