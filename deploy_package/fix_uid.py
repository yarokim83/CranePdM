"""
CranePdM 대시보드 UID 자동 수리 스크립트
서버 PC에서 실행하면 그라파나 데이터소스 UID를 자동으로
대시보드 JSON 파일에 적용합니다.
"""
import os, json, urllib.request, base64, glob

GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "admin"
GRAFANA_PASS = "adminpassword"

def get_influxdb_uid():
    """그라파나 API로 인플럭스DB 데이터소스의 실제 UID를 조회"""
    credentials = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASS}".encode()).decode()
    req = urllib.request.Request(
        f"{GRAFANA_URL}/api/datasources",
        headers={"Authorization": f"Basic {credentials}"}
    )
    with urllib.request.urlopen(req) as resp:
        datasources = json.loads(resp.read().decode('utf-8'))
    
    for ds in datasources:
        if ds.get("type") == "influxdb":
            return ds.get("uid")
    return None

def fix_json_files(target_uid):
    """현재 폴더의 대시보드 JSON 파일에서 col_cranepdm을 실제 UID로 교체"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_files = glob.glob(os.path.join(script_dir, "grafana_v2_*.json"))
    
    if not json_files:
        print("❌ grafana_v2_*.json 파일을 찾을 수 없습니다.")
        return
    
    for filepath in json_files:
        filename = os.path.basename(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # UID 교체 (col_cranepdm 또는 이전에 잘못 적용된 UID 모두 처리)
        original = content
        content = content.replace('col_cranepdm', target_uid)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        if original != content:
            print(f"🚀 수리 완료: {filename} (UID -> {target_uid})")
        else:
            print(f"✅ 이미 정상: {filename} (변경 없음)")

if __name__ == "__main__":
    print("=" * 50)
    print("🔧 CranePdM 대시보드 UID 자동 수리 도구")
    print("=" * 50)
    
    uid = get_influxdb_uid()
    if uid:
        print(f"\n✅ 인플럭스DB UID 발견: {uid}\n")
        fix_json_files(uid)
        print(f"\n{'=' * 50}")
        print("🎯 완료! 이제 그라파나에서 수리된 JSON 파일을 Import 하세요.")
        print(f"   경로: {os.path.dirname(os.path.abspath(__file__))}")
        print(f"{'=' * 50}")
    else:
        print("❌ 인플럭스DB 데이터소스를 찾을 수 없습니다.")
        print("   그라파나가 켜져 있는지, 데이터소스가 등록되어 있는지 확인하세요.")
