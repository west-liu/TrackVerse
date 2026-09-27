"""
客流统计模块 - 区域计数与停留分析
负责：统计进入/离开指定区域的目标数量，计算停留时长
"""
import time
from collections import defaultdict


class CrowdCounter:
    def __init__(self, region_points):
        """
        初始化客流统计器
        :param region_points: 区域多边形顶点列表 [(x1,y1), (x2,y2), ...]
        """
        self.region_points = region_points
        
        # 当前在区域内的目标 {track_id: enter_timestamp}
        self.inside_objects = {}
        # 总进入次数
        self.total_enter = 0
        # 总离开次数
        self.total_leave = 0
        # 历史停留记录 [(track_id, enter_time, leave_time, duration), ...]
        self.stay_records = []
        # 时段统计 {hour: count}
        self.hourly_stats = defaultdict(int)
        
    def reset(self):
        """重置统计"""
        self.inside_objects = {}
        self.total_enter = 0
        self.total_leave = 0
        self.stay_records = []
        self.hourly_stats = defaultdict(int)
    
    def _point_in_polygon(self, point, polygon):
        """判断点是否在多边形内（射线法）"""
        x, y = point
        n = len(polygon)
        inside = False
        
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
    def update(self, tracked_objects):
        """
        更新一帧的客流统计
        :param tracked_objects: 追踪结果列表
        :return: {"entered": [ids], "left": [ids], "current_count": int}
        """
        current_time = time.time()
        current_ids = set()
        entered = []
        left = []
        
        for obj in tracked_objects:
            track_id = obj["id"]
            cx, cy = obj["center"]
            current_ids.add(track_id)
            
            is_inside = self._point_in_polygon((cx, cy), self.region_points)
            
            if is_inside:
                if track_id not in self.inside_objects:
                    # 新进入
                    self.inside_objects[track_id] = current_time
                    self.total_enter += 1
                    entered.append(track_id)
                    # 时段统计
                    hour = int(time.strftime("%H", time.localtime(current_time)))
                    self.hourly_stats[hour] += 1
            else:
                if track_id in self.inside_objects:
                    # 离开
                    enter_time = self.inside_objects.pop(track_id)
                    duration = current_time - enter_time
                    self.total_leave += 1
                    self.stay_records.append({
                        "id": track_id,
                        "enter_time": enter_time,
                        "leave_time": current_time,
                        "duration": duration
                    })
                    left.append(track_id)
        
        # 处理消失的目标（可能离开画面了，也算离开）
        disappeared = []
        for track_id in list(self.inside_objects.keys()):
            if track_id not in current_ids:
                # 目标消失了，记录离开
                enter_time = self.inside_objects.pop(track_id)
                duration = current_time - enter_time
                self.total_leave += 1
                self.stay_records.append({
                    "id": track_id,
                    "enter_time": enter_time,
                    "leave_time": current_time,
                    "duration": duration,
                    "note": "disappeared"
                })
                disappeared.append(track_id)
        
        return {
            "entered": entered,
            "left": left,
            "disappeared": disappeared,
            "current_count": len(self.inside_objects),
            "total_enter": self.total_enter,
            "total_leave": self.total_leave
        }
    
    def get_current_stats(self):
        """获取当前统计数据"""
        durations = [r["duration"] for r in self.stay_records]
        avg_stay = sum(durations) / len(durations) if durations else 0
        
        return {
            "current_inside": len(self.inside_objects),
            "total_enter": self.total_enter,
            "total_leave": self.total_leave,
            "avg_stay_duration": round(avg_stay, 2),
            "hourly_stats": dict(self.hourly_stats)
        }
    
    def draw_region(self, frame, color=(255, 0, 0), thickness=2):
        """在帧上绘制统计区域"""
        import cv2
        import numpy as np
        result = frame.copy()
        
        points = np.array(self.region_points, np.int32)
        points = points.reshape((-1, 1, 2))
        cv2.polylines(result, [points], True, color, thickness)
        
        # 填充半透明
        overlay = result.copy()
        cv2.fillPoly(overlay, [points], (*color, 0.3))
        cv2.addWeighted(overlay, 0.3, result, 0.7, 0, result)
        
        # 标注区域名称
        if self.region_points:
            cx = sum(p[0] for p in self.region_points) // len(self.region_points)
            cy = sum(p[1] for p in self.region_points) // len(self.region_points)
            stats = self.get_current_stats()
            text = f"区域内: {stats['current_inside']}人"
            cv2.putText(result, text, (cx - 50, cy),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return result
