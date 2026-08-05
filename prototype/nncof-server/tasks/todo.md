# NCOF JSON 영속성 작업 목록

- [ ] JSON 저장소와 상태 파일 경로를 구현한다.
  - Acceptance. 원자적 쓰기와 손상 파일 격리가 가능하다.
  - Verify. 저장소 단위 테스트.
- [ ] Notify 데이터 저장소의 직렬화와 복원을 구현한다.
  - Acceptance. Notify 출처와 데이터가 유지된다.
  - Verify. 데이터 저장소 단위 테스트.
- [ ] 구독 핸들러와 관리자의 상태 저장 및 재시작 복구를 구현한다.
  - Acceptance. CRUD와 Notify가 JSON 상태에 반영되고 활성 구독이 복원된다.
  - Verify. 관리자 단위 테스트.
- [ ] FastAPI 수명주기와 테스트를 추가한다.
  - Acceptance. 서버 시작과 정상 종료에 복구 및 저장이 연결된다.
  - Verify. `PYTHONPATH=src pytest tests`.
