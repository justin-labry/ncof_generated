# 작업 컨텍스트 노트

- 2026-07-31: `NetworkCanvas.vue`의 `animateMessage`는 D3 전환이 끝난 후 구독 및 분석 상태를 반영한다. 따라서 탭이 숨겨진 경우 애니메이션만 생략하면 상태 변경이 누락된다.
- 2026-07-31: `visibilitychange`에서 현재 D3 전환과 신호 SVG를 정리하고, 숨김 중 메시지는 상태만 반영하도록 구현한다.
- 2026-07-31: 전환 취소로 발생하는 D3의 Promise 거부는 처리하되, 컴포넌트가 마운트된 상태이면 구독·분석 상태를 항상 반영한다.
- 2026-07-31: `npm run build`의 TypeScript 검사와 Vite 번들 생성은 통과했다. 마지막 복사 단계는 Windows에 없는 Unix `cp` 명령 때문에 실패했다.

## DEVICE 모드 NF 구성

- 2026-09-04: `MODE=DEVICE`일 때만 `device_info.json`을 읽어 NF 조회 테이블을 만들고, 그 외 모드에서는 기존 `_build_dummy_nfs()` 동작을 유지한다.
- 2026-09-04: `device_info.json`은 `ncof_setting.conf`와 같은 방식으로 상위 디렉터리를 탐색한다. JSON에는 보간 표현식이 아니라 치환이 끝난 실제 URI 문자열이 들어 있어야 한다.
- 2026-09-04: DEVICE 모드에서 파일이 없으면 `FileNotFoundError`, JSON 최상위 값이 객체가 아니면 `ValueError`를 발생시켜 잘못된 NF 구성을 조기에 드러낸다.
- 2026-09-04: 신규 단위 테스트 3개와 Python 구문 검사는 통과했다. 전체 NCOF 테스트는 기존 생성 테스트의 `null` 참조로 4개가 실패하고 12개가 통과했다.
- 2026-09-04: `nrf.py`의 `print("ENV.MODE:", os.getenv("MODE"))`와 `main.py` 등의 기존 미커밋 변경은 사용자 작업으로 간주해 보존한다.
