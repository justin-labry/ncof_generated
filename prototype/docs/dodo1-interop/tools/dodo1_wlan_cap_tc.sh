#!/bin/bash
# Non-3GPP(.125) 접속 용량 에뮬레이션 (2026-10-31) — dodo1(CP/UP 서버)에서 root 로 돌린다.
#  dodo1 N3 NIC 에서 .125 로 가는 하향(GTP-U G-PDU 2152 + 배경부하 udptp 6006/6007)만 HTB 클래스 1:10 에 묶고
#  PIE 로 같은 확률 드롭 → 배경부하가 용량을 넘으면 WLAN 다리(…103 · …104) VoD 도 같이 손실. gNB1 · gNB2 · NGAP 은 1:20(fq_codel).
#  clsact police(토큰버킷)는 쓰지 않는다 — udptp 64패킷 묶음 탓에 드롭이 udptp 에 몰려 VoD 손실이 예측되지 않는다(10/31 검토).
# 사용: sudo bash dodo1_wlan_cap_tc.sh apply [Mbps]   설치(기본 950 = 깎지 않음). 재부팅 뒤 다시 걸 때는 apply 570
#       sudo bash dodo1_wlan_cap_tc.sh cap <Mbps>     용량 바꾸기(시연 570, 더 깨지게 500 등). 재기동 없이 즉시
#       sudo bash dodo1_wlan_cap_tc.sh uncap          깎기만 풀기(ceil 950)
#       sudo bash dodo1_wlan_cap_tc.sh remove         원복(root qdisc 삭제 → 커널 기본 mq + fq_codel)
#            bash dodo1_wlan_cap_tc.sh status         조회(root 불필요) — 1:10 rate/ceil, pie dropped · prob · delay, SCTP
# 재부팅 · igb 재적재 때 사라진다(traffic_client.service 는 enabled 라 bg 는 다시 뜬다 — HIGH 350 이면 깎기 없이도 위험은 없다).
set -eu
DEV=${DEV:-enp131s0f1}
N3IWF=192.168.1.125
class10() { # $1 = rate Mbps, $2 = ceil Mbps, $3 = add | change
	tc class "$3" dev "$DEV" parent 1:1 classid 1:10 htb rate "$1"mbit ceil "$2"mbit quantum 15140
}
case "${1:-status}" in
apply)
	R=${2:-950}
	[ "$R" -le 950 ] || { echo "용량은 950 이하"; exit 2; }
	if tc qdisc show dev "$DEV" | grep -q '^qdisc htb 1: root'; then
		echo "이미 htb 가 걸려 있다 — 용량만 바꾸려면 cap, 처음부터 다시는 remove 뒤 apply"; exit 3
	fi
	tc qdisc replace dev "$DEV" root handle 1: htb default 20
	tc class add dev "$DEV" parent 1: classid 1:1 htb rate 950mbit ceil 950mbit quantum 15140
	class10 "$(( R < 570 ? R : 570 ))" "$R" add
	tc class add dev "$DEV" parent 1:1 classid 1:20 htb rate 320mbit ceil 950mbit quantum 15140
	tc qdisc add dev "$DEV" parent 1:10 pie limit 10000 target 15ms
	tc qdisc add dev "$DEV" parent 1:20 fq_codel
	tc filter add dev "$DEV" parent 1: protocol ip pref 11 u32 match ip dst $N3IWF/32 match ip protocol 17 0xff match ip dport 2152 0xffff match u8 0xff 0xff at 29 flowid 1:10
	tc filter add dev "$DEV" parent 1: protocol ip pref 12 flower ip_proto udp dst_ip $N3IWF dst_port 6006 classid 1:10
	tc filter add dev "$DEV" parent 1: protocol ip pref 13 flower ip_proto udp dst_ip $N3IWF dst_port 6007 classid 1:10
	;;
cap)
	R=${2:?용량(Mbps)}
	[ "$R" -le 950 ] || { echo "용량은 950 이하"; exit 2; }
	class10 "$R" "$R" change
	;;
uncap) class10 570 950 change ;;
remove) tc qdisc del dev "$DEV" root ;;
status)
	tc class show dev "$DEV" | grep '^class htb 1:10 ' || { echo "htb 없음 — 설치 안 됨(기본 mq)"; exit 0; }
	tc -s qdisc show dev "$DEV" | grep -A4 '^qdisc pie'
	awk -v ip=$N3IWF 'NR>1 && $0 ~ ip {print "SCTP(N2) .125 ST=" $5 " (3 = ESTABLISHED)"}' /proc/net/sctp/assocs
	;;
*) sed -n '2,12p' "$0"; exit 2 ;;
esac
