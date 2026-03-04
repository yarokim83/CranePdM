import snap7
from snap7.util import get_int, get_bool
import time
import matplotlib.pyplot as plt
import numpy as np

# PLC 설정
plc_ip = '10.200.72.34'
rack = 0
slot = 2

def collect_data(samples=3000):
    client = snap7.client.Client()
    times = []
    orders = []
    feedbacks = []
    loads = []
    weights = []
    positions = []
    
    try:
        client.connect(plc_ip, rack, slot)
        if client.get_connected():
            print(f"✅ PLC 연결 성공. {samples}개의 데이터 수집 시작 (약 5분 소요)...")
            
            start_time = time.time()
            for i in range(samples):
                # Order Speed (DB57.DBW8)
                order_data = client.db_read(57, 8, 2)
                order_val = get_int(order_data, 0)
                
                # Feedback Speed (DB57.DBW10)
                feedback_data = client.db_read(57, 10, 2)
                feedback_val = get_int(feedback_data, 0)
                
                # Twistlock Status (DB58.DBB185) - Lock is Bit 1
                tl_data = client.db_read(58, 185, 1)
                is_locked = get_bool(tl_data, 0, 1)
                
                # Total Load (Weight) (DB57.DBW48)
                weight_data = client.db_read(57, 48, 2)
                weight_val = get_int(weight_data, 0)
                
                # Gantry Position (DB57.DBW200)
                pos_data = client.db_read(57, 200, 2)
                pos_val = get_int(pos_data, 0)
                
                # 데이터 저장
                times.append(time.time() - start_time)
                orders.append(order_val)
                feedbacks.append(feedback_val)
                loads.append(is_locked)
                weights.append(weight_val)
                positions.append(pos_val)
                
                status_str = "Lock" if is_locked else "Unlock"
                print(f"[{i+1}/{samples}] Order: {order_val} | FB_Spd: {feedback_val} | Twist: {status_str} | Wgt: {weight_val} | Pos: {pos_val}")
                time.sleep(0.1) # 0.1초 간격
                
        else:
            print("❌ PLC 연결 실패")
            return None, None, None, None, None, None
            
    except Exception as e:
        print(f"⚠️ 오류 발생: {e}")
        return None, None, None, None, None, None
    finally:
        if client.get_connected():
            client.disconnect()
            
    return times, orders, feedbacks, loads, weights, positions

def analyze_and_plot(times, orders, feedbacks, loads, weights, positions):
    if not times:
        return

    # 오차 및 스트레스 계산
    errors = []
    stress_scores = []
    prev_feedback = feedbacks[0]
    
    total_stress_loaded = 0
    cnt_loaded = 0
    total_stress_empty = 0
    cnt_empty = 0
    
    for i in range(len(orders)):
        order = orders[i]
        feedback = feedbacks[i]
        is_loaded = loads[i]
        
        # 1. 속도 오차 (절대값)
        error = order - feedback
        errors.append(error)
        
        # 2. 급가감속 (Jerk) - 피드백 변화량
        jerk = abs(feedback - prev_feedback)
        prev_feedback = feedback
        
        # 3. 케이블 스트레스 지수 (가중치 적용)
        stress = (abs(error) * 0.6) + (jerk * 1.5)
        stress_scores.append(stress)
        
        if is_loaded:
            total_stress_loaded += stress
            cnt_loaded += 1
        else:
            total_stress_empty += stress
            cnt_empty += 1
            
    # 전체 상태 판단 KPI
    overall_stress = sum(stress_scores) / len(stress_scores)
    avg_stress_loaded = total_stress_loaded / cnt_loaded if cnt_loaded > 0 else 0
    avg_stress_empty = total_stress_empty / cnt_empty if cnt_empty > 0 else 0
    
    health_status = "Normal"
    if overall_stress > 250:
        health_status = "CRITICAL WARNING"
    elif overall_stress > 150:
        health_status = "Warning"

    # 시각화 (그래프 그리기)
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(12, 12), gridspec_kw={'height_ratios': [3, 2, 2, 1]})
    fig.suptitle('Gantry Speed, Error, Stress & Position Analysis', fontsize=16)

    # 1. 속도 그래프 (Order vs Feedback)
    ax1.plot(times, orders, label='Order Speed (MW450)', color='blue', linestyle='--')
    ax1.plot(times, feedbacks, label='Feedback Speed (DB57.DBW10)', color='red', alpha=0.7)
    
    # Twistlock Lock(주황) 구간 강조
    for i in range(len(times)-1):
        if loads[i]:
            ax1.axvspan(times[i], times[i+1], color='orange', alpha=0.1, lw=0)
            
    # X축 하중 데이터 추가
    ax1_w = ax1.twinx()
    ax1_w.plot(times, weights, color='green', alpha=0.3, label='Payload Weight (DB57.DBW48)')
    ax1_w.set_ylabel('Weight', color='green')

    ax1.set_ylabel('Speed')
    ax1.legend(loc='upper left')
    ax1.grid(True)
    ax1.set_title('Order vs Feedback Speed (Orange BG: Twistlock Locked)')

    # 2. 오차 그래프 (Order - Feedback)
    ax2.plot(times, errors, label='Speed Error', color='purple')
    ax2.axhline(0, color='black', linewidth=1)
    
    for i in range(len(times)-1):
        if loads[i]:
            ax2.axvspan(times[i], times[i+1], color='orange', alpha=0.1, lw=0)
            
    ax2.set_ylabel('Error Value')
    ax2.legend()
    ax2.grid(True)

    # 3. 스트레스/피로도 그래프
    ax3.plot(times, stress_scores, label='Cable Reel Stress Score', color='darkorange')
    ax3.axhline(150, color='red', linestyle=':', label='Warning Threshold')
    ax3.set_ylabel('Stress Index')
    ax3.legend()
    ax3.grid(True)
    
    # 4. Gantry 위치 그래프 추가
    ax4.plot(times, positions, label='Gantry Position (DB57.DBW62)', color='darkblue')
    ax4.set_xlabel('Time (seconds)')
    ax4.set_ylabel('Position')
    ax4.legend()
    ax4.grid(True)

    # 전체 통계 텍스트
    stats_text = (
        f"Health Status: {health_status}\n"
        f"Overall Avg Stress: {overall_stress:.1f}\n"
        f"Loaded Avg Stress: {avg_stress_loaded:.1f}\n"
        f"Empty Avg Stress: {avg_stress_empty:.1f}\n"
        f"Max Error: {max(map(abs, errors))}\n"
        f"Distance Traveled: {abs(positions[-1] - positions[0]) if positions else 0}"
    )
    plt.figtext(0.01, 0.01, stats_text, fontsize=10, bbox=dict(facecolor='white', alpha=0.8))

    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig('cable_reel_analysis_load_aware.png')
    plt.show()
    plt.close()

if __name__ == "__main__":
    t, o, f, l, w, p = collect_data(samples=3000) # 5분간 수집 (10Hz)
    analyze_and_plot(t, o, f, l, w, p)
