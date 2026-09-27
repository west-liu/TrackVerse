"""
衣服颜色识别模块
负责：检测目标上半身的主色调，映射为颜色名称
"""
import cv2
import numpy as np


# 颜色名称映射（HSV范围）
COLOR_RANGES = [
    ("红色", [(0, 100, 100), (10, 255, 255)]),
    ("红色", [(170, 100, 100), (180, 255, 255)]),
    ("橙色", [(10, 100, 100), (25, 255, 255)]),
    ("黄色", [(25, 100, 100), (35, 255, 255)]),
    ("绿色", [(35, 100, 100), (85, 255, 255)]),
    ("青色", [(85, 100, 100), (100, 255, 255)]),
    ("蓝色", [(100, 100, 100), (130, 255, 255)]),
    ("紫色", [(130, 100, 100), (160, 255, 255)]),
    ("粉色", [(160, 50, 200), (170, 150, 255)]),
]

# BGR颜色值（用于绘图）
COLOR_BGR = {
    "红色": (0, 0, 255),
    "橙色": (0, 165, 255),
    "黄色": (0, 255, 255),
    "绿色": (0, 255, 0),
    "青色": (255, 255, 0),
    "蓝色": (255, 0, 0),
    "紫色": (255, 0, 255),
    "粉色": (203, 192, 255),
    "黑色": (0, 0, 0),
    "白色": (255, 255, 255),
    "灰色": (128, 128, 128),
    "未知": (128, 128, 128),
}


def detect_dominant_color(frame, bbox, upper_body_ratio=0.5):
    """
    检测目标上半身的主色调
    :param frame: OpenCV BGR图像
    :param bbox: 边界框 [x1, y1, x2, y2]
    :param upper_body_ratio: 上半身占比（0.5表示上半部分）
    :return: (颜色名称, BGR颜色值, 置信度)
    """
    x1, y1, x2, y2 = bbox
    h = y2 - y1
    w = x2 - x1
    
    if h < 20 or w < 20:
        return "未知", COLOR_BGR["未知"], 0.0
    
    # 只取上半身（衣服区域）
    upper_y2 = int(y1 + h * upper_body_ratio)
    # 缩小一点，避开边界框边缘
    margin_x = int(w * 0.2)
    margin_y = int(h * 0.05)
    
    roi = frame[y1 + margin_y:upper_y2, x1 + margin_x:x2 - margin_x]
    
    if roi.size == 0 or roi.shape[0] < 10 or roi.shape[1] < 10:
        return "未知", COLOR_BGR["未知"], 0.0
    
    # 转换到HSV空间
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # 先判断黑/白/灰（低饱和度或高亮度）
    h, s, v = cv2.split(hsv)
    
    # 白色：高亮度，低饱和度
    white_mask = (s < 40) & (v > 200)
    white_ratio = np.sum(white_mask) / white_mask.size
    
    # 黑色：低亮度
    black_mask = v < 50
    black_ratio = np.sum(black_mask) / black_mask.size
    
    # 灰色：低饱和度，中等亮度
    gray_mask = (s < 30) & (v >= 50) & (v <= 200)
    gray_ratio = np.sum(gray_mask) / gray_mask.size
    
    # 如果黑白灰占比高，直接返回
    if white_ratio > 0.4:
        return "白色", COLOR_BGR["白色"], white_ratio
    if black_ratio > 0.4:
        return "黑色", COLOR_BGR["黑色"], black_ratio
    if gray_ratio > 0.4:
        return "灰色", COLOR_BGR["灰色"], gray_ratio
    
    # 检测彩色（只考虑有一定饱和度的像素）
    color_scores = {}
    total_color_pixels = 0
    
    for color_name, (lower, upper) in COLOR_RANGES:
        lower_np = np.array(lower, dtype=np.uint8)
        upper_np = np.array(upper, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_np, upper_np)
        count = np.sum(mask > 0)
        total_color_pixels += count
        if color_name in color_scores:
            color_scores[color_name] += count
        else:
            color_scores[color_name] = count
    
    if total_color_pixels < 100:
        # 彩色像素太少，可能是黑白灰
        if white_ratio >= black_ratio and white_ratio >= gray_ratio:
            return "白色", COLOR_BGR["白色"], white_ratio
        elif black_ratio >= gray_ratio:
            return "黑色", COLOR_BGR["黑色"], black_ratio
        else:
            return "灰色", COLOR_BGR["灰色"], gray_ratio
    
    # 找出占比最高的颜色
    best_color = max(color_scores, key=color_scores.get)
    best_score = color_scores[best_color]
    confidence = best_score / (roi.shape[0] * roi.shape[1])
    
    return best_color, COLOR_BGR[best_color], float(confidence)


class ClothingColorDetector:
    """衣服颜色检测器（带缓存，避免每帧重复计算）"""
    
    def __init__(self, cache_frames=30):
        """
        :param cache_frames: 缓存帧数，每N帧更新一次颜色
        """
        self.cache_frames = cache_frames
        self.color_cache = {}  # {track_id: (color_name, color_bgr, confidence, frame_count)}
        self.frame_counters = {}  # {track_id: frames_since_update}
    
    def reset(self):
        """重置缓存"""
        self.color_cache = {}
        self.frame_counters = {}
    
    def detect(self, frame, tracked_objects):
        """
        检测一批目标的衣服颜色
        :param frame: OpenCV BGR图像
        :param tracked_objects: 追踪结果列表
        :return: 更新后的追踪结果（添加了color字段）
        """
        current_ids = set()
        
        for obj in tracked_objects:
            track_id = obj["id"]
            current_ids.add(track_id)
            
            # 更新帧计数
            if track_id not in self.frame_counters:
                self.frame_counters[track_id] = 0
            
            self.frame_counters[track_id] += 1
            
            # 需要更新颜色（首次出现或达到缓存帧数）
            if track_id not in self.color_cache or self.frame_counters[track_id] >= self.cache_frames:
                color_name, color_bgr, confidence = detect_dominant_color(frame, obj["bbox"])
                self.color_cache[track_id] = (color_name, color_bgr, confidence)
                self.frame_counters[track_id] = 0
            
            # 添加颜色信息
            color_name, color_bgr, confidence = self.color_cache[track_id]
            obj["color_name"] = color_name
            obj["color_bgr"] = color_bgr
            obj["color_confidence"] = confidence
        
        # 清理已经消失的目标
        disappeared = set(self.color_cache.keys()) - current_ids
        for tid in disappeared:
            del self.color_cache[tid]
            del self.frame_counters[tid]
        
        return tracked_objects
