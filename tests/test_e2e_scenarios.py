import sys
import os
import random
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.node import Node
from src.simulator import Simulator
from config.node_config import CONFIG

def test_chaos_network_liveness():
    """
    Test khả năng sống sót (Liveness):
    Mạng rớt 20% gói tin, delay cao. Hệ thống vẫn phải finalize được block.
    """
    print("\n--- Testing Chaos Network (20% Drop Rate) ---")
    
    # 1. Cấu hình mạng khắc nghiệt - override từ config gốc
    chaos_config = {
        "min_delay": CONFIG["network"]["min_delay"],
        "max_delay": 0.2,  # Tăng delay cho chaos test
        "drop_prob": 0.2,  # 20% drop rate
        "duplicate_prob": CONFIG["network"]["duplicate_prob"]
    }
    sim = Simulator(chaos_config)
    
    # 2. Setup Nodes từ config
    node_names = CONFIG["nodes"]
    num_nodes = len(node_names)
    
    nodes = []
    validator_keys = []
    for i in range(num_nodes):
        n = Node(node_names[i], sim, [], config=CONFIG)
        nodes.append(n)
        validator_keys.append(n.key_pair.pub_key_str)
        sim.register_node(n)

    # Tính threshold theo công thức BFT
    threshold = (num_nodes * 2) // 3 + 1

    for n in nodes:
        n.consensus.validators = validator_keys
        n.consensus.n = num_nodes
        n.consensus.threshold = threshold
        for peer in nodes:
            n.add_peer(peer.node_id)

    # 3. Chạy đồng thuận
    nodes[0].start_consensus()
    
    # Chạy lâu hơn bình thường (20s) để bù cho các gói tin bị mất
    sim.run(max_time=20.0)
    
    # 4. Kiểm tra kết quả
    finalized_count = sum(1 for n in nodes if n.finalized_height >= 1)
    
    print(f"Nodes finalized: {finalized_count}/{num_nodes}")
    
    # Yêu cầu: Ít nhất threshold node phải đồng thuận xong
    assert finalized_count >= threshold, "FAIL: Mạng yếu làm hệ thống dừng hoạt động (Liveness broken)"
    
    # Kiểm tra Safety: Tất cả các node đã finalize phải có cùng Block Hash
    hashes = set()
    for n in nodes:
        if n.finalized_height >= 1:
            block = n.blocks[1]
            hashes.add(block.get_hash())
            
    assert len(hashes) == 1, "FAIL: Safety broken! Các node finalize các block khác nhau."
    print("PASS: Chaos Test OK (Liveness & Safety preserved)")

if __name__ == "__main__":
    test_chaos_network_liveness()