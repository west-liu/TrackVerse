"""
AI 引擎主模块 - 整合所有CV算法
提供统一的接口供后端调用
"""
import cv2
import numpy as np
import time

from .tracker import MultiObjectTracker
from .line_crossing import LineCrossingDetector
from .crowd_counter import CrowdCounter
from .behavior_analyzer import BehaviorAnalyzer
from .clothing_color import ClothingColorDetector
from .lane_assigner import LaneAssigner


class AIEngine:
    def __init__(self, model_path="yolov8n.pt", mode="racing"):
        """
        初始化AI引擎
        :param model_path: YOLO模型路径
        :param mode: 运行模式 "racing" | "crowd" | "behavior" | "all"
        """
        self.mode = mode
        self.tracker = MultiObjectTracker(model_path=model_path)
        
        # 默认配置（可通过API修改）
        self.line_detector = None
        self.crowd_counter = None
        self.behavior_analyzer = None
        self.color_detector = None
        self.lane_assigner = None
        
        if mode in ["racing", "all"]:
            # 默认终点线（画面底部）
            self.line_detector = LineCrossingDetector(
                line_start=(100, 400),
                line_end=(500, 400),
                direction="both"
            )
            # 衣服颜色识别
            self.color_detector = ClothingColorDetector(cache_frames=30)
            # 跑道分配器
            self.lane_assigner = LaneAssigner(num_lanes=20, direction="horizontal")
        
        if mode in ["crowd", "all"]:
            # 默认统计区域（画面中央）
            self.crowd_counter = CrowdCounter(
                region_points=[(200, 100), (400, 100), (400, 300), (200, 300)]
            )
        
        if mode in ["behavior", "all"]:
            self.behavior_analyzer = BehaviorAnalyzer()
        
        # 帧率统计
        self.frame_count = 0
        self.fps = 0
        self.last_fps_time = time.time()
        
        # 视频时间（用帧数/fps计算，避免CPU慢导致时间不准）
        self.video_fps = None
        self.video_frame_idx = 0
    
    def set_line(self, start_x, start_y, end_x, end_y, direction="both"):
        """设置过线检测线"""
        self.line_detector = LineCrossingDetector(
            line_start=(start_x, start_y),
            line_end=(end_x, end_y),
            direction=direction
        )
    
    def set_region(self, points):
        """设置客流统计区域"""
        self.crowd_counter = CrowdCounter(region_points=points)
    
    def reset_race(self):
        """重置比赛"""
        if self.line_detector:
            self.line_detector.reset()
        if self.color_detector:
            self.color_detector.reset()
        if self.lane_assigner:
            self.lane_assigner.reset()
    
    def start_race(self):
        """开始比赛（记录开始时间，不再锁定跑道）"""
        pass
    
    def set_video_fps(self, fps):
        """设置视频FPS（用于帧时间计算）"""
        self.video_fps = fps
    
    def process_frame(self, frame):
        """
        处理单帧图像
        :param frame: OpenCV BGR图像
        :return: 处理结果字典
        """
        self.video_frame_idx += 1
        
        # 计算视频时间（帧索引/fps）
        if self.video_fps:
            video_time = self.video_frame_idx / self.video_fps
        else:
            video_time = time.time()
        
        result = {
            "timestamp": video_time,
            "tracked_objects": [],
            "frame": frame,
        }
        
        # 1. 目标检测与追踪
        tracked_objects = self.tracker.track_frame(frame)
        result["tracked_objects"] = tracked_objects
        
        # 1.5 衣服颜色识别（竞速模式）
        if self.color_detector:
            tracked_objects = self.color_detector.detect(frame, tracked_objects)
            result["tracked_objects"] = tracked_objects
        
        # 1.6 跑道分配（竞速模式）
        if self.lane_assigner:
            tracked_objects = self.lane_assigner.assign_lanes(tracked_objects)
            result["tracked_objects"] = tracked_objects
            result["lane_count"] = self.lane_assigner.get_assigned_count()
        
        # 2. 过线检测（竞速模式）
        if self.line_detector:
            crossings = self.line_detector.update(tracked_objects, timestamp=video_time)
            result["crossings"] = crossings
            result["rankings"] = self.line_detector.get_rankings()
        
        # 3. 客流统计（客流模式）
        if self.crowd_counter:
            crowd_stats = self.crowd_counter.update(tracked_objects)
            result["crowd_stats"] = crowd_stats
        
        # 4. 行为分析（行为模式）
        if self.behavior_analyzer:
            anomalies = self.behavior_analyzer.update(tracked_objects)
            result["anomalies"] = anomalies
            result["behavior_summary"] = self.behavior_analyzer.get_summary()
        
        # 5. 计算FPS
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:
            self.fps = self.frame_count / (current_time - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = current_time
        result["fps"] = round(self.fps, 1)
        
        # 6. 绘制结果
        result["annotated_frame"] = self._draw_results(frame, result)
        
        return result
    
    def _draw_results(self, frame, result):
        """在帧上绘制所有结果"""
        annotated = frame.copy()
        
        # 绘制追踪结果
        annotated = self.tracker.draw_results(annotated, result["tracked_objects"])
        
        # 绘制过线
        if self.line_detector:
            annotated = self.line_detector.draw_line(annotated)
        
        # 绘制客流区域
        if self.crowd_counter:
            annotated = self.crowd_counter.draw_region(annotated)
        
        # 绘制行为标签
        if self.behavior_analyzer:
            annotated = self.behavior_analyzer.draw_behavior_labels(
                annotated, result["tracked_objects"]
            )
        
        # 绘制FPS
        cv2.putText(annotated, f"FPS: {result['fps']}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        return annotated
    
    def get_status(self):
        """获取当前状态"""
        status = {
            "mode": self.mode,
            "fps": self.fps,
            "tracked_count": len(self.tracker.last_seen),
        }
        
        if self.line_detector:
            status["race_rankings"] = self.line_detector.get_rankings()
            status["race_finished_count"] = len(self.line_detector.rankings)
        
        if self.crowd_counter:
            status["crowd_stats"] = self.crowd_counter.get_current_stats()
        
        if self.behavior_analyzer:
            status["behavior_summary"] = self.behavior_analyzer.get_summary()
        
        return status
