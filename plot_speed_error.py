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
                
                # 데이터 저장
                times.append(time.time() - start_time)
                orders.append(order_val)
                feedbacks.append(feedback_val)
                loads.append(is_locked)
                weights.append(weight_val)
                
                status_str = "Lock" if is_locked else "Unlock"
                print(f"[{i+1}/{samples}] Order: {order_val} | FB_Spd: {feedback_val} | Twist: {status_str} | Wgt: {weight_val}")
                time.sleep(0.1) # 0.1초 간격
                
        else:
            print("❌ PLC 연결 실패")
            return None, None, None, None, None
            
    except Exception as e:
        print(f"⚠️ 오류 발생: {e}")
        return None, None, None, None, None
    finally:
        if client.get_connected():
            client.disconnect()
            
    return times, orders, feedbacks, loads, weights

def analyze_and_plot(times, orders, feedbacks, loads, weights):
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

    avg_stress_loaded = total_stress_loaded / cnt_loaded if cnt_loaded > 0 else 0
    avg_stress_empty = total_stress_empty / cnt_empty if cnt_empty > 0 else 0
    avg_stress_total = sum(stress_scores) / len(stress_scores) if stress_scores else 0
    
    # 한글 폰트 설정 (윈도우)
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    
    # 그래프 그리기
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 11), sharex=True)
    
    np_times = np.array(times)
    np_loads = np.array(loads)
    
    # Load 상태 배경 구별 함수
    def add_load_background(ax, include_label=False):
        lbl = 'Loaded (Container)' if include_label else None
        ax.fill_between(np_times, 0, 1, where=np_loads, color='lightgray', alpha=0.5, 
                        transform=ax.get_xaxis_transform(), label=lbl)

    # 1. 속도 비교 그래프 (가중치/하중 표시 추가)
    ax1.plot(times, orders, label='Order (DB57.DBW8)', color='blue', linestyle='--')
    ax1.plot(times, feedbacks, label='Feedback (DB57.DBW10)', color='green')
    
    # 오른쪽 축에 하중(Weight) 차트 추가
    ax1_wgt = ax1.twinx()
    ax1_wgt.plot(times, weights, label='Total Load (Weight)', color='purple', alpha=0.3, linewidth=2)
    ax1_wgt.set_ylabel('Weight (DB57.DBW48)', color='purple')
    ax1_wgt.tick_params(axis='y', labelcolor='purple')
    
    ax1.set_title('Gantry Speed & Load Correlation')
    ax1.set_ylabel('Speed')
    add_load_background(ax1, True)
    
    # 범례 합치기
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_wgt.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    ax1.grid(True)
    
    # 2. 오차 그래프
    ax2.plot(times, errors, label='Error (Order - Feedback)', color='red')
    ax2.axhline(0, color='black', linestyle='--')
    ax2.set_title('Speed Error')
    ax2.set_ylabel('Difference')
    add_load_background(ax2)
    ax2.legend()
    ax2.grid(True)

    # 3. 케이블 스트레스 분석
    ax3.plot(times, stress_scores, label='Cable Stress Index', color='orange')
    ax3.axhline(avg_stress_loaded, color='purple', linestyle=':', label=f'Avg Loaded: {avg_stress_loaded:.1f}')
    ax3.axhline(avg_stress_empty, color='brown', linestyle=':', label=f'Avg Empty: {avg_stress_empty:.1f}')
    ax3.set_title('Cable Reel Stress Analysis')
    ax3.set_ylabel('Stress Score')
    ax3.set_xlabel('Time (s)')
    add_load_background(ax3)
    ax3.legend()
    ax3.grid(True)
    
    # 상태 판정 (Load-Aware)
    status = "Normal (정상)"
    if avg_stress_empty > 300: # 빈 훅인데 저항/오차가 크면 이상 징후
        status = "WARNING (빈 상태에서 높은 스트레스 발견 -> 기계적 마찰/구동부 점검 필요)"
    elif avg_stress_loaded > 600:
        status = "Caution (컨테이너 적재 시 높은 스트레스 -> 모터 추력 및 릴 세팅 확인)"
        
    fig.suptitle(f'Speed Analytics (Load-Aware) - 진단: {status}', fontsize=16)
    
    # 여백 조정
    plt.tight_layout()
    
    # 저장 및 표시
    filename = 'cable_reel_analysis_load_aware.png'
    plt.savefig(filename)
    print(f"\n📊 분석 그래프가 저장되었습니다: {filename}")
    print(f"🩺 진단 결과: {status}")
    print(f"   - 컨테이너 적재 시(Loaded) 평균 스트레스 : {avg_stress_loaded:.1f}")
    print(f"   - 빈 부분 이동 시(Empty) 평균 스트레스   : {avg_stress_empty:.1f}")
    print(f"   - 전체 평균 스트레스                  : {avg_stress_total:.1f}")
    plt.show()

if __name__ == "__main__":
    t, o, f, l, w = collect_data(samples=3000)
    if t:
        analyze_and_plot(t, o, f, l, w)
