"""
竞速场景Demo - 过线计时演示（增强版）
功能：
  1. 追踪ID排名
  2. 跑道号分配
  3. 衣服颜色识别
  4. 中文UI界面
  5. 保存输出视频
  6. 暂停/慢放
  7. 自动截图排名

用法：python demo_racing.py --video test.mp4
按键：S=开始 R=重置 Q=退出 空格=暂停/继续
"""
import cv2
import argparse
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.engine import AIEngine
from ai.text_renderer import put_chinese_text, draw_panel


def draw_ranking_panel(frame, rankings, start_time):
    """绘制中文排名面板"""
    if not rankings:
        return frame
    
    panel_x = 15
    panel_y = 50
    panel_w = 300
    row_h = 42
    header_h = 40
    
    num_ranks = min(len(rankings), 8)
    panel_h = header_h + num_ranks * row_h + 10
    
    frame = draw_panel(frame, panel_x, panel_y, panel_w, panel_h)
    
    cv2.rectangle(frame, (panel_x, panel_y), 
                 (panel_x + panel_w, panel_y + header_h), 
                 (0, 140, 255), -1)
    frame = put_chinese_text(frame, "实时排名", (panel_x + 15, panel_y + 8),
                            color=(255, 255, 255), size=22, bg_color=(0, 140, 255))
    
    rank_colors = {1: (0, 215, 255), 2: (192, 192, 192), 3: (0, 140, 255)}
    
    for i, r in enumerate(rankings[:8]):
        y = panel_y + header_h + i * row_h + 5
        
        rank_color = rank_colors.get(r["rank"], (100, 100, 100))
        cv2.circle(frame, (panel_x + 25, y + 16), 15, rank_color, -1)
        frame = put_chinese_text(frame, str(r["rank"]), (panel_x + 25, y + 5),
                                color=(255, 255, 255), size=18, align="center")
        
        lane = r.get("lane")
        lane_text = f"{lane}号" if lane else "-"
        frame = put_chinese_text(frame, lane_text, (panel_x + 50, y + 8),
                                color=(200, 200, 200), size=16)
        
        color_bgr = r.get("color_bgr", (128, 128, 128))
        cv2.rectangle(frame, (panel_x + 100, y + 5), 
                     (panel_x + 125, y + 28), color_bgr, -1)
        cv2.rectangle(frame, (panel_x + 100, y + 5), 
                     (panel_x + 125, y + 28), (100, 100, 100), 1)
        
        color_name = r.get("color_name", "未知")
        frame = put_chinese_text(frame, color_name, (panel_x + 132, y + 8),
                                color=(255, 255, 255), size=15)
        
        if start_time is not None:
            elapsed = r["timestamp"] - start_time
            time_text = f"{elapsed:.2f}s"
        else:
            time_text = "-"
        frame = put_chinese_text(frame, time_text, (panel_x + 215, y + 8),
                                color=(0, 255, 100), size=16)
    
    return frame


def draw_status_bar(frame, fps, tracked_count, lane_count, race_started, paused=False):
    """绘制状态栏"""
    h, w = frame.shape[:2]
    
    frame = draw_panel(frame, 0, 0, w, 38, color=(25, 25, 45), alpha=0.85)
    
    frame = put_chinese_text(frame, f"FPS:{fps}", (10, 8), color=(0, 255, 0), size=18)
    frame = put_chinese_text(frame, f"目标:{tracked_count}", (110, 8), color=(255, 255, 0), size=18)
    frame = put_chinese_text(frame, f"选手:{lane_count}", (210, 8), color=(0, 200, 255), size=18)
    
    if paused:
        status_text = "已暂停"
        status_color = (0, 100, 255)
    elif race_started:
        status_text = "比赛中"
        status_color = (0, 0, 255)
    else:
        status_text = "准备中[按S开始]"
        status_color = (0, 255, 255)
    frame = put_chinese_text(frame, status_text, (w - 180, 8), color=status_color, size=18)


def draw_help_panel(frame):
    """绘制帮助"""
    h, w = frame.shape[:2]
    panel_x = w - 210
    panel_y = 48
    panel_w = 195
    panel_h = 115
    
    frame = draw_panel(frame, panel_x, panel_y, panel_w, panel_h)
    
    frame = put_chinese_text(frame, "操作说明", (panel_x + 10, panel_y + 8),
                            color=(0, 200, 255), size=16)
    
    items = ["S - 开始比赛", "R - 重置", "Q - 退出", "空格 - 暂停/继续"]
    for i, text in enumerate(items):
        frame = put_chinese_text(frame, text, (panel_x + 10, panel_y + 35 + i * 20),
                                color=(200, 200, 200), size=14)


