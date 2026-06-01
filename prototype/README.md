# NCOF 

## 사전설치

NOCF 프로젝트 실행을 위해서 아래 사항들을 준비한다.

- uv 설치 (0.6.12)
- python 설치 (3.12.9)
- nodejs 설치 (v24.13.1): UI 개발용

## 실행절차

- 5개의 터미널을 실행 후 서브프로젝트별 디렉토리로 이동하여 스크립트를 실행한다.

### 포트 할당 정보

1. NCOF: 8000
2. SMF(UPF): 8001
3. AF: 8002
4. RICF: 8003
5. PCF: 8004

### 실행 방법

```sh
sh run.sh # ./nncof-server
sh run_af.sh # ./nnef-server
sh run_ricf.sh # ./nnef-server (subscription, notification 모두 수행)
sh run.sh # ./nsmf-server (UPF Mockup 도 함께 수행)
sh run.sh # callback-server, NCOF 로부터 notification 수신을 위한 서버 (PCF Mockup 으로 활용)
```
- 현재 구현에서 callback-server 는 PCF 가 NCOF로 부터 제어 명령을 수신하는 기능만 제공하고, 구독요청 보내는 기능은 별도의 방법을 이용한다.

## 확인

PCF 또는 RICF 에서 NCOF로 구독요청을 보내기 위해서 Postman, VS Code REST Client Plugin, Python 클라이언트 등을 사용할 수 있다.
- 방법1: VSCode 를 사용하는 경우 확장자가 .http 인 파일을 선택하여 요청을 보낸다.
- 방법2: 터미널에서 client.py 를 실행한다. (추천)

### NCOF로 구독요청 보내기

./api-client/ 로 이동후 아래 명령을 실행한다. ./api-client/의 json 파일의 내용을 확인한다.

```sh
sh run.sh
```
메뉴가 출력되면 1번 또는 2번을 선택하여 구독 요청을 보낸다.

### 동작 확인

1. 개별 터미널에서 로그를 확인한다.
