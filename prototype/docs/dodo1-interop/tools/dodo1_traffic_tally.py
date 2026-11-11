"""두두원 sbi_poc_app 로그의 traffic raw/interval/counter reset 줄을 IMSI별로 센다(10/08 빌드 로그 형식).

사용: python3 -I dodo1_traffic_tally.py <sbi_poc_app.….log>
  IMSI별 결과 분포(big=>1000 Mbps · zero · reset · plaus), 조회된 currentDl 고유값과 횟수를 찍는다.
"""
import re,sys,collections,statistics
raw=re.compile(r'traffic raw imsi=(\d+) sec=(\d+) baseUl=(\d+) currentUl=(\d+) baseDl=(\d+) currentDl=(\d+)')
itv=re.compile(r'traffic interval imsi=(\d+) sec=(\d+) deltaUl=(-?\d+) deltaDl=(-?\d+) avgUlBps=([\d.]+) avgDlBps=([\d.]+) maxUlBps=([\d.]+) maxDlBps=([\d.]+)')
rst=re.compile(r'traffic counter reset imsi=(\d+)')
cur=collections.defaultdict(collections.Counter)
res=collections.defaultdict(lambda: collections.Counter())
avg=collections.defaultdict(list); mx=collections.defaultdict(list)
order=collections.defaultdict(list)
for ln,l in enumerate(open(sys.argv[1],errors='replace'),1):
    m=raw.search(l)
    if m: cur[m.group(1)][int(m.group(6))]+=1; continue
    m=itv.search(l)
    if m:
        im=m.group(1); a=float(m.group(6))/1e6; avg[im].append(a); mx[im].append(float(m.group(8))/1e6)
        res[im]['zero' if a==0 else ('big' if a>1000 else 'plaus')]+=1
        order[im].append('0' if a==0 else ('X' if a>1000 else 'p')); continue
    m=rst.search(l)
    if m: res[m.group(1)]['reset']+=1; order[m.group(1)].append('.')
for im in sorted(res):
    r=res[im]; n=sum(r.values()); nz=[a for a in avg[im] if a>0]
    print(im,'n=%d'%n,dict(r),'big_pct=%.1f'%(100*r['big']/n),'nonzero min/med/max=',((round(min(nz),2),round(statistics.median(nz),2),round(max(nz),2)) if nz else None),'maxDl range=',((round(min(mx[im]),3),round(max(mx[im]),3)) if mx[im] else None))
    print('   distinct currentDl:',len(cur[im]),dict(cur[im].most_common()))
    print('   seq:',''.join(order[im]))
