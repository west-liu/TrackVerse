# 追迹 (Trace) - 基于eufy摄像头的多目标智能追踪系统

> Anker首届黑客松挑战赛 - 智能安防赛道

## 项目简介

"追迹"是一个基于eufy SoloCam E30摄像头的多目标智能追踪系统。通过YOLOv8目标检测 + ByteTrack多目标追踪，实现过线计时、颜色识别、客流统计、行为分析等AI能力。

## Demo效果

以路跑比赛为例，系统实现了：
- 多人实时追踪（8-20人同时追踪）
- 过线自动计时（精度0.01秒）
- 实时排名生成
- 选手编号分配
- 衣服颜色识别（红/黑/白/黄/灰等）

## 技术架构

```
eufy SoloCam E30 (Web SDK取流)
        ↓ 截图帧
    YOLOv8 目标检测          ← 找到人
        ↓
    ByteTrack 多目标追踪      ← 追踪同一个人
        ↓
    ┌──────────────────┐
    │  过线检测+计时    │ ← 比赛计时
    │  颜色识别(HSV)    │ ← 人员分类
    │  选手编号分配     │ ← 位置管理
    │  客流统计         │ ← 区域监控
    │  行为分析         │ ← 异常检测
    └──────────────────┘
        ↓
    可视化输出 + 排名面板
```

## 核心技术

| 模块 | 技术 | 说明 |
|------|------|------|
| 目标检测 | YOLOv8n | 每帧检测画面中的人，输出位置框+置信度 |
| 多目标追踪 | ByteTrack | 跨帧关联同一人，分配唯一追踪ID |
| 颜色识别 | HSV色彩空间 | 在检测框区域内分析主色调 |
| 过线计时 | 几何交叉判断 | 判断目标中心点是否穿过终点线 |
| 选手编号 | 位置排序 | 起跑时按位置从左到右分配1号、2号... |
| 行为分析 | 速度+轨迹分析 | 检测奔跑、逗留、静止等行为 |

## 代码结构

```
├── ai/                          # 核心AI算法
│   ├── engine.py               # AI引擎 - 协调所有模块
│   ├── tracker.py               # YOLO检测 + ByteTrack追踪
│   ├── line_crossing.py         # 过线检测 + 计时排名
│   ├── clothing_color.py       # 衣服颜色识别(HSV)
│   ├── lane_assigner.py        # 选手编号分配
│   ├── crowd_counter.py        # 客流统计
│   ├── behavior_analyzer.py    # 行为分析
│   └── text_renderer.py        # 中文渲染(PIL)
├── backend/
│   └── main.py                 # FastAPI后端服务
├── demo_racing.py              # 竞速Demo入口
├── demo_crowd.py               # 客流Demo入口
├── requirements.txt            # Python依赖
└── screenshots/               # Demo截图和视频
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行竞速Demo（用视频文件）
python demo_racing.py --video your_video.mp4 --line-orientation vertical --line-pos 0.5 --auto-start 1 --lane-direction vertical

# 运行竞速Demo（用摄像头）
python demo_racing.py --video 0

# 保存Demo结果
python demo_racing.py --video your_video.mp4 --save output.mp4 --save-frame result.jpg
```

## 操作说明

| 按键 | 功能 |
|------|------|
| S | 开始比赛（锁定选手编号） |
| R | 重置比赛 |
| 空格 | 暂停/继续 |
| Q | 退出 |

## 硬件选型

| 设备 | 型号 | 能力 |
|------|------|------|
| 主摄像头 | eufy SoloCam E30 (T8171) | 360°云台、AI自动追踪、2K画面 |
| 辅助摄像头 | eufy Video Doorbell E340 (T8214) | 双摄模式、下摄视角 |

## 技术约束

- App SDK：事件 → 缩略图 → AI分析
- Web SDK：取流 → 截图 → AI分析
- 不支持实时视频流分析，采用帧截图分析模式

## 团队

- 刘云龙 - 算法+后端+架构
- 李雪微 - UI设计
- 董哲宇 - 前端开发
- 朱依静 - 客流模块+文案
