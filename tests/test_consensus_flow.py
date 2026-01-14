import sys
import os
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.node import Node
from src.simulator import Simulator
from config.node_config import CONFIG

def test_consensus_happy_path():
    """Kịch bản hoàn hảo: 4 node đồng thuận finalize block 1"""
    # 1. Setup mạng với cấu hình không drop
    network_config = CONFIG["network"].copy()
    network_config["drop_prob"] = 0.0  # Override để test happy path
    network_config["duplicate_prob"] = 0.0
    
    sim = Simulator(network_config)
    
    # Lấy danh sách node từ config
    node_names = CONFIG["nodes"]
    num_nodes = len(node_names)
    
    # Tạo nodes
    validator_keys = []
    nodes = []
    for i in range(num_nodes):
        n = Node(node_names[i], sim, [], config=CONFIG)
        nodes.append(n)
        validator_keys.append(n.key_pair.pub_key_str)
        sim.register_node(n)

    # Tính threshold theo công thức BFT
    threshold = (num_nodes * 2) // 3 + 1

    # Cập nhật danh sách validator cho các node và kết nối peers
    for n in nodes:
        n.consensus.validators = validator_keys
        n.consensus.n = num_nodes
        n.consensus.threshold = threshold
        for peer in nodes:
            n.add_peer(peer.node_id)

    # 2. Bắt đầu đồng thuận
    print("\n--- Starting Consensus Test ---")
    nodes[0].start_consensus()
    
    # 3. Chạy mô phỏng
    max_time = CONFIG.get("simulation", {}).get("max_time", 10.0)
    sim.run(max_time=max_time)
    
    # 4. Kiểm tra kết quả
    for n in nodes:
        assert n.finalized_height == 1, f"{n.node_id} chưa finalize block 1!"
        print(f"PASS: {n.node_id} finalized block 1")

if __name__ == "__main__":
    test_consensus_happy_path()