#!/bin/bash

# 세션 이름 설정
SESSION_NAME="ncof"

# 이미 같은 이름의 tmux 세션이 실행 중이라면 해당 세션으로 접속
tmux has-session -t $SESSION_NAME 2>/dev/null
if [ $? -eq 0 ]; then
  echo "⚠️ 이미 '$SESSION_NAME' 세션이 실행 중입니다. 해당 세션으로 접속합니다."
  tmux attach-session -t $SESSION_NAME
  exit 0
fi

# 스크립트가 실행된 현재 루트 디렉토리 위치 파악
BASE_DIR=$(pwd)

# 실행할 디렉토리 목록 배열 정의
DIRS=(
  "api-clients"
  "callback-server"
  "nncof-server"
  "nnef-server"
  "nsmf-server"
)

echo "🚀 tmux 세션을 생성하고 5개 서비스를 동시 실행합니다..."

# 1. 첫 번째 디렉토리(api-clients)로 백그라운드 tmux 세션 생성
tmux new-session -d -s $SESSION_NAME -n "Services"
tmux send-keys -t $SESSION_NAME "cd $BASE_DIR/${DIRS[0]} && sh ./run_http2.sh" C-m

# 2. 나머지 4개 디렉토리에 대해 패널을 분할하며 실행
for i in $(seq 1 $((${#DIRS[@]} - 1))); do
  tmux split-window -t $SESSION_NAME
  tmux send-keys -t $SESSION_NAME "cd $BASE_DIR/${DIRS[$i]} && sh ./run_http2.sh" C-m
  # 매 분할 시 레이아웃 균등 재정렬
  tmux select-layout -t $SESSION_NAME tiled
done

# 3. 최종적으로 5개 패널을 격자(tiled) 형태로 균등 배치
tmux select-layout -t $SESSION_NAME tiled

# 4. 생성된 tmux 세션으로 화면 전환(접속)
tmux attach-session -t $SESSION_NAME
