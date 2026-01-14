# src/simulator.py
import heapq
import random
import logging

# Cấu hình logging để ghi file log theo yêu cầu
logging.basicConfig(
    filename='logs/network.log', 
    level=logging.INFO,
    format='%(message)s', # Format tùy chỉnh sau
    filemode='w'
)

class Event:
    def __init__(self, delivery_time, receiver_id, sender_id, message):
        self.delivery_time = delivery_time
        self.receiver_id = receiver_id
        self.sender_id = sender_id
        self.message = message

    # Để heapq so sánh được thứ tự dựa trên thời gian
    def __lt__(self, other):
        return self.delivery_time < other.delivery_time

class Simulator:
    def __init__(self, config: dict):
        if "seed" in config:
            random.seed(config["seed"])
            
        self.nodes = {}       # Map: node_id -> Node object
        self.events = []      # Priority Queue (Min-Heap)
        self.current_time = 0.0
        
        # Lấy cấu hình mạng từ config, hỗ trợ cả flat config và nested config
        if "network" in config:
            network_config = config["network"]
            self.min_delay = network_config.get("min_delay", 0.01)
            self.max_delay = network_config.get("max_delay", 0.1)
            self.drop_prob = network_config.get("drop_prob", 0.0)
            self.duplicate_prob = network_config.get("duplicate_prob", 0.0)
        else:
            self.min_delay = config.get("min_delay", 0.01)
            self.max_delay = config.get("max_delay", 0.1)
            self.drop_prob = config.get("drop_prob", 0.0)
            self.duplicate_prob = config.get("duplicate_prob", 0.0)      

    def register_node(self, node):
        self.nodes[node.node_id] = node

    def send_message(self, sender_id: str, receiver_id: str, message: dict):
        """Mô phỏng gửi tin qua mạng không tin cậy [cite: 59]"""
        
        # 1. DROP: Kiểm tra xem tin có bị mất không [cite: 60]
        if random.random() < self.drop_prob:
            logging.info(f"{self.current_time:.3f} DROP {sender_id}->{receiver_id} {message}")
            return # Tin nhắn biến mất

        # 2. DELAY: Tính toán thời gian đến ngẫu nhiên [cite: 60]
        delay = random.uniform(self.min_delay, self.max_delay)
        delivery_time = self.current_time + delay
        
        # Tạo sự kiện
        event = Event(delivery_time, receiver_id, sender_id, message)
        heapq.heappush(self.events, event)
        
        # Log sự kiện SEND [cite: 63]
        logging.info(f"{self.current_time:.3f} SEND {sender_id}->{receiver_id} msg={message}")

        # 3. DUPLICATE: Nhân đôi tin nhắn [cite: 60]
        if random.random() < self.duplicate_prob:
            extra_delay = random.uniform(self.min_delay, self.max_delay)
            dup_event = Event(delivery_time + extra_delay, receiver_id, sender_id, message)
            heapq.heappush(self.events, dup_event)
            logging.info(f"{self.current_time:.3f} DUPLICATE {sender_id}->{receiver_id}")

    def run(self, max_time=100.0):
        """Vòng lặp chính xử lý sự kiện"""
        print(f"--- Simulation Started (Max Time: {max_time}) ---")
        
        while self.events:
            # Lấy sự kiện có thời gian nhỏ nhất ra
            event = heapq.heappop(self.events)
            
            if event.delivery_time > max_time:
                break
            
            # Cập nhật thời gian hệ thống
            self.current_time = event.delivery_time
            
            # Giao tin nhắn cho Node
            if event.receiver_id in self.nodes:
                node = self.nodes[event.receiver_id]
                node.receive(event.sender_id, event.message)
                
                # Log sự kiện RECEIVE
                logging.info(f"{self.current_time:.3f} RECV {event.receiver_id}<-{event.sender_id} msg={event.message}")