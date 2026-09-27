"""
客流统计Demo - 区域计数演示
用法：python demo_crowd.py --video test.mp4
"""
import cv2
import argparse
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.engine import AIEngine


def main():
    parser = argparse.ArgumentParser(description="追迹 - 客流统计Demo")
    parser.add_argument("--video", type=str, default="0")
    parser.add_argument("--model", type=str, default="yolov8n.pt")
    args = parser.parse_args()
    
    print("正在加载模型...")
    engine = AIEngine(model_path=args.model, mode="crowd")
    print("模型加载完成！")
    
    # 打开视频
    if args.video == "0":
        cap = cv2.VideoCapture(0)
    else:
        cap = cv2.VideoCapture(args.video)
    
    if not cap.isOpened():
        print(f"无法打开视频: {args.video}")
        return
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"视频尺寸: {width}x{height}")
    
    # 设置统计区域（画面中央的矩形）
    region = [
        (width // 4, height // 4),
        (width * 3 // 4, height // 4),
        (width * 3 // 4, height * 3 // 4),
        (width // 4, height * 3 // 4),
    ]
    engine.set_region(region)
    
    print("\n=== 客流统计Demo ===")
    print("按 'q' 退出")
    print("====================\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        result = engine.process_frame(frame)
        annotated = result["annotated_frame"]
        
        # 显示统计数据
        stats = result.get("crowd_stats", {})
        if stats:
            y_offset = 60
            cv2.putText(annotated, "=== 客流统计 ===", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            y_offset += 30
            
            cv2.putText(annotated, f"当前区域内: {stats.get('current_count', 0)}人",
                       (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            y_offset += 25
            cv2.putText(annotated, f"总进入: {stats.get('total_enter', 0)}",
                       (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            y_offset += 25
            cv2.putText(annotated, f"总离开: {stats.get('total_leave', 0)}",
                       (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        cv2.imshow("追迹 - 客流统计Demo", annotated)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 打印最终统计
    stats = engine.crowd_counter.get_current_stats() if engine.crowd_counter else {}
    print(f"\n=== 客流统计结果 ===")
    print(f"总进入: {stats.get('total_enter', 0)}")
    print(f"总离开: {stats.get('total_leave', 0)}")
    print(f"平均停留: {stats.get('avg_stay_duration', 0):.2f}秒")


if __name__ == "__main__":
    main()
