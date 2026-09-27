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
├── demo_racing.py              # 竞速Demo入口（实时窗口）
├── demo_crowd.py               # 客流Demo入口
├── run_analysis.py             # 自动化分析脚本（一键生成报告）
├── requirements.txt            # Python依赖
├── output/demo/                # 分析结果
│   ├── annotated.mp4           # 标注视频(16MB)
│   ├── demo_preview.mp4        # 压缩预览版(3.2MB)
│   ├── result.jpg              # 最终排名截图
│   ├── report.html             # HTML可视化报告
│   ├── report.json             # JSON数据报告
│   └── frame_log.csv           # 逐帧CSV日志
└── screenshots/               # 效果截图
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> 国内用户推荐使用清华镜像源：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 2. 自动化分析（推荐，一键生成报告）

输入一个视频，自动生成标注视频+截图+HTML报告+JSON+CSV日志：

```bash
# 基本用法
python run_analysis.py --video your_video.mp4

# 完整参数（竖屏视频，终点线在画面中间）
python run_analysis.py --video your_video.mp4 --line-orientation vertical --line-pos 0.5 --auto-start 1 --lane-direction vertical

# 横屏视频
python run_analysis.py --video your_video.mp4 --line-orientation horizontal --line-pos 0.8 --auto-start 1 --lane-direction horizontal
```

输出目录：`output/视频名/`
- `annotated.mp4` — 标注后的视频
- `result.jpg` — 最终排名截图
- `report.html` — HTML可视化报告（浏览器打开即可）
- `report.json` — JSON数据报告
- `frame_log.csv` — 逐帧检测日志

### 3. 实时窗口Demo（交互式）

```bash
# 用视频文件
python demo_racing.py --video your_video.mp4 --line-orientation vertical --line-pos 0.5 --auto-start 1 --lane-direction vertical

# 用电脑摄像头
python demo_racing.py --video 0

# 保存结果
python demo_racing.py --video your_video.mp4 --save output.mp4 --save-frame result.jpg
```

### 4. 查看分析报告

```bash
# 打开HTML报告
start output/your_video/report.html

# 播放标注视频
start output/your_video/annotated.mp4
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--video` | 必填 | 视频路径，`0`为摄像头 |
| `--model` | yolov8n.pt | YOLO模型路径 |
| `--line-orientation` | vertical | 终点线方向：vertical(竖线) / horizontal(横线) |
| `--line-pos` | 0.5 | 终点线位置（0-1，0.5=画面中间） |
| `--auto-start` | 1 | 第几帧自动开始比赛 |
| `--lane-direction` | vertical | 编号分配方向：vertical(从上到下) / horizontal(从左到右) |
| `--max-width` | 720 | 显示窗口最大宽度 |
| `--max-height` | 900 | 显示窗口最大高度 |
| `--save` | 无 | 保存输出视频路径 |
| `--save-frame` | 无 | 保存最终截图路径 |

## 实时窗口操作

| 按键 | 功能 |
|------|------|
| S | 开始比赛（锁定选手编号） |
| R | 重置比赛 |
| 空格 | 暂停/继续 |
| Q | 退出 |

## Demo结果

以路跑比赛视频为例（8-10人跑步，12秒）：

| 指标 | 结果 |
|------|------|
| 总帧数 | 367 |
| 视频时长 | 12.4s |
| 处理速度 | 6.4 FPS |
| 同帧最多目标 | 8人 |
| 独立追踪ID | 48个 |
| 完赛人数 | 17人 |

最终排名（前5）：

| 名次 | 选手 | 衣服颜色 | 冲线时间 |
|------|------|---------|---------|
| 🥇 1 | 4号 | 黑色 | 0.30s |
| 🥈 2 | 5号 | 黑色 | 0.51s |
| 🥉 3 | 8号 | 红色 | 0.85s |
| 4 | 11号 | 黑色 | 1.56s |
| 5 | 6号 | 黑色 | 2.54s |

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
