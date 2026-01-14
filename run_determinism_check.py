import sys
import os
import hashlib
import random
import logging
from src.node import Node
from src.simulator import Simulator
from config.node_config import CONFIG

def run_simulation(seed, log_file):
    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(message)s', filemode='w')

    # Lấy cấu hình từ CONFIG
    network_config = CONFIG["network"]
    simulation_config = CONFIG.get("simulation", {})
    node_names = CONFIG["nodes"]
    
    config = {
        "min_delay": network_config["min_delay"],
        "max_delay": network_config["max_delay"],
        "drop_prob": network_config["drop_prob"],
        "duplicate_prob": network_config["duplicate_prob"],
        "seed": seed 
    }
    sim = Simulator(config)

    nodes = []
    validator_keys = []
    num_nodes = len(node_names)
    
    # Khởi tạo nodes với key_seed cố định dựa trên seed chung
    for i in range(num_nodes):
        node_seed = f"node_{i}_{seed}"
        n = Node(node_names[i], sim, [], key_seed=node_seed, config=CONFIG)
        nodes.append(n)
        validator_keys.append(n.key_pair.pub_key_str)
        sim.register_node(n)

    # Tính threshold theo công thức BFT: 2/3 + 1
    threshold = (num_nodes * 2) // 3 + 1

    for n in nodes:
        n.consensus.validators = validator_keys
        n.consensus.n = num_nodes
        n.consensus.threshold = threshold
        for peer in nodes:
            n.add_peer(peer.node_id)

    nodes[0].start_consensus()
    
    max_time = simulation_config.get("max_time", 5.0)
    sim.run(max_time=max_time)
    
    if 1 in nodes[0].blocks:
        return nodes[0].blocks[1].get_hash()
    return "None"

def get_file_hash(filepath):
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

if __name__ == "__main__":
    print("--- DETERMINISM CHECK SCRIPT ---")
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    SEED = CONFIG.get("simulation", {}).get("seed", 123456)
    
    print(f"1. Running Simulation 1 (Seed={SEED})...")
    state1 = run_simulation(SEED, "logs/run1.log")
    hash_log1 = get_file_hash("logs/run1.log")
    
    print(f"2. Running Simulation 2 (Seed={SEED})...")
    state2 = run_simulation(SEED, "logs/run2.log")
    hash_log2 = get_file_hash("logs/run2.log")
    
    print("\n--- RESULTS ---")
    print(f"Run 1 State Hash: {state1}")
    print(f"Run 2 State Hash: {state2}")
    print(f"Run 1 Log Hash:   {hash_log1}")
    print(f"Run 2 Log Hash:   {hash_log2}")
    
    if state1 == state2 and hash_log1 == hash_log2:
        print("\n>>> SUCCESS: Determinism Verified! (10/10)")
    else:
        print("\n>>> FAIL: Logs or State do not match.")