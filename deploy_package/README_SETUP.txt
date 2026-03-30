===========================================================
  CranePdM V2.0 - 신규 PC 이관(설치) 가이드
===========================================================

이 폴더(deploy_package)를 그대로 복사하여 신규 PC 바탕화면에 붙여넣어 주세요.
신규 PC는 현장에 연결될 컴퓨터이면서, 동시에 서버(DB+대시보드) 역할을 수행합니다.

[설치 및 실행 절차]

1. Docker Desktop 설치
   - 신규 PC에 Docker Desktop이 설치되어 있지 않다면 설치해 주세요. (https://www.docker.com/products/docker-desktop/)

2. InfluxDB & Grafana (DB/웹서버) 구동
   - 명령 프롬프트(CMD)를 열고 이 폴더(deploy_package)로 이동합니다.
   - 다음 명령어를 입력하여 서버 인프라를 백그라운드로 실행합니다:
     docker-compose up -d
   (*참고: 초기 실행 시 InfluxDB 비밀번호(adminpassword)와 토큰(my-super-secret-auth-token), 버킷(cranepdm_kpis)이 자동 세팅됩니다.*)

3. Grafana 대시보드 셋업
   - 웹 브라우저를 열고 http://localhost:3000 에 접속합니다.
   - ID: admin / PW: admin (최초 로그인 시 비밀번호 변경 안내창이 뜹니다. 원하시는 암호(예: cranepdm2024)로 설정하세요)
   - 좌측 메뉴에서 'Connections' -> 'Data Sources'로 이동하여 InfluxDB가 잘 연결되어 있는지 확인합니다.
     (만약 없다면 InfluxDB 추가 후 URL: http://influxdb:8086, Token: my-super-secret-auth-token 입력)
   - 좌측 메뉴 'Dashboards' -> 우측 상단 '+' -> 'Import' 클릭
   - 동봉된 [grafana_v2_detail_dashboard.json] 파일 내용을 복사해서 붙여넣고 Import!
   - 그 다음 [grafana_v2_dashboard.json] 파일 내용도 복사해서 붙여넣고 Import!

4. 데이터 수집 로거(Edge Logger) 실행
   - 이제 모든 준비가 끝났습니다. 크레인과 통신망이 연결된 상태에서 바로 이 폴더에 있는 `crane_edge_logger.exe`를 더블클릭하여 실행하세요.
   - **백그라운드 실행**: 실행 시 별도의 창이 뜨지 않으며, 윈도우 우측 하단 **시스템 트레이(시계 옆)**에 아이콘이 나타납니다.
   - **자동 시작 설정**: 트레이 아이콘을 우클릭하여 'Auto-start on Boot'를 체크하면, PC 재부팅 시 프로그램이 자동으로 시작됩니다.
   - **종료**: 프로그램을 완전히 종료하려면 트레이 아이콘 우클릭 후 'Exit'를 클릭하세요.

* 주의: 트레이 아이콘이 떠 있는 동안에는 백그라운드에서 데이터를 실시간으로 수집하고 있습니다.
===========================================================
