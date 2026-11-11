"""8_(UPF 사용량 리포트) UE별 스루풋 집계 — ncof_console_notif_parse.py 출력(JSON lines)을 읽는다.

사용: python3 -I upf8_throughput_stats.py <a.jsonl[,b.jsonl]> [<시작 ts>] [<끝 ts>] [seq]
  ts 는 콘솔 헤더 형식("2026-10-08 13:24:31"). seq 를 주면 구독별 X/0/./p 시퀀스도 찍는다.
  tsm.dl_average_throughput = USER_DATA_USAGE_MEASURES 의 filter-00N-dl 흐름 값(6라운드 메일 §2 표의 기준).
"""
import json,sys,collections,statistics,re
IPMAP={'192.168.101.10':'UE1','192.168.102.10':'UE3','192.168.103.10':'UE2','192.168.104.10':'UE4'}
FLT={'filter-001':'192.168.101.10','filter-002':'192.168.102.10','filter-003':'192.168.103.10','filter-004':'192.168.104.10'}
def val(s):
    if s is None: return None
    m=re.fullmatch(r'\s*([-0-9.eE+]+)\s*(\w+)\s*',str(s))
    if not m: return ('BAD',s)
    return (float(m.group(1)), m.group(2))
start=sys.argv[2] if len(sys.argv)>2 else ''
end=sys.argv[3] if len(sys.argv)>3 else '9'
units=collections.Counter()
series=collections.defaultdict(list)   # key (field, ue) -> list of (ts, sub, value or None)
nblk=collections.Counter()
for f in sys.argv[1].split(','):
  for l in open(f):
    r=json.loads(l)
    if r['src']!='UPF' or not (start<=r['ts']<=end): continue
    o=r['obj']; items=o['notification_items']
    if not any(it['event_type']=='QOS_MONITORING' for it in items): continue  # 8_ only
    sub=o['correlation_id'][-15:]
    nblk[sub]+=1
    for it in items:
        if it['event_type']=='QOS_MONITORING':
            ip=it['ue_ipv4_addr']; q=it.get('qos_monitoring_measurement') or {}
            for fld in ('dl_ave_throughput','ul_ave_throughput'):
                v=val(q.get(fld)); 
                if v: units[('qm',fld,v[1])]+=1
                series[('qm.'+fld,IPMAP[ip])].append((r['ts'],sub,None if v is None else v[0], r['hdr_line']))
        elif it['event_type']=='USER_DATA_USAGE_MEASURES':
            for u in it['user_data_usage_measurements'] or []:
                pf=u['flow_info']['pack_filt_id']; ip=FLT[pf[:10]]; d=pf[-2:]
                t=u.get('throughput_statistics_measurement') or {}
                for fld in ('dl_average_throughput','ul_average_throughput','ul_peak_throughput','dl_peak_through_put','dl_peak_throughput'):
                    if fld not in t: continue
                    v=val(t.get(fld))
                    if v: units[('tsm',fld,v[1])]+=1
                    if (d=='dl' and fld.startswith('dl')) or (d=='ul' and fld.startswith('ul')):
                        series[('tsm.'+fld,IPMAP[ip])].append((r['ts'],sub,None if v is None else v[0], r['hdr_line']))
print('blocks per sub',dict(nblk))
print('units',dict(units))
def fmt(x): return '%.2f'%x
for k in sorted(series):
    s=series[k]; n=len(s)
    vals=[x[2] for x in s if x[2] is not None]
    nz=[v for v in vals if v!=0]
    big=[v for v in vals if v>1000]
    zero=sum(1 for v in vals if v==0)
    plaus=[v for v in vals if 0<v<=1000]
    line='%-32s %s n=%d present=%d none=%d zero=%d >1000=%d (%.1f%% of n, %.1f%% of present) plaus(0,1000]=%d'%(k[0],k[1],n,len(vals),n-len(vals),zero,len(big),100*len(big)/n if n else 0,100*len(big)/len(vals) if vals else 0,len(plaus))
    if vals: line+=' min=%s med=%s max=%s'%(fmt(min(vals)),fmt(statistics.median(vals)),fmt(max(vals)))
    if nz: line+=' | nonzero min=%s med=%s'%(fmt(min(nz)),fmt(statistics.median(nz)))
    print(line)
    if len(sys.argv)>4:
        persub=collections.defaultdict(list)
        for x in s: persub[x[1]].append(x)
        for sb,xs in persub.items():
            print('     sub',sb,''.join('.' if x[2] is None else ('0' if x[2]==0 else ('X' if x[2]>1000 else 'p')) for x in xs))
