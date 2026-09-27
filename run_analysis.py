"""
自动化视频分析脚本
输入一个视频，自动生成：
1. 标注后的视频（带检测框+排名+标签）
2. 结果截图（最终排名画面）
3. 数据报告（JSON + CSV + HTML）
4. 检测日志（每帧每人详细数据）

用法：
    python run_analysis.py --video video/01_跑步比赛/16038578_2160_3840_30fps.mp4
    python run_analysis.py --video my_video.mp4 --line-orientation vertical --line-pos 0.5
"""
import cv2
import argparse
import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.engine import AIEngine
from ai.text_renderer import put_chinese_text, draw_panel


def draw_ranking_panel(frame, rankings, start_time):
    if not rankings:
        return frame
    panel_x, panel_y = 15, 50
    panel_w = 300
    row_h = 42
    header_h = 40
    num_ranks = min(len(rankings), 8)
    panel_h = header_h + num_ranks * row_h + 10
    frame = draw_panel(frame, panel_x, panel_y, panel_w, panel_h)
    cv2.rectangle(frame, (panel_x, panel_y), (panel_x + panel_w, panel_y + header_h), (0, 140, 255), -1)
    frame = put_chinese_text(frame, "实时排名", (panel_x + 15, panel_y + 8), color=(255, 255, 255), size=22, bg_color=(0, 140, 255))
    rank_colors = {1: (0, 215, 255), 2: (192, 192, 192), 3: (0, 140, 255)}
    for i, r in enumerate(rankings[:8]):
        y = panel_y + header_h + i * row_h + 5
        rank_color = rank_colors.get(r["rank"], (100, 100, 100))
        cv2.circle(frame, (panel_x + 25, y + 16), 15, rank_color, -1)
        frame = put_chinese_text(frame, str(r["rank"]), (panel_x + 25, y + 5), color=(255, 255, 255), size=18, align="center")
        lane = r.get("lane")
        lane_text = f"{lane}号" if lane else "-"
        frame = put_chinese_text(frame, lane_text, (panel_x + 50, y + 8), color=(200, 200, 200), size=16)
        color_bgr = r.get("color_bgr", (128, 128, 128))
        cv2.rectangle(frame, (panel_x + 100, y + 5), (panel_x + 125, y + 28), color_bgr, -1)
        cv2.rectangle(frame, (panel_x + 100, y + 5), (panel_x + 125, y + 28), (100, 100, 100), 1)
        color_name = r.get("color_name", "未知")
        frame = put_chinese_text(frame, color_name, (panel_x + 132, y + 8), color=(255, 255, 255), size=15)
        if start_time is not None:
            elapsed = r["timestamp"] - start_time
            time_text = f"{elapsed:.2f}s"
        else:
            time_text = "-"
        frame = put_chinese_text(frame, time_text, (panel_x + 215, y + 8), color=(0, 255, 100), size=16)
    return frame


def draw_status_bar(frame, fps, tracked_count, lane_count, race_started, paused=False):
    h, w = frame.shape[:2]
    frame = draw_panel(frame, 0, 0, w, 38, color=(25, 25, 45), alpha=0.85)
    frame = put_chinese_text(frame, f"FPS:{fps}", (10, 8), color=(0, 255, 0), size=18)
    frame = put_chinese_text(frame, f"目标:{tracked_count}", (110, 8), color=(255, 255, 0), size=18)
    frame = put_chinese_text(frame, f"选手:{lane_count}", (210, 8), color=(0, 200, 255), size=18)
    if paused:
        status_text, status_color = "已暂停", (0, 100, 255)
    elif race_started:
        status_text, status_color = "比赛中", (0, 0, 255)
    else:
        status_text, status_color = "准备中", (0, 255, 255)
    frame = put_chinese_text(frame, status_text, (w - 180, 8), color=status_color, size=18)


