"""
中文渲染工具 - 用PIL在OpenCV画面上绘制中文
解决cv2.putText不支持中文的问题
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

# Windows系统字体路径
FONT_PATHS = [
    "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",     # 黑体
    "C:/Windows/Fonts/simsun.ttc",     # 宋体
    "C:/Windows/Fonts/Deng.ttf",       # 等线
]

_font_cache = {}

def _get_font(size):
    """获取字体（带缓存）"""
    if size in _font_cache:
        return _font_cache[size]
    
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[size] = font
                return font
            except:
                continue
    
    # 兜底：默认字体
    font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def put_chinese_text(img, text, position, color=(255, 255, 255), size=20, bg_color=None, align="left"):
    """
    在OpenCV图像上绘制中文文字
    :param img: OpenCV BGR图像
    :param text: 要绘制的文字
    :param position: (x, y) 左上角位置
    :param color: 文字颜色 (B, G, R)
    :param size: 字体大小
    :param bg_color: 背景颜色 (B, G, R)，None为透明
    :param align: 对齐方式 "left" | "center" | "right"
    :return: 绘制后的图像
    """
    # OpenCV BGR -> PIL RGB
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    font = _get_font(size)
    
    # 计算文字尺寸
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x, y = position
    if align == "center":
        x = x - text_w // 2
    elif align == "right":
        x = x - text_w
    
    # 绘制背景
    if bg_color is not None:
        # BGR -> RGB
        bg_rgb = (bg_color[2], bg_color[1], bg_color[0])
        draw.rectangle([x - 2, y - 2, x + text_w + 4, y + text_h + 4], fill=bg_rgb)
    
    # BGR -> RGB
    rgb_color = (color[2], color[1], color[0])
    draw.text((x, y), text, font=font, fill=rgb_color)
    
    # PIL RGB -> OpenCV BGR
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def draw_panel(img, x, y, w, h, color=(20, 20, 40), alpha=0.8):
    """绘制半透明面板"""
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
    return cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
