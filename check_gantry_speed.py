import snap7
from snap7.util import get_int
import time

# 246호기 타겟 설정
plc_ip = '10.200.72.34'

def check_readability():
    client = snap7.client.Client()
    try:
        # S7-300 전용 슬롯(2번) 연결
        client.connect(plc_ip, 0, 2)
        
        if client.get_connected():
            print(f"✅ 연결 성공: {plc_ip}")
            print("Gantry 조이스틱을 조작하며 값이 변하는지 확인하세요.")
            
            # 10번만 읽어보기 테스트
            for _ in range(10):
                # MW450(2바이트) 읽기
                data = client.mb_read(450, 2)
                value = get_int(data, 0)
                print(f"현재 Order Speed 값: {value}")
                time.sleep(1)
        else:
            print("❌ 연결 실패: IP 또는 PLC 설정을 확인하세요.")
            
    except Exception as e:
        print(f"⚠️ 오류 발생: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    check_readability()