def generate_html_report(output_dir, video_name, stats, rankings, frame_logs):
    html_path = os.path.join(output_dir, "report.html")
    color_distribution = {}
    for r in rankings:
        c = r.get("color_name", "未知")
        color_distribution[c] = color_distribution.get(c, 0) + 1

    rankings_rows = ""
    for r in rankings:
        medal = ["🥇", "🥈", "🥉"][r["rank"]-1] if r["rank"] <= 3 else f"{r['rank']}"
        rankings_rows += f"""
        <tr>
            <td>{medal}</td>
            <td>{r.get('lane', '-')}</td>
            <td><span class="color-tag" style="background:rgb({r.get('color_bgr',(128,128,128))[2]},{r.get('color_bgr',(128,128,128))[1]},{r.get('color_bgr',(128,128,128))[0]})">{r.get('color_name','未知')}</span></td>
            <td>#{r['id']}</td>
            <td class="time">{r.get('timestamp', 0):.2f}s</td>
        </tr>"""

    color_bars = ""
    total = sum(color_distribution.values())
    for c, cnt in sorted(color_distribution.items(), key=lambda x: -x[1]):
        pct = cnt / total * 100 if total > 0 else 0
        color_bars += f'<div class="color-bar"><span class="color-label">{c}</span><div class="bar-bg"><div class="bar-fill" style="width:{pct}%"></div></div><span class="color-count">{cnt}人 ({pct:.0f}%)</span></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>追迹 - 视频分析报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #0f0f1e; color: #e0e0e0; padding: 20px; }}
