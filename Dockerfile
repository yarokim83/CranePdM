FROM python:3.9-slim

# 필요한 의존성 설치를 위해 작업 디렉토리 설정
WORKDIR /app

# 파이썬 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 파이썬 스크립트 복사
COPY crane_edge_logger.py .

# 컨테이너 시작 시 수집기 실행
CMD ["python", "-u", "crane_edge_logger.py"]
