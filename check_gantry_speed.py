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
            print("Gantry Speed Check: Order(MW450) vs Feedback(DB57.DBW10)")
            print("-" * 60)
            
            # 100번만 읽어보기 테스트
            for i in range(100):
                # Order Speed: MW450 읽기
                order_data = client.mb_read(450, 2)
                order_val = get_int(order_data, 0)
                
                # Feedback Speed: DB57.DBW10 읽기
                feedback_data = client.db_read(57, 10, 2)
                feedback_val = get_int(feedback_data, 0)
                
                print(f"[{i+1}/100] Order: {order_val}  |  Feedback: {feedback_val}")
                time.sleep(1)
        else:
            print("❌ 연결 실패: IP 또는 PLC 설정을 확인하세요.")
            
    except Exception as e:
        print(f"⚠️ 오류 발생: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    check_readability()
