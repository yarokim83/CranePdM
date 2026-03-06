# 🚀 CranePdM V1.0 배포 가이드

> **배포 대상 PC**: `10.200.19.104`  
> **작성일**: 2026-03-06  
> **예상 소요 시간**: 약 30분  

---

## 목차

1. [사전 준비물](#1-사전-준비물)
2. [Docker Desktop 설치](#2-docker-desktop-설치)
3. [Python 설치](#3-python-설치)
4. [프로젝트 코드 다운로드](#4-프로젝트-코드-다운로드)
5. [InfluxDB + Grafana 실행](#5-influxdb--grafana-실행)
6. [Grafana 데이터소스 연결](#6-grafana-데이터소스-연결)
7. [대시보드 Import](#7-대시보드-import)
8. [Python 환경 구성 및 실행](#8-python-환경-구성-및-실행)
9. [자동 시작 설정 (선택)](#9-자동-시작-설정-선택)
10. [접속 정보 요약](#10-접속-정보-요약)

---

## 1. 사전 준비물

| 항목 | 요구사항 |
|---|---|
| OS | Windows 10/11 (64-bit) |
| RAM | 최소 8GB |
| 디스크 여유 | 최소 10GB |
| 네트워크 | PLC 망 접근 가능 (10.200.71.x ~ 10.200.72.x) |
| 인터넷 | 초기 설치 시 필요 (Docker 이미지 다운로드) |

---

## 2. Docker Desktop 설치

### 2.1 다운로드
- https://www.docker.com/products/docker-desktop/ 접속
- **"Download for Windows"** 클릭 → 설치 파일 실행

### 2.2 설치 과정
1. 설치 마법사에서 **"Use WSL 2 instead of Hyper-V"** 체크 (권장)
2. 설치 완료 후 **PC 재부팅**
3. 재부팅 후 Docker Desktop 자동 실행 확인

### 2.3 설치 확인
PowerShell을 열고 아래 명령어 실행:
```powershell
docker --version
docker compose version
```
버전이 정상 출력되면 설치 완료.

> ⚠️ WSL 2 관련 오류 발생 시, PowerShell(관리자)에서 아래 명령 실행:
> ```powershell
> wsl --install
> ```
> 이후 PC 재부팅.

---

## 3. Python 설치

### 3.1 다운로드
- https://www.python.org/downloads/ 접속
- **Python 3.11 이상** 다운로드

### 3.2 설치 시 주의사항
- ⚠️ 설치 첫 화면에서 **"Add Python to PATH"** 반드시 체크!!
- "Install Now" 클릭

### 3.3 설치 확인
```powershell
python --version
pip --version
```

---

## 4. 프로젝트 코드 다운로드

### 방법 A: Git Clone (Git이 설치된 경우)
```powershell
cd C:\
git clone https://github.com/yarokim83/CranePdM.git
cd CranePdM
```

### 방법 B: ZIP 다운로드 (Git 없는 경우)
1. 브라우저에서 https://github.com/yarokim83/CranePdM 접속
2. 초록색 **"Code"** 버튼 → **"Download ZIP"** 클릭
3. 다운로드된 ZIP을 `C:\CranePdM` 에 압축 해제

---

## 5. InfluxDB + Grafana 실행

프로젝트 폴더에서 Docker Compose 실행:
```powershell
cd C:\CranePdM
docker compose up -d
```

실행 확인:
```powershell
docker ps
```

아래 두 컨테이너가 **"Up"** 상태인지 확인:
| 컨테이너 이름 | 포트 | 용도 |
|---|---|---|
| `cranepdm_influxdb` | 8086 | 시계열 데이터베이스 |
| `cranepdm_grafana` | 3000 | 대시보드 시각화 |

> 💡 처음 실행 시 Docker 이미지 다운로드로 2~3분 소요될 수 있습니다.

---

## 6. Grafana 데이터소스 연결

### 6.1 Grafana 접속
- 브라우저에서 **http://localhost:3000** 접속
- 로그인: `admin` / `adminpassword`

### 6.2 InfluxDB 데이터소스 추가
1. 좌측 메뉴 → ⚙️ **Connections** → **Data sources** → **Add data source**
2. **"InfluxDB"** 선택
3. 아래 값 입력:

| 항목 | 값 |
|---|---|
| **Name** | `InfluxDB_CranePdM` |
| **Query Language** | `Flux` |
| **URL** | `http://cranepdm_influxdb:8086` |
| **Organization** | `myorg` |
| **Token** | `my-super-secret-auth-token` |
| **Default Bucket** | `cranepdm_kpis` |

4. **"Save & Test"** 클릭 → ✅ 초록 메시지 확인

### 6.3 ⚠️ 중요: 데이터소스 UID 변경
대시보드 JSON이 `col_cranepdm` UID를 참조하므로, 데이터소스 UID를 맞춰야 합니다.

1. Data source 설정 페이지의 URL에서 현재 UID 확인  
   (예: `http://localhost:3000/connections/datasources/edit/abcd1234`)
2. 브라우저 주소창에 아래 URL 입력:
   ```
   http://localhost:3000/api/datasources/uid/abcd1234
   ```
3. 위 방법 대신, 더 간단한 방법: **대시보드 JSON 파일**에서 UID를 직접 수정

PowerShell에서 아래 명령으로 UID를 대시보드에 반영:
```powershell
# 먼저 현재 데이터소스 UID 확인
$response = Invoke-RestMethod -Uri "http://localhost:3000/api/datasources" -Headers @{Authorization="Basic $([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('admin:adminpassword')))"}
$uid = $response[0].uid
Write-Host "현재 데이터소스 UID: $uid"

# 대시보드 JSON의 UID를 현재 값으로 교체
(Get-Content "C:\CranePdM\grafana_unified_dashboard.json") -replace 'col_cranepdm', $uid | Set-Content "C:\CranePdM\grafana_unified_dashboard.json"
Write-Host "대시보드 JSON UID 교체 완료: col_cranepdm → $uid"
```

> 또는, Grafana API로 데이터소스 UID를 `col_cranepdm`으로 직접 지정할 수도 있습니다:
> ```powershell
> $body = @{
>   name = "InfluxDB_CranePdM"
>   type = "influxdb"
>   uid = "col_cranepdm"
>   url = "http://cranepdm_influxdb:8086"
>   access = "proxy"
>   jsonData = @{
>     defaultBucket = "cranepdm_kpis"
>     organization = "myorg"
>     version = "Flux"
>   }
>   secureJsonData = @{
>     token = "my-super-secret-auth-token"
>   }
> } | ConvertTo-Json -Depth 5
> 
> Invoke-RestMethod -Method Post -Uri "http://localhost:3000/api/datasources" `
>   -Headers @{Authorization="Basic $([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('admin:adminpassword')))"} `
>   -ContentType "application/json" -Body $body
> ```

---

## 7. 대시보드 Import

### 7.1 Import
1. Grafana 좌측 메뉴 → **Dashboards** → **New** → **Import**
2. **"Upload dashboard JSON file"** 클릭
3. `C:\CranePdM\grafana_unified_dashboard.json` 파일 선택
4. **"Import"** 클릭

### 7.2 확인
- 대시보드가 표시되면 설치 성공!
- 데이터가 아직 없으므로 패널이 빈 상태가 정상입니다.

---

## 8. Python 환경 구성 및 실행

### 8.1 Snap7 DLL 설치
`python-snap7` 라이브러리가 동작하려면 Snap7 DLL이 필요합니다.

```powershell
pip install python-snap7
```

> ⚠️ DLL 누락 오류 발생 시:
> 1. https://sourceforge.net/projects/snap7/files/1.4.2/ 에서 다운로드
> 2. `snap7.dll` 파일을 `C:\Windows\System32\` 에 복사

### 8.2 Python 패키지 설치
```powershell
cd C:\CranePdM
pip install -r requirements.txt
```

### 8.3 프로그램 실행
```powershell
cd C:\CranePdM
python crane_edge_logger.py
```

정상 실행 시 아래와 같은 메시지가 출력됩니다:
```
Edge Logger Started. Monitoring 38 cranes...
[14:05:23] [211] Connecting to PLC 10.200.71.11...
[14:05:24] [212] Connecting to PLC 10.200.71.12...
...
```

> 💡 PLC 연결에 실패하는 호기는 5초 간격으로 자동 재시도합니다.

---

## 9. 자동 시작 설정 (선택)

PC가 재부팅되어도 프로그램이 자동으로 시작되도록 설정합니다.

### 9.1 Docker 자동 시작
Docker Desktop 설정 → **General** → **"Start Docker Desktop when you sign in"** 체크  
(docker-compose.yml에 `restart: always`가 이미 설정되어 있으므로 Docker가 시작되면 컨테이너도 자동 시작)

### 9.2 Python 프로그램 자동 시작

**방법 A: 시작 프로그램 폴더** (간단)
1. `Win + R` → `shell:startup` 입력 → Enter
2. 열린 폴더에 바로가기 생성:
   - 우클릭 → 새로 만들기 → 바로 가기
   - 위치: `pythonw C:\CranePdM\crane_edge_logger.py`
   - 이름: `CranePdM Logger`

**방법 B: Windows 작업 스케줄러** (안정적, 권장)
```powershell
$action = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "C:\CranePdM\crane_edge_logger.py" -WorkingDirectory "C:\CranePdM"
$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "CranePdM_Logger" -Action $action -Trigger $trigger -Settings $settings -Description "ARMGC Crane PdM Edge Logger" -RunLevel Highest
```

---

## 10. 접속 정보 요약

배포 완료 후, **같은 네트워크의 모든 PC**에서 아래 주소로 대시보드에 접속할 수 있습니다:

| 서비스 | 주소 | 계정 |
|---|---|---|
| **Grafana 대시보드** | http://10.200.19.104:3000 | `admin` / `adminpassword` |
| **InfluxDB 관리** | http://10.200.19.104:8086 | `admin` / `adminpassword` |

> 💡 방화벽에서 포트 **3000**, **8086**이 차단되어 있다면 아래 명령으로 열어줍니다:
> ```powershell
> New-NetFirewallRule -DisplayName "Grafana" -Direction Inbound -Port 3000 -Protocol TCP -Action Allow
> New-NetFirewallRule -DisplayName "InfluxDB" -Direction Inbound -Port 8086 -Protocol TCP -Action Allow
> ```

---

## 체크리스트 ✅

| # | 단계 | 확인 |
|---|---|---|
| 1 | Docker Desktop 설치 및 실행 | ☐ |
| 2 | Python 3.11+ 설치 (PATH 추가) | ☐ |
| 3 | 프로젝트 코드 다운로드 (`C:\CranePdM`) | ☐ |
| 4 | `docker compose up -d` 실행 | ☐ |
| 5 | Grafana 데이터소스 연결 (UID: `col_cranepdm`) | ☐ |
| 6 | 대시보드 JSON Import | ☐ |
| 7 | `pip install -r requirements.txt` | ☐ |
| 8 | `python crane_edge_logger.py` 실행 | ☐ |
| 9 | 다른 PC에서 `http://10.200.19.104:3000` 접속 확인 | ☐ |
| 10 | 자동 시작 설정 (선택) | ☐ |

---

*문제 발생 시 `crane_edge_logger.py` 콘솔 출력 메시지를 확인하거나, Docker 로그를 점검하세요:*
```powershell
docker logs cranepdm_influxdb
docker logs cranepdm_grafana
```