.header {{ text-align: center; padding: 30px 0; border-bottom: 1px solid #2a2a4a; margin-bottom: 30px; }}
.header h1 {{ font-size: 28px; color: #a78bfa; }}
.header .subtitle {{ color: #6b7280; margin-top: 8px; font-size: 14px; }}
.section {{ background: #1a1a2e; border-radius: 12px; padding: 24px; margin-bottom: 20px; border: 1px solid #2a2a4a; }}
.section h2 {{ color: #a78bfa; font-size: 18px; margin-bottom: 16px; border-left: 3px solid #7c3aed; padding-left: 12px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; }}
.stat-card {{ background: #16213e; border-radius: 8px; padding: 16px; text-align: center; }}
.stat-card .value {{ font-size: 28px; font-weight: 700; color: #4ade80; }}
.stat-card .label {{ font-size: 12px; color: #6b7280; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 12px; text-align: center; border-bottom: 1px solid #2a2a4a; }}
th {{ color: #a78bfa; font-size: 13px; }}
td {{ font-size: 14px; }}
td.time {{ color: #4ade80; font-family: monospace; font-weight: 600; }}
.color-tag {{ padding: 2px 10px; border-radius: 12px; font-size: 12px; color: #fff; }}
.color-bar {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
.color-label {{ width: 60px; font-size: 13px; }}
.bar-bg {{ flex: 1; background: #2a2a4a; border-radius: 4px; height: 24px; overflow: hidden; }}
.bar-fill {{ background: linear-gradient(90deg, #7c3aed, #a78bfa); height: 100%; border-radius: 4px; }}
.color-count {{ width: 100px; font-size: 12px; color: #6b7280; }}
.screenshot {{ text-align: center; }}
.screenshot img {{ max-width: 100%; border-radius: 8px; border: 1px solid #2a2a4a; }}
.footer {{ text-align: center; color: #4b5563; font-size: 12px; padding: 20px 0; }}
</style>
</head>
<body>
<div class="header">
    <h1>🏃 追迹 - 视频分析报告</h1>
    <div class="subtitle">视频: {video_name} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
</div>

<div class="section">
    <h2>📊 基础统计</h2>
    <div class="stats-grid">
        <div class="stat-card"><div class="value">{stats['total_frames']}</div><div class="label">总帧数</div></div>
        <div class="stat-card"><div class="value">{stats['duration']:.1f}s</div><div class="label">视频时长</div></div>
        <div class="stat-card"><div class="value">{stats['avg_fps']:.1f}</div><div class="label">处理FPS</div></div>
        <div class="stat-card"><div class="value">{stats['max_tracked']}</div><div class="label">同帧最多目标</div></div>
        <div class="stat-card"><div class="value">{stats['total_unique_ids']}</div><div class="label">独立追踪ID数</div></div>
        <div class="stat-card"><div class="value">{len(rankings)}</div><div class="label">完赛人数</div></div>
    </div>
</div>

<div class="section">
    <h2>🏁 最终排名</h2>
    <table>
        <thead><tr><th>名次</th><th>选手编号</th><th>衣服颜色</th><th>追踪ID</th><th>冲线时间</th></tr></thead>
        <tbody>{rankings_rows}</tbody>
    </table>
</div>

<div class="section">
    <h2>🎨 颜色分布</h2>
    {color_bars}
</div>

<div class="section">
    <h2>📸 结果截图</h2>
    <div class="screenshot">
        <img src="result.jpg" alt="最终排名截图">
    </div>
</div>

<div class="footer">
    追迹系统 | 基于YOLOv8 + ByteTrack + HSV颜色识别 | Anker黑客松 2026
</div>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


def main():
    parser = argparse.ArgumentParser(description="追迹 - 自动化视频分析")
    parser.add_argument("--video", type=str, required=True, help="输入视频路径")
    parser.add_argument("--model", type=str, default="yolov8n.pt")
    parser.add_argument("--line-pos", type=float, default=0.5, help="终点线位置(0-1)")
    parser.add_argument("--line-orientation", type=str, default="vertical", choices=["horizontal", "vertical"])
    parser.add_argument("--auto-start", type=int, default=1, help="第几帧自动开始")
    parser.add_argument("--lane-direction", type=str, default="vertical", choices=["horizontal", "vertical"])
    parser.add_argument("--max-width", type=int, default=720)
    parser.add_argument("--max-height", type=int, default=900)
    parser.add_argument("--output-dir", type=str, default="", help="输出目录（默认: output/视频名/）")
    args = parser.parse_args()

    # 输出目录
    video_name = os.path.splitext(os.path.basename(args.video))[0]
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.join("output", video_name)
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 输出目录: {output_dir}")

    # 初始化
    print("正在加载模型...")
    engine = AIEngine(model_path=args.model, mode="racing")
    if engine.lane_assigner:
        engine.lane_assigner.direction = args.lane_direction
    print("模型加载完成！")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"无法打开视频: {args.video}")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    print(f"视频: {width}x{height}, {fps:.1f}fps, {duration:.1f}s, {total_frames}帧")

    if fps > 0:
        engine.set_video_fps(fps)

    # 缩放
    scale = 1.0
    max_w = args.max_width if args.max_width > 0 else width
    max_h = args.max_height if args.max_height > 0 else height
    if width > max_w or height > max_h:
        scale = min(max_w / width, max_h / height)
    disp_w, disp_h = int(width * scale), int(height * scale)

    # 终点线
    if args.line_orientation == "horizontal":
        line_y = int(disp_h * args.line_pos)
        engine.set_line(50, line_y, disp_w - 50, line_y, direction="both")
    else:
        line_x = int(disp_w * args.line_pos)
        engine.set_line(line_x, 50, line_x, disp_h - 50, direction="both")

    # 视频输出
    out_video_path = os.path.join(output_dir, "annotated.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_fps = fps if fps > 0 else 25
    writer = cv2.VideoWriter(out_video_path, fourcc, out_fps, (disp_w, disp_h))

    # 数据记录
    frame_logs = []
    all_ids = set()
    max_tracked = 0
    frame_count = 0
    start_time = time.time()
    race_started = False
    race_start_time = None
    last_frame = None

    print(f"\n开始分析...")
    print(f"=" * 50)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

        if scale < 1.0:
            frame = cv2.resize(frame, (disp_w, disp_h))

        result = engine.process_frame(frame)
        annotated = result["annotated_frame"]

        if args.auto_start > 0 and frame_count >= args.auto_start and not race_started:
            race_started = True
            race_start_time = engine.video_frame_idx / engine.video_fps if engine.video_fps else time.time()

        tracked_objects = result["tracked_objects"]
        tracked_count = len(tracked_objects)
        if tracked_count > max_tracked:
            max_tracked = tracked_count

        for obj in tracked_objects:
            all_ids.add(obj["id"])

        # 记录每帧数据
        frame_log = {
            "frame": frame_count,
            "timestamp": round(frame_count / fps, 3) if fps > 0 else frame_count,
            "tracked_count": tracked_count,
            "objects": [{
                "id": o["id"],
                "bbox": o["bbox"],
                "lane": o.get("lane"),
                "color": o.get("color_name", "未知"),
                "conf": round(o.get("conf", 0), 3)
            } for o in tracked_objects]
        }
        frame_logs.append(frame_log)

        # 绘制UI
        lane_count = result.get("lane_count", 0)
        draw_status_bar(annotated, result["fps"], tracked_count, lane_count, race_started)
        rankings = result.get("rankings", [])
        if rankings:
            annotated = draw_ranking_panel(annotated, rankings, race_start_time)

        writer.write(annotated)
        last_frame = annotated.copy()

        if frame_count % 50 == 0:
            print(f"  帧 {frame_count}/{total_frames} | 目标:{tracked_count} | FPS:{result['fps']:.1f}")

    # 保存最终截图
    result_path = os.path.join(output_dir, "result.jpg")
    if last_frame is not None:
        cv2.imwrite(result_path, last_frame)

    # 统计数据
    elapsed = time.time() - start_time
    avg_fps = frame_count / elapsed if elapsed > 0 else 0
    rankings = engine.line_detector.get_rankings() if engine.line_detector else []

    stats = {
        "video_name": os.path.basename(args.video),
        "video_resolution": f"{width}x{height}",
        "video_fps": round(fps, 1),
        "total_frames": frame_count,
        "duration": round(duration, 1),
        "analysis_time": round(elapsed, 1),
        "avg_fps": round(avg_fps, 1),
        "max_tracked": max_tracked,
        "total_unique_ids": len(all_ids),
        "total_rankings": len(rankings),
    }

    # JSON报告
    json_path = os.path.join(output_dir, "report.json")
    report = {
        "stats": stats,
        "rankings": [{**r, "timestamp": round(r["timestamp"] - race_start_time, 3) if race_start_time else r["timestamp"]} for r in rankings],
        "frame_logs_count": len(frame_logs),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # CSV日志
    csv_path = os.path.join(output_dir, "frame_log.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("frame,timestamp,tracked_count,object_ids,object_colors\n")
        for log in frame_logs:
            ids = "|".join(str(o["id"]) for o in log["objects"])
            colors = "|".join(o["color"] for o in log["objects"])
            f.write(f"{log['frame']},{log['timestamp']},{log['tracked_count']},{ids},{colors}\n")

    # HTML报告
    html_path = generate_html_report(output_dir, os.path.basename(args.video), stats, rankings, frame_logs)

    writer.release()
    cap.release()

    print(f"\n{'=' * 50}")
    print(f"✅ 分析完成！")
    print(f"{'=' * 50}")
    print(f"📁 输出目录: {output_dir}")
    print(f"   ├── annotated.mp4     ({os.path.getsize(out_video_path)//1024//1024}MB)  标注视频")
    print(f"   ├── result.jpg         ({os.path.getsize(result_path)//1024}KB)  最终截图")
    print(f"   ├── report.html         HTML可视化报告")
    print(f"   ├── report.json         JSON数据报告")
    print(f"   └── frame_log.csv       逐帧CSV日志")
    print(f"\n📊 统计:")
    print(f"   总帧数: {stats['total_frames']}")
    print(f"   视频时长: {stats['duration']}s")
    print(f"   处理速度: {stats['avg_fps']} FPS")
    print(f"   同帧最多目标: {stats['max_tracked']}")
    print(f"   独立追踪ID: {stats['total_unique_ids']}")
    print(f"   完赛人数: {stats['total_rankings']}")
    if rankings:
        print(f"\n🏁 最终排名:")
        for r in rankings[:8]:
            lane = f"{r.get('lane','?')}号" if r.get('lane') else "-"
            t = r["timestamp"] - race_start_time if race_start_time else r["timestamp"]
            print(f"   第{r['rank']}名: {lane} {r.get('color_name','?')} #{r['id']} {t:.2f}s")


if __name__ == "__main__":
    main()
