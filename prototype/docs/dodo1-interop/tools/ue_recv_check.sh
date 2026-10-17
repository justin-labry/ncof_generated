#!/bin/bash
# UE 수신 확인 (2026-10-17) — 동글 재연결 전후에 돌린다. 읽기 전용.
#  1) NCOF 최신 콘솔 꼬리에서 AF 9_ · RICF 10_a 의 UE·gNB 별 최근 값(thrputDl, plr)
#  2) 두두원 SBI 로그의 STAMP aggregate 최근 손실(notebook1_ue1 = UE1 NR, notebook2_ue1 = UE3 NR, *_ue2 = WLAN)
# 사용: bash ue_recv_check.sh [콘솔 꼬리 바이트 수, 기본 3000000 ≈ 최근 수 분]
# 정상 기준(10/13): UE1 9_ 약 100~110 Mbps · plr 0, UE3(gNB2 ACTIVE 때) 약 74 Mbps, STAMP loss 0.
# UE3 · gNB2(.123) 는 gNB2 가 DEEP_SLEEP 이면 두두원이 보고를 걸러 None 으로 나온다 — ACTIVE 때 값을 볼 것.
set -u
NC=/home/labry/git/ncof_generated/prototype/nncof-server
T=$(dirname "$(readlink -f "$0")")
B=${1:-3000000}
C=$(ls -t "$NC"/logs/console.2026-* | head -1)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
echo "NCOF 콘솔: $C ($(date '+%F %T'))"
tail -c "$B" "$C" > "$TMP/tail.log"
python3 -I "$T/ncof_console_notif_parse.py" "$TMP/tail.log" > "$TMP/tail.jsonl" 2>/dev/null
python3 -I - "$TMP/tail.jsonl" <<'EOF'
import json, sys
names = {'192.168.101.10': 'UE1 NR(노트북1)', '192.168.102.10': 'UE3 NR(노트북2)',
         '192.168.103.10': 'UE2 WLAN(노트북1)', '192.168.104.10': 'UE4 WLAN(노트북2)',
         '192.168.1.122': 'gNB1 N3', '192.168.1.123': 'gNB2 N3'}
last = {}
for line in open(sys.argv[1]):
    r = json.loads(line)
    if 'obj' not in r:
        continue
    for en in r['obj'].get('event_notifs') or []:
        for q in en.get('perf_data_infos') or []:
            ip = q['ue_ip_addr']['ipv4_addr']
            pd = q.get('perf_data') or {}
            last.setdefault((r['src'], ip), []).append((r['ts'][11:19], pd.get('thrput_dl'), pd.get('plr')))
if not last:
    print('최근 9_ / 10_a 통지 없음 — NCOF 가 떠 있는지, 바이트 수를 늘려 볼 것')
for (src, ip), v in sorted(last.items()):
    tail = ', '.join(f'{t} {d}/plr {p}' for t, d, p in v[-3:])
    print(f'{src:4} {ip:15} {names.get(ip, ""):18} {tail}')
EOF
echo "--- 두두원 STAMP 최근 손실 (loss %, count = 20초 창 행 수)"
timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=10 dodo1 'L=$(ls -t ~/SBI/app/sbi_poc_app.*.log | head -1); echo "SBI 로그: $L"; for id in notebook1_ue1 notebook2_ue1 notebook1_ue2 notebook2_ue2 gnb1 gnb2; do grep "STAMP aggregate id=$id " "$L" | tail -1 | sed -E "s/.*id=([^ ]+).* count=([0-9]+).* loss=([0-9.]+).*/  \1 count=\2 loss=\3/"; done' || echo "  (dodo1 ssh 실패 — NCOF 쪽 값만 볼 것)"