def main():
    parser = argparse.ArgumentParser(description="追迹 - 竞速过线计时Demo")
    parser.add_argument("--video", type=str, default="0")
    parser.add_argument("--model", type=str, default="yolov8n.pt")
    parser.add_argument("--line-pos", type=float, default=0.7)
    parser.add_argument("--line-orientation", type=str, default="horizontal",
                       choices=["horizontal", "vertical"])
    parser.add_argument("--auto-start", type=int, default=0)
    parser.add_argument("--max-width", type=int, default=720)
    parser.add_argument("--max-height", type=int, default=900)
    parser.add_argument("--lane-direction", type=str, default="horizontal",
                       choices=["horizontal", "vertical"])
    parser.add_argument("--save", type=str, default="",
                       help="保存输出视频路径（如 output.mp4）")
    parser.add_argument("--save-frame", type=str, default="",
                       help="保存最终排名截图路径（如 result.jpg）")
    args = parser.parse_args()
    
    print("正在加载模型...")
    engine = AIEngine(model_path=args.model, mode="racing")
    if engine.lane_assigner:
        engine.lane_assigner.direction = args.lane_direction
    print("模型加载完成！")
    
    if args.video == "0":
        cap = cv2.VideoCapture(0)
    else:
        cap = cv2.VideoCapture(args.video)
    
    if not cap.isOpened():
        print(f"无法打开视频: {args.video}")
        return
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"原始视频: {width}x{height}, FPS: {fps:.1f}")
    
    if fps > 0:
        engine.set_video_fps(fps)
    
    scale = 1.0
    max_w = args.max_width if args.max_width > 0 else width
    max_h = args.max_height if args.max_height > 0 else height
    if width > max_w or height > max_h:
        scale = min(max_w / width, max_h / height)
        disp_w, disp_h = int(width * scale), int(height * scale)
        print(f"缩放到: {disp_w}x{disp_h}")
    else:
        disp_w, disp_h = width, height
    
    if args.line_orientation == "horizontal":
        line_y = int(disp_h * args.line_pos)
        engine.set_line(50, line_y, disp_w - 50, line_y, direction="both")
        print(f"终点线(横线): y={line_y}")
    else:
        line_x = int(disp_w * args.line_pos)
        engine.set_line(line_x, 50, line_x, disp_h - 50, direction="both")
        print(f"终点线(竖线): x={line_x}")
    
    print("\n按S开始 / 按R重置 / 空格暂停 / 按Q退出\n")
    
    # 视频输出
    writer = None
    if args.save:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_fps = fps if fps > 0 else 25
        writer = cv2.VideoWriter(args.save, fourcc, out_fps, (disp_w, disp_h))
        print(f"将保存输出视频到: {args.save}")
    
    frame_count = 0
    start_time = time.time()
    race_started = False
    race_start_time = None
    paused = False
    last_frame = None
    
    while True:
        if not paused:
            ret, frame = cap.read()
            if not ret:
                print("视频结束")
                break
        else:
            # 暂停时重复显示最后一帧
            if last_frame is not None:
                frame = last_frame.copy()
            else:
                continue
        
        last_frame = frame.copy()
        frame_count += 1
        
        if scale < 1.0:
            frame = cv2.resize(frame, (disp_w, disp_h))
        
        result = engine.process_frame(frame)
        annotated = result["annotated_frame"]
        
        if args.auto_start > 0 and frame_count >= args.auto_start and not race_started:
            race_started = True
            race_start_time = engine.video_frame_idx / engine.video_fps if engine.video_fps else time.time()
            lane_count = result.get("lane_count", 0)
            print(f"比赛开始！已分配{lane_count}名选手编号")
        
        tracked_count = len(result["tracked_objects"])
        lane_count = result.get("lane_count", 0)
        draw_status_bar(annotated, result["fps"], tracked_count, lane_count, race_started, paused)
        
        rankings = result.get("rankings", [])
        if rankings:
            annotated = draw_ranking_panel(annotated, rankings, race_start_time)
        
        draw_help_panel(annotated)
        
        # 暂停标志
        if paused:
            h, w = annotated.shape[:2]
            frame_overlay = annotated.copy()
            cv2.rectangle(frame_overlay, (0, 0), (w, h), (0, 0, 0), -1)
            annotated = cv2.addWeighted(frame_overlay, 0.4, annotated, 0.6, 0)
            annotated = put_chinese_text(annotated, "已暂停", (w // 2, h // 2),
                                        color=(0, 200, 255), size=48, align="center")
        
        # 保存输出视频
        if writer:
            writer.write(annotated)
        
        cv2.imshow("AI Tracking Demo", annotated)
        
        key = cv2.waitKey(1 if not paused else 100) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            engine.reset_race()
            race_started = False
            race_start_time = None
            print("已重置！")
        elif key == ord('s') and not race_started:
            race_started = True
            race_start_time = engine.video_frame_idx / engine.video_fps if engine.video_fps else time.time()
            print("比赛开始！")
        elif key == ord(' '):
            paused = not paused
            print("已暂停" if paused else "继续")
    
    # 保存最终排名截图
    if last_frame is not None and args.save_frame:
        final_frame = last_frame.copy()
        if scale < 1.0:
            final_frame = cv2.resize(final_frame, (disp_w, disp_h))
        
        result = engine.process_frame(final_frame)
        annotated = result["annotated_frame"]
        rankings = result.get("rankings", [])
        
        draw_status_bar(annotated, result["fps"], len(result["tracked_objects"]), 
                        result.get("lane_count", 0), race_started)
        if rankings:
            annotated = draw_ranking_panel(annotated, rankings, race_start_time)
        
        cv2.imwrite(args.save_frame, annotated)
        print(f"排名截图已保存: {args.save_frame}")
    
    if writer:
        writer.release()
    cap.release()
    cv2.destroyAllWindows()
    
    elapsed = time.time() - start_time
    print(f"\n总帧数: {frame_count}, 耗时: {elapsed:.1f}s, FPS: {frame_count/elapsed:.1f}")
    
    rankings = engine.line_detector.get_rankings() if engine.line_detector else []
    if rankings:
        print(f"\n{'='*50}")
        print(f"最终排名（{len(rankings)}人完赛）：")
        print(f"{'='*50}")
        for r in rankings:
            lane = f"{r['lane']}号" if r.get('lane') else "-"
            t = f"{r['timestamp']-race_start_time:.2f}s" if race_start_time is not None else "-"
            print(f"  第{r['rank']}名: {lane} {r['color_name']} #{r['id']} {t}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
