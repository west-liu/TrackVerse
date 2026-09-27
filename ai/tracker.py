"""
多目标追踪模块 - 基于 YOLOv8 + ByteTrack
负责：目标检测 + 多目标追踪，输出每个目标的轨迹
"""
import cv2
from .text_renderer import put_chinese_text
import numpy as np
from ultralytics import YOLO
from collections import defaultdict
import time


class MultiObjectTracker:
    def __init__(self, model_path="yolov8n.pt", conf_threshold=0.3, track_classes=None):
        """
        初始化多目标追踪器
        :param model_path: YOLO模型路径
        :param conf_threshold: 置信度阈值
        :param track_classes: 要追踪的类别列表，None表示追踪所有
        """
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.track_classes = track_classes
        
        # 存储每个目标的历史轨迹 {track_id: [(x, y, timestamp), ...]}
        self.tracks = defaultdict(list)
        # 存储每个目标的速度 {track_id: (vx, vy)}
        self.speeds = defaultdict(lambda: (0, 0))
        # 目标最后出现的帧
        self.last_seen = {}
        # 目标最大消失帧数（超过则清除轨迹）
        self.max_disappeared = 30
        
    def track_frame(self, frame):
        """
        处理单帧，进行目标检测和追踪
        :param frame: OpenCV图像 (BGR)
        :return: 追踪结果列表 [{"id": int, "bbox": [x1,y1,x2,y2], "class": int, "conf": float, "center": (cx, cy)}]
        """
        results = self.model.track(
            frame, 
            persist=True, 
            conf=self.conf_threshold,
            classes=self.track_classes,
            verbose=False
        )
        
        tracked_objects = []
        
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()  # 边界框
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)  # 追踪ID
            confs = results[0].boxes.conf.cpu().numpy()  # 置信度
            classes = results[0].boxes.cls.cpu().numpy().astype(int)  # 类别
            
            current_time = time.time()
            
            for box, track_id, conf, cls in zip(boxes, track_ids, confs, classes):
                x1, y1, x2, y2 = box
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                center = (cx, cy)
                
                # 更新轨迹
                self.tracks[track_id].append((cx, cy, current_time))
                # 只保留最近100个点
                if len(self.tracks[track_id]) > 100:
                    self.tracks[track_id] = self.tracks[track_id][-100:]
                
                # 计算速度（基于最近10帧）
                if len(self.tracks[track_id]) >= 5:
                    recent = self.tracks[track_id][-5:]
                    dx = recent[-1][0] - recent[0][0]
                    dy = recent[-1][1] - recent[0][1]
                    dt = recent[-1][2] - recent[0][2]
                    if dt > 0:
                        self.speeds[track_id] = (dx / dt, dy / dt)
                
                self.last_seen[track_id] = current_time
                
                tracked_objects.append({
                    "id": int(track_id),
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "class": int(cls),
                    "class_name": self.model.names[int(cls)],
                    "conf": float(conf),
                    "center": center,
                    "speed": self.speeds[track_id]
                })
        
        # 清理长时间消失的目标
        current_time = time.time()
        to_remove = []
        for track_id, last_time in self.last_seen.items():
            if current_time - last_time > self.max_disappeared / 30:  # 假设30fps
                to_remove.append(track_id)
        for track_id in to_remove:
            if track_id in self.tracks:
                del self.tracks[track_id]
            if track_id in self.speeds:
                del self.speeds[track_id]
            del self.last_seen[track_id]
        
        return tracked_objects
    
    def get_track_history(self, track_id, max_points=50):
        """获取指定目标的历史轨迹"""
        if track_id in self.tracks:
            history = self.tracks[track_id][-max_points:]
            return [(p[0], p[1]) for p in history]
        return []
    
    def draw_results(self, frame, tracked_objects):
        """在帧上绘制检测结果"""
        result_frame = frame.copy()
        
        # 绘制每个目标
        for obj in tracked_objects:
            x1, y1, x2, y2 = obj["bbox"]
            track_id = obj["id"]
            conf = obj["conf"]
            cls_name = obj["class_name"]
            
            # 优先用衣服颜色作为框的颜色
            color = obj.get("color_bgr", self._get_color(track_id))
            
            # 画边界框
            cv2.rectangle(result_frame, (x1, y1), (x2, y2), color, 2)
            
            # 构建标签
            lane = obj.get("lane")
            color_name = obj.get("color_name", "")
            
            label_parts = []
            if lane:
                label_parts.append(f"{lane}号")
            if color_name and color_name != "未知":
                label_parts.append(color_name)
            label_parts.append(f"#{track_id}")
            label = " ".join(label_parts)
            
            # 画标签背景和文字（用PIL渲染中文）
            result_frame = put_chinese_text(result_frame, label, (x1, y1 - 22),
                                           color=(255, 255, 255), size=16, bg_color=color)
            
            # 画中心点
            cx, cy = obj["center"]
            cv2.circle(result_frame, (cx, cy), 4, color, -1)
            
            # 画轨迹
            history = self.get_track_history(track_id, 30)
            for i in range(1, len(history)):
                pt1 = history[i - 1]
                pt2 = history[i]
                cv2.line(result_frame, pt1, pt2, color, 2)
        
        return result_frame
    
    def _get_color(self, track_id):
        """根据ID生成固定颜色"""
        np.random.seed(track_id)
        return tuple(np.random.randint(0, 255, 3).tolist())
