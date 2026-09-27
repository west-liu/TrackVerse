"""
选手编号模块
负责：起跑时按目标位置从左到右分配选手编号（1号、2号、3号...）
之后保持映射不变，类似号码布
"""
from collections import defaultdict


class LaneAssigner:
    """选手编号分配器 - 起跑时按位置分配编号，之后保持不变，动态扩容"""
    
    def __init__(self, direction="horizontal", max_lanes=100):
        """
        :param direction: 分配方向 "horizontal"（从左到右） | "vertical"（从上到下）
        :param max_lanes: 最大跑道数（动态扩容，默认100足够）
        """
        self.direction = direction
        self.max_lanes = max_lanes
        
        # 追踪ID -> 跑道号 映射
        self.id_to_lane = {}
        # 跑道号 -> 追踪ID 映射
        self.lane_to_id = {}
        # 是否已锁定（起跑后锁定，不再分配新跑道）
        self.locked = False
        # 最后一次出现的帧 {track_id: frame_idx}
        self.last_seen = {}
        # 当前帧索引
        self.frame_idx = 0
        # 已使用的最大跑道号
        self.next_lane = 1
    
    def reset(self):
        """重置（新一轮比赛）"""
        self.id_to_lane = {}
        self.lane_to_id = {}
        self.locked = False
        self.last_seen = {}
        self.frame_idx = 0
        self.next_lane = 1
    
    def lock(self):
        """锁定分配（起跑后调用，不再分配新跑道）"""
        self.locked = True
    
    def assign_lanes(self, tracked_objects):
        """
        给当前画面中的目标分配跑道号
        - 已分配的目标保持不变
        - 新出现的目标：如果锁定了就不给号；没锁定就分配新号
        """
        self.frame_idx += 1
        
        current_ids = set()
        
        for obj in tracked_objects:
            tid = obj["id"]
            current_ids.add(tid)
            self.last_seen[tid] = self.frame_idx
            
            if tid in self.id_to_lane:
                obj["lane"] = self.id_to_lane[tid]
            else:
                obj["lane"] = None
        
        # 锁定后不给新目标分配编号
        if self.locked:
            return tracked_objects
        
        # 找出未分配跑道的目标
        unassigned = [o for o in tracked_objects if o["id"] not in self.id_to_lane]
        
        if not unassigned:
            return tracked_objects
        
        # 按位置排序
        if self.direction == "horizontal":
            unassigned.sort(key=lambda o: o["center"][0])
        else:
            unassigned.sort(key=lambda o: o["center"][1])
        
        # 给每个未分配目标分配新的跑道号
        for obj in unassigned:
            tid = obj["id"]
            if self.next_lane <= self.max_lanes:
                lane_num = self.next_lane
                self.id_to_lane[tid] = lane_num
                self.lane_to_id[lane_num] = tid
                obj["lane"] = lane_num
                self.next_lane += 1
            else:
                obj["lane"] = None
        
        return tracked_objects
    
    def get_lane(self, track_id):
        """根据追踪ID获取跑道号"""
        return self.id_to_lane.get(track_id, None)
    
    def get_track_id(self, lane_num):
        """根据跑道号获取追踪ID"""
        return self.lane_to_id.get(lane_num, None)
    
    def get_assigned_count(self):
        """获取已分配的跑道数"""
        return len(self.id_to_lane)
    
    def cleanup_missing(self, max_missing_frames=30):
        """清理长时间消失的目标（释放跑道号）"""
        stale_ids = []
        for tid, last_frame in self.last_seen.items():
            if self.frame_idx - last_frame > max_missing_frames:
                stale_ids.append(tid)
        
        for tid in stale_ids:
            if tid in self.id_to_lane:
                lane = self.id_to_lane[tid]
                del self.id_to_lane[tid]
                if lane in self.lane_to_id:
                    del self.lane_to_id[lane]
            if tid in self.last_seen:
                del self.last_seen[tid]
