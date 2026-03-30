import influxdb_client
from datetime import timedelta

# InfluxDB 접속 정보 (현장 서버 PC 기준)
url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"

try:
    client = influxdb_client.InfluxDBClient(url=url, token=token, org=org, timeout=60000)
    query_api = client.query_api()
except Exception as e:
    print(f"❌ InfluxDB 연결 실패: {e}")
    exit(1)

print("🔍 InfluxDB 분석 시작...")
print("최근 7일간 'Max 오차가 9500 이상' 발생한 시점의 정확한 원시 데이터(Raw Data)를 추적합니다.\n")

# 1. kpis 버킷에서 오차가 9500 이상이었던 주행(Movement)의 종료시간(_time)을 찾습니다.
q_kpi = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "max_error")
  |> filter(fn: (r) => r["_value"] > 9500.0)
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 5)
'''

print("👉 1단계: 10000 갭이 발생한 주행 이벤트 검색 중...")
tables = query_api.query(q_kpi)

if not tables:
    print("✅ 최근 7일 내에 오차가 9500 이상인 데이터가 없습니다.")
    exit(0)

print(f"✅ 총 {len(tables[0].records)}건의 비정상 주행 이벤트(max_error > 9500)를 발견했습니다.\n")

for i, record in enumerate(tables[0].records):
    end_time = record.get_time()
    crane_id = record.values.get("crane_id")
    max_err = record.get_value()
    
    print("======================================================")
    print(f"🚨 [Case {i+1}] 타겟 발견! | 호기: {crane_id} | 측정된 Max 오차: {max_err:.0f}")
    print(f"  주행 기록 시각: {end_time}")
    print("👉 2단계: 해당 로케이션의 100ms 단위 상세 통신 로그를 불러옵니다...\n")
    
    # 2. 해당 주행이 끝난 시점 기준으로 -2분 ~ +10초 사이의 raw 데이터를 가져옵니다.
    start_time_str = (end_time - timedelta(minutes=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
    end_time_str = (end_time + timedelta(seconds=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    q_raw = f'''
    from(bucket: "cranepdm_raw")
      |> range(start: {start_time_str}, stop: {end_time_str})
      |> filter(fn: (r) => r["_measurement"] == "crane_data")
      |> filter(fn: (r) => r["crane_id"] == "{crane_id}")
      |> filter(fn: (r) => r["_field"] == "db11_gantry_fbspeed" or r["_field"] == "db11_gantry_speed" or r["_field"] == "db11_gantry_pos")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    
    try:
        raw_tables = query_api.query(q_raw)
        if not raw_tables:
            print("❌ 원시 로그 데이터가 없습니다. (보존 기간 만료 또는 삭제됨)\n")
            continue
            
        points = []
        for raw_table in raw_tables:
            for raw_record in raw_table.records:
                time = raw_record.get_time()
                pos = raw_record.values.get("db11_gantry_pos")
                order = raw_record.values.get("db11_gantry_speed")
                feedback = raw_record.values.get("db11_gantry_fbspeed")
                
                # None 예외 처리
                pos = pos if pos is not None else 0.0
                order = order if order is not None else 0.0
                feedback = feedback if feedback is not None else 0.0
                
                diff = abs(order - feedback)
                points.append({"time": time, "pos": pos, "order": order, "feedback": feedback, "diff": diff})
        
        # 시간순 정렬
        points.sort(key=lambda x: x["time"])
        
        # 9500 이상의 갭이 발생한 최초 시점 찾기
        huge_gaps = [p for p in points if p["diff"] > 9500.0]
        
        if not huge_gaps:
             print("❌ 10000 갭 순간을 정확히 캡처하지 못했습니다. (데이터 수집 딜레이 가능성)\n")
             continue
             
        first_gap = huge_gaps[0]
        first_gap_time = first_gap["time"]
        
        print(f"⏱️ 10000 갭 발생 최초 시각: {first_gap_time}")
        print(f"📍 해당 시점 갠트리 위치: {first_gap['pos']:.1f} m\n")
        
        # 앞뒤 3초 데이터만 필터링하여 출력
        start_context = first_gap_time - timedelta(seconds=2)
        end_context = first_gap_time + timedelta(seconds=2)
        context_points = [p for p in points if start_context <= p["time"] <= end_context]
        
        if context_points:
            print("--- [ ⏱️ 갭 발생 전/후 2초 데이터 흐름 추적 ] ---")
            print(f"{'Time':<25} | {'Position(m)':<12} | {'지령(Order)':<11} | {'실제반응(FB)':<11} | {'순간 오차(Diff)':<13}")
            print("-" * 80)
            for p in context_points:
                # 갭이 클 때는 빨간색 느낌표 표시를 위해 살짝 문자 추가
                alert = "🚨" if p["diff"] > 9500.0 else "  "
                time_str = p['time'].strftime('%H:%M:%S.%f')[:-3]
                print(f"{time_str:<25} | {p['pos']:<12.1f} | {p['order']:<11.0f} | {p['feedback']:<11.0f} | {alert} {p['diff']:.0f}")
            print("\n")
            
    except Exception as e:
        print(f"원시 로그 파싱 중 오류 발생: {e}\n")

print("👉 분석이 완료되었습니다. 결과 로그를 위로 올려서 확인해보세요!")
