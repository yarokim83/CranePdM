# CranePdM Project Rules

- **배포 시 버전 관리 규정**:
  - 업데이트 배포(코드 수정, 기능 갱신, 핫픽스 등)를 수행할 때마다 소스 코드(예: [crane_edge_logger.py](file:///c:/Users/huser/.gemini/CranePdM/crane_edge_logger.py)) 내에 명시된 버전 정보를 항상 **버전 업(상향 조정)**해야 합니다.
  - 실행 파일(예: `crane_edge_logger.exe`)을 갱신하여 배포 패키지(`deploy_package`)를 만들 때도, 반드시 버전 업된 소스를 기반으로 빌드하고 배포해야 합니다.
