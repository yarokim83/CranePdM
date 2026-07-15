# CranePdM Project Rules

- **배포 시 버전 관리 규정**:
  - 업데이트 배포(코드 수정, 기능 갱신, 핫픽스 등)를 수행할 때마다 소스 코드(예: [crane_edge_logger.py](file:///c:/Users/huser/.gemini/CranePdM/crane_edge_logger.py)) 내에 명시된 버전 정보를 항상 **버전 업(상향 조정)**해야 합니다.
  - 실행 파일(예: `crane_edge_logger.exe`)을 갱신하여 배포 패키지(`deploy_package`)를 만들 때도, 반드시 버전 업된 소스를 기반으로 빌드하고 배포해야 합니다.
- **QC SCR - ARMGC GCR 격리 개발 규정**:
  - QC SCR(Quay Crane Spreader Cable Reducer) 기능 개발 및 수정 시, 기존 운영 중인 ARMGC GCR(Yard Crane Gantry Cable Reel) 수집기 동작 및 데이터의 정합성에 절대로 영향을 미치지 않도록 다음과 같은 이중 격리 아키텍처를 상시 유지해야 합니다.
  - **데이터베이스 태그 격리**: InfluxDB 적재 시 `source`, `crane_type`, `component` 태그를 상호 엄격히 다르게 매핑합니다.
    - 야드 크레인(ARMGC GCR): `source="live_v26"`, `crane_type="ARMGC"`, `component="CableReel"`
    - 안벽 크레인(QC SCR): `source="live_qc_v26"`, `crane_type="QC"`, `component="SpreaderCable"`
  - **대시보드 필터 격리**: ARMGC GCR 대시보드([crane_pdm.json](file:///c:/Users/huser/.gemini/CranePdM/grafana/dashboards/crane_pdm.json))의 모든 종합 통계 패널 쿼리 및 호기 선택 드롭다운 콤보박스는 정규식 `/^2.*/`를 강제 적용하여 200번대 야드 크레인만 조회되도록 차단 상태를 상시 유지해야 합니다.
  - **수집 코드 격리**: `crane_edge_logger.py` 내의 QC SCR 전용 수집기 루프(`monitor_qc_spreader()`)와 ARMGC GCR 수집기 루프(`monitor_crane()`)는 서로 독립된 함수로 분리 구현하여 스레드 간 기능적 결합도(Coupling)를 차단해야 합니다.
