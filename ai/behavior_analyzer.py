"""
行为分析模块 - 基于轨迹的简单行为判断
负责：判断目标是正常行走、奔跑、逗留、还是长时间不动
"""
import time
from collections import defaultdict
import numpy as np


class BehaviorAnalyzer:
    def __init__(self):
        """初始化行为分析器"""
        # 目标行为历史 {track_id: [{"time": t, "behavior": str, "confidence": float}, ...]}
        self.behavior_history = defaultdict(list)
        # 当前行为状态 {track_id: current_behavior}
        self.current_behavior = {}
        # 异常事件列表
        self.anomaly_events = []
        
        # 行为阈值配置
        self.speed_threshold_walk = 50  # 行走速度阈值（像素/秒）
        self.speed_threshold_run = 150  # 奔跑速度阈值
        self.stay_duration_threshold = 30  # 逗留阈值（秒）
        self.stay_radius_threshold = 50  # 逗留半径阈值（像素）
        self.inactivity_threshold = 60  # 长时间不动阈值（秒）
        
        # 每个目标的起始位置 {track_id: (x, y, timestamp)}
        self.stay_start_pos = {}
        
    def update(self, tracked_objects):
        """
        更新一帧的行为分析
        :param tracked_objects: 追踪结果列表
        :return: 异常事件列表
        """
        current_time = time.time()
        new_anomalies = []
        
        for obj in tracked_objects:
            track_id = obj["id"]
            center = obj["center"]
            speed = obj.get("speed", (0, 0))
            speed_magnitude = np.sqrt(speed[0]**2 + speed[1]**2)
            
            # 判断行为类型
            if speed_magnitude < 5:
                behavior = "stationary"  # 静止
            elif speed_magnitude < self.speed_threshold_walk:
                behavior = "walking"  # 行走
            elif speed_magnitude < self.speed_threshold_run:
                behavior = "fast_walking"  # 快走
            else:
                behavior = "running"  # 奔跑
            
            # 检测逗留
            if track_id not in self.stay_start_pos:
                self.stay_start_pos[track_id] = (center[0], center[1], current_time)
            else:
                sx, sy, st = self.stay_start_pos[track_id]
                dist = np.sqrt((center[0] - sx)**2 + (center[1] - sy)**2)
                duration = current_time - st
                
                if dist < self.stay_radius_threshold and duration > self.stay_duration_threshold:
                    behavior = "loitering"  # 逗留
                    
                    # 逗留超过阈值，记录异常
                    if duration > self.inactivity_threshold:
                        event = {
                            "id": track_id,
                            "type": "loitering",
                            "timestamp": current_time,
                            "description": f"目标#{track_id}在同一位置逗留了{int(duration)}秒",
                            "severity": "warning"
                        }
                        if not any(e["id"] == track_id and e["type"] == "loitering" 
                                  for e in self.anomaly_events[-10:]):
                            self.anomaly_events.append(event)
                            new_anomalies.append(event)
                elif dist > self.stay_radius_threshold * 2:
                    # 目标移动了，重置逗留起点
                    self.stay_start_pos[track_id] = (center[0], center[1], current_time)
            
            # 检测突然奔跑（可能是异常）
            if behavior == "running":
                event = {
                    "id": track_id,
                    "type": "sudden_run",
                    "timestamp": current_time,
                    "description": f"目标#{track_id}突然快速移动",
                    "severity": "info"
                }
                if not any(e["id"] == track_id and e["type"] == "sudden_run"
                          for e in self.anomaly_events[-5:]):
                    self.anomaly_events.append(event)
                    new_anomalies.append(event)
            
            # 记录行为历史
            self.behavior_history[track_id].append({
                "time": current_time,
                "behavior": behavior,
                "speed": speed_magnitude
            })
            
            # 只保留最近300条记录
            if len(self.behavior_history[track_id]) > 300:
                self.behavior_history[track_id] = self.behavior_history[track_id][-300:]
            
            self.current_behavior[track_id] = behavior
        
        return new_anomalies
    
    def get_behavior(self, track_id):
        """获取指定目标的当前行为"""
        return self.current_behavior.get(track_id, "unknown")
    
    def get_behavior_label(self, behavior):
        """获取行为的中文标签"""
        labels = {
            "stationary": "静止",
            "walking": "行走",
            "fast_walking": "快走",
            "running": "奔跑",
            "loitering": "逗留"
        }
        return labels.get(behavior, behavior)
    
    def get_summary(self):
        """获取行为统计摘要"""
        behavior_counts = defaultdict(int)
        for behavior in self.current_behavior.values():
            behavior_counts[behavior] += 1
        
        return {
            "total_objects": len(self.current_behavior),
            "behavior_distribution": dict(behavior_counts),
            "anomaly_count": len(self.anomaly_events),
            "recent_anomalies": self.anomaly_events[-10:]
        }
    
    def draw_behavior_labels(self, frame, tracked_objects):
        """在帧上绘制行为标签"""
        import cv2
        result = frame.copy()
        
        for obj in tracked_objects:
            track_id = obj["id"]
            x1, y1, x2, y2 = obj["bbox"]
            behavior = self.get_behavior(track_id)
            label = self.get_behavior_label(behavior)
            
            # 行为颜色
            colors = {
                "stationary": (255, 255, 0),   # 黄色
                "walking": (0, 255, 0),        # 绿色
                "fast_walking": (0, 255, 255), # 青色
                "running": (0, 0, 255),        # 红色
                "loitering": (255, 0, 255)     # 紫色
            }
            color = colors.get(behavior, (255, 255, 255))
            
            cv2.putText(result, label, (x1, y2 + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return result
