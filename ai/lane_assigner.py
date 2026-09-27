"""
选手编号模块
负责：起跑时按目标位置从左到右分配选手编号（1号、2号、3号...）
之后保持映射不变，类似号码布
"""


class LaneAssigner:
    """选手编号分配器 - 起跑时按位置分配编号，之后保持不变"""
    
    def __init__(self, num_lanes=8, direction="horizontal"):
        """
        :param num_lanes: 最大跑道数
        :param direction: 分配方向 "horizontal"（从左到右） | "vertical"（从上到下）
        """
        self.num_lanes = num_lanes
        self.direction = direction
        
        # 追踪ID -> 跑道号 映射
        self.id_to_lane = {}
        # 跑道号 -> 追踪ID 映射
        self.lane_to_id = {}
        # 是否已锁定（起跑后锁定，不再分配新跑道）
        self.locked = False
    
    def reset(self):
        """重置（新一轮比赛）"""
        self.id_to_lane = {}
        self.lane_to_id = {}
        self.locked = False
    
    def lock(self):
        """锁定分配（起跑后调用，不再分配新跑道）"""
        self.locked = True
    
    def assign_lanes(self, tracked_objects):
        """
        给当前画面中的目标分配跑道号
        新出现的目标按当前位置分配最近的空跑道号
        已分配的目标保持不变
        """
        # 先给已有跑道号的目标更新
        for obj in tracked_objects:
            tid = obj["id"]
            if tid in self.id_to_lane:
                obj["lane"] = self.id_to_lane[tid]
            else:
                obj["lane"] = None
        
        # 找出未分配跑道的目标
        unassigned = [o for o in tracked_objects if o["id"] not in self.id_to_lane]
        
        if not unassigned:
            return tracked_objects
        
        # 按位置排序（决定分配顺序）
        if self.direction == "horizontal":
            unassigned.sort(key=lambda o: o["center"][0])
        else:
            unassigned.sort(key=lambda o: o["center"][1])
        
        # 找出已占用的跑道号
        used_lanes = set(self.id_to_lane.values())
        
        # 给每个未分配目标分配最近的空跑道号
        for obj in unassigned:
            tid = obj["id"]
            # 找下一个空跑道号
            for lane_num in range(1, self.num_lanes + 1):
                if lane_num not in used_lanes:
                    self.id_to_lane[tid] = lane_num
                    self.lane_to_id[lane_num] = tid
                    used_lanes.add(lane_num)
                    obj["lane"] = lane_num
                    break
        
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
