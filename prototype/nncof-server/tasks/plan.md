# Spec: NCOF JSON 영속성

## Objective

NCOF가 최초 구독 요청, 수신 Notify, 생성한 제어 명령을 JSON 파일에 저장하고 재시작 후 활성 구독의 데이터 분석과 하위 NF 구독을 재개한다.

## Tech Stack

Python 3.12, FastAPI, Pydantic v2, 파일 기반 JSON 저장소를 사용한다. 새 외부 데이터베이스 의존성은 추가하지 않는다.

## Commands

테스트는 `PYTHONPATH=src pytest tests`로 실행한다.

## Project Structure

- `src/nncof/core/persistence_store.py`는 원자적 JSON 읽기와 쓰기를 담당한다.
- `src/nncof/core/data_store.py`는 Notify 출처를 포함한 상태 내보내기와 복원을 제공한다.
- `src/nncof/core/subscription_manager.py`는 상태 저장과 재시작 복구를 조정한다.
- `src/nncof/core/subscription_handler.py`는 Notify와 제어 명령 변경을 관리자에 알린다.
- `src/nncof/main.py`는 FastAPI 수명주기에서 복구와 정상 종료를 실행한다.

## Code Style

비즈니스 로직에는 한국어 독스트링을 사용하고, Pydantic 모델은 `to_dict()`와 `from_dict()`로 변환한다.

```python
await self._state_changed()
```

## Testing Strategy

임시 JSON 파일을 이용해 저장, 복원, 손상 파일 처리와 구독 CRUD의 상태 반영을 단위 테스트한다. 외부 NF HTTP 호출은 모킹한다.

## Boundaries

- Always. 데이터 상태가 변경되면 원자적으로 저장하고 테스트를 실행한다.
- Ask first. JSON 보관 기간, 자동 재시도 정책, 관계형 DB 전환은 별도 결정이 필요하다.
- Never. 생성된 `models/` 파일을 수정하거나 하위 NF 재구독 실패를 무한 재시도하지 않는다.

## Success Criteria

- 구독 요청, 수신 Notify, 제어 명령이 `NCOF_STATE_FILE` 또는 기본 JSON 파일에 저장된다.
- 재시작 시 유효한 구독과 수집 데이터를 복원하고 하위 NF 구독과 분석 태스크를 다시 시작한다.
- 만료 또는 손상된 상태 파일은 서버 기동을 막지 않는다.
- 삭제된 구독은 영속 상태에서도 제거된다.

## Decisions

- 하위 NF 구독 ID는 재시작 후 재사용하지 않는다. 기존 ID 해지를 시도한 뒤 새 구독을 생성한다.
- 정상 종료는 하위 NF 구독을 해지하지 않고, 분석 태스크와 HTTP 클라이언트만 정리한다.
