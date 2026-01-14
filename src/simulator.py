# src/simulator.py
import heapq
import random
import logging
from collections import defaultdict

# Cấu hình logging để ghi file log theo yêu cầu
logging.basicConfig(
    filename='logs/network.log', 
    level=logging.INFO,
    format='%(message)s', # Format tùy chỉnh sau
    filemode='w'
)

class Event:
    def __init__(self, delivery_time, receiver_id, sender_id, message, event_type="MESSAGE"):
        self.delivery_time = delivery_time
        self.receiver_id = receiver_id
        self.sender_id = sender_id
        self.message = message
        self.event_type = event_type  # MESSAGE, HEADER, BODY, UNBLOCK

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
            # Rate limiting config
            rate_config = network_config.get("rate_limit", {})
            self.max_msg_per_sec = rate_config.get("max_messages_per_second", 100)
            self.block_duration = rate_config.get("block_duration", 1.0)
        else:
            self.min_delay = config.get("min_delay", 0.01)
            self.max_delay = config.get("max_delay", 0.1)
            self.drop_prob = config.get("drop_prob", 0.0)
            self.duplicate_prob = config.get("duplicate_prob", 0.0)
            self.max_msg_per_sec = config.get("max_messages_per_second", 100)
            self.block_duration = config.get("block_duration", 1.0)
        
        # Rate limiting state: Đếm số tin nhắn từ mỗi sender trong 1 giây
        self.message_counts = defaultdict(lambda: {"count": 0, "window_start": 0.0})
        # Blocked peers: {(sender, receiver): unblock_time}
        self.blocked_peers = {}
        # Pending block bodies: {(sender, receiver, block_hash): block_data}
        self.pending_bodies = {}
        # Accepted headers: {(receiver, block_hash): True}
        self.accepted_headers = defaultdict(set)

    def register_node(self, node):
        self.nodes[node.node_id] = node

    def _check_rate_limit(self, sender_id: str, receiver_id: str) -> bool:
        """Kiểm tra và cập nhật rate limit. Trả về True nếu được phép gửi."""
        pair_key = (sender_id, receiver_id)
        
        # Kiểm tra xem peer có đang bị block không
        if pair_key in self.blocked_peers:
            if self.current_time < self.blocked_peers[pair_key]:
                logging.info(f"{self.current_time:.3f} BLOCKED {sender_id}->{receiver_id} (rate limit)")
                return False
            else:
                # Hết thời gian block
                del self.blocked_peers[pair_key]
                logging.info(f"{self.current_time:.3f} UNBLOCK {sender_id}->{receiver_id}")
        
        # Cập nhật đếm tin nhắn
        stats = self.message_counts[pair_key]
        if self.current_time - stats["window_start"] >= 1.0:
            # Reset window
            stats["count"] = 0
            stats["window_start"] = self.current_time
        
        stats["count"] += 1
        
        # Kiểm tra vượt ngưỡng
        if stats["count"] > self.max_msg_per_sec:
            self.blocked_peers[pair_key] = self.current_time + self.block_duration
            logging.info(f"{self.current_time:.3f} BLOCK {sender_id}->{receiver_id} (exceeded rate limit)")
            return False
        
        return True

    def send_header(self, sender_id: str, receiver_id: str, header: dict):
        """Gửi Header của block trước (theo yêu cầu đề bài)"""
        if not self._check_rate_limit(sender_id, receiver_id):
            return
            
        if random.random() < self.drop_prob:
            logging.info(f"{self.current_time:.3f} DROP_HEADER {sender_id}->{receiver_id}")
            return

        delay = random.uniform(self.min_delay, self.max_delay)
        delivery_time = self.current_time + delay
        
        event = Event(delivery_time, receiver_id, sender_id, header, "HEADER")
        heapq.heappush(self.events, event)
        
        logging.info(f"{self.current_time:.3f} SEND_HEADER {sender_id}->{receiver_id} height={header.get('height')}")

    def send_body(self, sender_id: str, receiver_id: str, body: dict, block_hash: str):
        """Gửi Body của block (chỉ khi receiver đã accept header)"""
        if not self._check_rate_limit(sender_id, receiver_id):
            return
            
        # Kiểm tra xem receiver đã accept header chưa
        if block_hash not in self.accepted_headers[receiver_id]:
            # Lưu pending body để gửi sau khi header được accept
            self.pending_bodies[(sender_id, receiver_id, block_hash)] = body
            logging.info(f"{self.current_time:.3f} PENDING_BODY {sender_id}->{receiver_id} (waiting for header)")
            return
            
        if random.random() < self.drop_prob:
            logging.info(f"{self.current_time:.3f} DROP_BODY {sender_id}->{receiver_id}")
            return

        delay = random.uniform(self.min_delay, self.max_delay)
        delivery_time = self.current_time + delay
        
        event = Event(delivery_time, receiver_id, sender_id, body, "BODY")
        heapq.heappush(self.events, event)
        
        logging.info(f"{self.current_time:.3f} SEND_BODY {sender_id}->{receiver_id} height={body.get('height')}")

    def accept_header(self, receiver_id: str, block_hash: str):
        """Node báo đã accept header, cho phép nhận body"""
        self.accepted_headers[receiver_id].add(block_hash)
        
        # Gửi các pending bodies đang chờ
        keys_to_remove = []
        for key, body in self.pending_bodies.items():
            sender_id, recv_id, b_hash = key
            if recv_id == receiver_id and b_hash == block_hash:
                self.send_body(sender_id, receiver_id, body, block_hash)
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.pending_bodies[key]

    def send_message(self, sender_id: str, receiver_id: str, message: dict):
        """Mô phỏng gửi tin qua mạng không tin cậy"""
        
        # Kiểm tra rate limit
        if not self._check_rate_limit(sender_id, receiver_id):
            return
        
        # 1. DROP: Kiểm tra xem tin có bị mất không
        if random.random() < self.drop_prob:
            logging.info(f"{self.current_time:.3f} DROP {sender_id}->{receiver_id} {message}")
            return # Tin nhắn biến mất

        # 2. DELAY: Tính toán thời gian đến ngẫu nhiên
        delay = random.uniform(self.min_delay, self.max_delay)
        delivery_time = self.current_time + delay
        
        # Tạo sự kiện
        event = Event(delivery_time, receiver_id, sender_id, message)
        heapq.heappush(self.events, event)
        
        # Log sự kiện SEND
        logging.info(f"{self.current_time:.3f} SEND {sender_id}->{receiver_id} msg={message}")

        # 3. DUPLICATE: Nhân đôi tin nhắn
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
                
                if event.event_type == "HEADER":
                    node.receive_header(event.sender_id, event.message)
                    logging.info(f"{self.current_time:.3f} RECV_HEADER {event.receiver_id}<-{event.sender_id}")
                elif event.event_type == "BODY":
                    node.receive_body(event.sender_id, event.message)
                    logging.info(f"{self.current_time:.3f} RECV_BODY {event.receiver_id}<-{event.sender_id}")
                else:
                    node.receive(event.sender_id, event.message)
                    logging.info(f"{self.current_time:.3f} RECV {event.receiver_id}<-{event.sender_id} msg={event.message}")