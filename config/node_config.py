# Node configuration
CONFIG = {
    "network": {
        "min_delay": 0.01,
        "max_delay": 0.1,
        "drop_prob": 0.1,
        "duplicate_prob": 0.05
    },
    "consensus": {
        "timeout_prevote": 1.0,
        "timeout_precommit": 1.0,
        "retry_count": 4  # Số lần gửi lại tin nhắn
    },
    "nodes": ["Node0", "Node1", "Node2", "Node3"],
    "simulation": {
        "max_time": 10.0,
        "seed": 123456
    }
}