"""
过线计时模块 - 虚拟终点线检测与排名
负责：检测目标是否跨过设定的线，记录时间，生成排名
"""
import time
from collections import defaultdict


class LineCrossingDetector:
    def __init__(self, line_start, line_end, direction="both"):
        """
        初始化过线检测器
        :param line_start: 线段起点 (x, y)
        :param line_end: 线段终点 (x, y)
        :param direction: 检测方向 "both" | "left_to_right" | "right_to_left" | "top_to_bottom" | "bottom_to_top"
        """
        self.line_start = line_start
        self.line_end = line_end
        self.direction = direction
        
        # 记录每个目标上一帧的位置 {track_id: (x, y)}
        self.prev_positions = {}
        # 记录每个目标的过线记录 {track_id: [timestamp, ...]}
        self.crossing_records = defaultdict(list)
        # 排名列表 [(track_id, timestamp, rank), ...]
        self.rankings = []
        # 已完成过线的目标集合（只记第一次）
        self.crossed_ids = set()
        
    def reset(self):
        """重置检测器（新一轮计时）"""
        self.prev_positions = {}
        self.crossing_records = defaultdict(list)
        self.rankings = []
        self.crossed_ids = set()
    
    def _is_crossing(self, prev_pos, curr_pos):
        """
        判断目标是否跨过了线
        :return: (是否过线, 过线方向)
        """
        x1, y1 = self.line_start
        x2, y2 = self.line_end
        px, py = prev_pos
        cx, cy = curr_pos
        
        # 计算线段方程 Ax + By + C = 0
        A = y2 - y1
        B = x1 - x2
        C = x2 * y1 - x1 * y2
        
        # 计算点在线的哪一侧
        prev_side = A * px + B * py + C
        curr_side = A * cx + B * cy + C
        
        # 符号变化表示跨过了线
        if prev_side * curr_side < 0:
            # 判断方向
            if self.direction == "both":
                return True, "crossing"
            elif self.direction == "left_to_right" and curr_side > prev_side:
                return True, "left_to_right"
            elif self.direction == "right_to_left" and curr_side < prev_side:
                return True, "right_to_left"
            elif self.direction == "top_to_bottom" and curr_side > prev_side:
                return True, "top_to_bottom"
            elif self.direction == "bottom_to_top" and curr_side < prev_side:
                return True, "bottom_to_top"
        
        return False, None
    
    def update(self, tracked_objects, timestamp=None):
        """
        更新一帧的过线检测
        :param tracked_objects: 追踪结果列表，来自 MultiObjectTracker
        :param timestamp: 当前时间戳（视频帧时间），None则用系统时间
        :return: 本帧新过线的目标列表 [{"id": int, "timestamp": float, "rank": int}]
        """
        new_crossings = []
        current_time = timestamp if timestamp is not None else time.time()
        
        for obj in tracked_objects:
            track_id = obj["id"]
            cx, cy = obj["center"]
            
            if track_id in self.prev_positions:
                prev_pos = self.prev_positions[track_id]
                is_crossing, direction = self._is_crossing(prev_pos, (cx, cy))
                
                if is_crossing and track_id not in self.crossed_ids:
                    # 记录过线
                    self.crossed_ids.add(track_id)
                    rank = len(self.rankings) + 1
                    record = {
                        "id": track_id,
                        "timestamp": current_time,
                        "rank": rank,
                        "direction": direction,
                        "class_name": obj.get("class_name", "unknown"),
                        "lane": obj.get("lane", None),
                        "color_name": obj.get("color_name", "未知"),
                        "color_bgr": obj.get("color_bgr", (128, 128, 128)),
                    }
                    self.crossing_records[track_id].append(record)
                    self.rankings.append(record)
                    new_crossings.append(record)
            
            # 更新上一帧位置
            self.prev_positions[track_id] = (cx, cy)
        
        return new_crossings
    
    def get_rankings(self):
        """获取当前排名"""
        return sorted(self.rankings, key=lambda x: x["rank"])
    
    def get_results_summary(self):
        """获取比赛结果摘要"""
        rankings = self.get_rankings()
        if not rankings:
            return "暂无选手冲线"
        
        summary = f"🏁 比赛结果（共{len(rankings)}人完赛）：\n"
        for r in rankings:
            lane_str = f"{r['lane']}号 " if r.get('lane') else ""
            color_str = f"[{r['color_name']}]" if r.get('color_name') else ""
            summary += f"  第{r['rank']}名: {lane_str}{r['color_name']}选手 #{r['id']}\n"
        
        return summary
    
    def draw_line(self, frame, color=(0, 255, 0), thickness=3):
        """在帧上绘制检测线"""
        import cv2
        result = frame.copy()
        cv2.line(result, self.line_start, self.line_end, color, thickness)
        
        # 绘制方向箭头
        mid_x = (self.line_start[0] + self.line_end[0]) // 2
        mid_y = (self.line_start[1] + self.line_end[1]) // 2
        cv2.putText(result, "FINISH", (mid_x - 40, mid_y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        
        return result
