"""
FastAPI 后端服务
提供AI推理API、WebSocket实时推送
"""
import cv2
import numpy as np
import base64
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import time
import json
from typing import List, Optional

from ai.engine import AIEngine

app = FastAPI(title="追迹 - AI追踪引擎API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局AI引擎实例
engine: Optional[AIEngine] = None

# WebSocket连接管理
active_connections: List[WebSocket] = []


@app.on_event("startup")
async def startup_event():
    """启动时初始化AI引擎"""
    global engine
    print("正在加载YOLO模型...")
    engine = AIEngine(model_path="yolov8n.pt", mode="all")
    print("AI引擎初始化完成！")


@app.get("/")
async def root():
    return {"message": "追迹 AI 追踪引擎 API", "status": "running"}


@app.get("/api/status")
async def get_status():
    """获取引擎状态"""
    if engine is None:
        return {"status": "initializing"}
    return engine.get_status()


@app.post("/api/analyze")
async def analyze_image(file: UploadFile = File(...)):
    """
    分析单张图片
    上传图片，返回检测结果和标注后的图片
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="AI引擎未就绪")
    
    # 读取图片
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if frame is None:
        raise HTTPException(status_code=400, detail="无法解析图片")
    
    # 处理
    result = engine.process_frame(frame)
    
    # 将标注后的图片转成base64
    _, buffer = cv2.imencode('.jpg', result["annotated_frame"])
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return {
        "success": True,
        "timestamp": result["timestamp"],
        "fps": result["fps"],
        "tracked_objects": result["tracked_objects"],
        "crossings": result.get("crossings", []),
        "rankings": result.get("rankings", []),
        "crowd_stats": result.get("crowd_stats", {}),
        "anomalies": result.get("anomalies", []),
        "annotated_image": f"data:image/jpeg;base64,{img_base64}"
    }


@app.post("/api/line/set")
async def set_line(data: dict):
    """设置过线检测线"""
    if engine is None:
        raise HTTPException(status_code=503, detail="AI引擎未就绪")
    
    start_x = data.get("start_x", 100)
    start_y = data.get("start_y", 400)
    end_x = data.get("end_x", 500)
    end_y = data.get("end_y", 400)
    direction = data.get("direction", "both")
    
    engine.set_line(start_x, start_y, end_x, end_y, direction)
    
    return {"success": True, "message": "检测线已更新"}


@app.post("/api/region/set")
async def set_region(data: dict):
    """设置客流统计区域"""
    if engine is None:
        raise HTTPException(status_code=503, detail="AI引擎未就绪")
    
    points = data.get("points", [])
    if len(points) < 3:
        raise HTTPException(status_code=400, detail="区域至少需要3个点")
    
    engine.set_region([(p["x"], p["y"]) for p in points])
    
    return {"success": True, "message": "统计区域已更新"}


@app.post("/api/race/reset")
async def reset_race():
    """重置比赛"""
    if engine is None:
        raise HTTPException(status_code=503, detail="AI引擎未就绪")
    
    engine.reset_race()
    
    return {"success": True, "message": "比赛已重置"}


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket实时视频流分析
    客户端发送视频帧，服务端返回分析结果
    """
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # 接收base64图片
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "frame" and engine is not None:
                # 解码图片
                img_data = base64.b64decode(message["image"])
                nparr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    # 处理
                    result = engine.process_frame(frame)
                    
                    # 将标注后的图片转成base64
                    _, buffer = cv2.imencode('.jpg', result["annotated_frame"])
                    img_base64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # 返回结果
                    response = {
                        "type": "result",
                        "timestamp": result["timestamp"],
                        "fps": result["fps"],
                        "tracked_count": len(result["tracked_objects"]),
                        "tracked_objects": result["tracked_objects"],
                        "rankings": result.get("rankings", []),
                        "crowd_stats": result.get("crowd_stats", {}),
                        "annotated_image": f"data:image/jpeg;base64,{img_base64}"
                    }
                    
                    await websocket.send_json(response)
            
            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print("WebSocket连接断开")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
