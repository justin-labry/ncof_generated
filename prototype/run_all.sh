#!/bin/bash
# 주의: bash 전용 문법(배열 등)을 쓰지 않는다.
#       프로젝트 관례상 `sh ./run_all.sh` 로도 실행되므로 POSIX sh 호환을 유지할 것.
set -u

# 세션 이름 설정
SESSION_NAME="ncof"

# 스크립트 파일 위치를 기준으로 경로를 확정(어느 디렉터리에서 실행해도 동작)
BASE_DIR=$(cd "$(dirname "$0")" && pwd)

# tmux 안에서 실행한 경우 세션을 중첩하지 않고 클라이언트만 전환
attach_session() {
  if [ -n "${TMUX:-}" ]; then
    tmux switch-client -t "$SESSION_NAME"
  else
    tmux attach-session -t "$SESSION_NAME"
  fi
}

if ! command -v tmux >/dev/null 2>&1; then
  echo "❌ tmux 가 설치되어 있지 않습니다. (예: sudo apt install tmux)"
  exit 1
fi

# 이미 같은 이름의 tmux 세션이 실행 중이라면 해당 세션으로 접속
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "⚠️ 이미 '$SESSION_NAME' 세션이 실행 중입니다. 해당 세션으로 접속합니다."
  attach_session
  exit 0
fi

# 실행할 디렉토리 목록(공백 구분 — 디렉터리명에 공백이 없음을 전제)
# nupf-server 는 독립 NF 가 아니라 nsmf/nncof 가 모델을 가져다 쓰는 uv 워크스페이스
# 라이브러리이므로(prototype/pyproject.toml 참조) 별도로 띄우지 않는다.
DIRS="api-clients callback-server nncof-server nnef-server nsmf-server"

# 기동 스크립트가 실제로 있는 대상만 추림 — 빈 패널이 남는 것을 방지
RUN_DIRS=""
for d in $DIRS; do
  if [ -f "$BASE_DIR/$d/run_http2.sh" ]; then
    RUN_DIRS="$RUN_DIRS $d"
  else
    echo "⚠️ 건너뜀: $d (run_http2.sh 없음)"
  fi
done

if [ -z "$RUN_DIRS" ]; then
  echo "❌ 실행할 서비스가 없습니다. BASE_DIR=$BASE_DIR"
  exit 1
fi

echo "🚀 tmux 세션을 생성하고 $(echo $RUN_DIRS | wc -w)개 서비스를 동시 실행합니다..."

# 첫 대상으로 세션을 만들고, 이후 대상은 패널을 분할하며 실행
#  - -c 로 패널 시작 경로를 지정하므로 send-keys 에 cd 를 넣지 않는다
#  - split-window 가 돌려주는 pane_id 로 대상을 명시(활성 패널 추적에 의존하지 않음)
#  - 매 분할 후 tiled 재정렬로 다음 분할 공간을 확보
FIRST_PANE=""
for d in $RUN_DIRS; do
  if [ -z "$FIRST_PANE" ]; then
    tmux new-session -d -s "$SESSION_NAME" -n "Services" -c "$BASE_DIR/$d"
    PANE=$(tmux list-panes -t "$SESSION_NAME" -F '#{pane_id}' | head -1)
    FIRST_PANE="$PANE"
  else
    PANE=$(tmux split-window -t "$SESSION_NAME" -c "$BASE_DIR/$d" -P -F '#{pane_id}')
  fi
  tmux send-keys -t "$PANE" "sh ./run_http2.sh" C-m
  tmux select-layout -t "$SESSION_NAME" tiled >/dev/null
done

# 최종적으로 패널을 격자(tiled) 형태로 균등 배치하고 대화형 클라이언트 패널로 포커스
tmux select-layout -t "$SESSION_NAME" tiled >/dev/null
tmux select-pane -t "$FIRST_PANE"

# 생성된 tmux 세션으로 화면 전환(접속)
attach_session
