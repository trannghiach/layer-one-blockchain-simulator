# Layer 1 Blockchain Simulator

## 1. Giới thiệu

Dự án mô phỏng một mạng lưới Blockchain Layer 1 với cơ chế đồng thuận hai pha (Two-Phase Voting Consensus) theo tinh thần Tendermint/HotStuff. Hệ thống đảm bảo:
- **Safety**: Không có 2 block khác nhau được finalize ở cùng một height
- **Liveness**: Nếu delay mạng có giới hạn, block mới vẫn được đề xuất và finalize
- **Determinism**: Chạy lại với cùng seed cho kết quả byte-identical

## 2. Yêu cầu hệ thống

- Python 3.8 trở lên
- pip (Python package manager)

## 3. Cài đặt môi trường

```bash
# Tạo virtual environment (khuyến nghị)
python -m venv venv

# Kích hoạt virtual environment
# Windows bash:
source ./venv/Scripts/activate
# Linux/Mac:
source ./venv/bin/activate

# Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

## 4. Hướng dẫn chạy

### 4.1 Chạy toàn bộ Test Suite (Entry Point chính)

```bash
pytest -v
```

**Kết quả mong đợi:** `26 passed`

Bao gồm:
- Unit tests: Crypto, State Machine, Vote counting
- E2E tests: Safety, Liveness, Invalid signature rejection, Duplicate handling, Network resilience, Determinism

### 4.2 Kiểm chứng tính Đơn định (Determinism Check)

```bash
python run_determinism_check.py
```

**Kết quả mong đợi:**
```
>>> SUCCESS: Determinism Verified! (10/10)
```

Script này chạy mô phỏng 2 lần với cùng seed và so sánh:
- State Hash cuối cùng
- Log Hash (byte-identical logs)

### 4.3 Chạy từng module test riêng

```bash
# Unit tests cho Cryptography
pytest tests/test_unit_crypto.py -v

# Unit tests cho State Machine
pytest tests/test_state_machine.py -v

# E2E Consensus flow
pytest tests/test_consensus_flow.py -v

# E2E Complete test suite
pytest tests/test_e2e_complete.py -v

# Chaos network test (high drop rate)
pytest tests/test_e2e_scenarios.py -v
```

## 5. Cấu trúc thư mục

```
Lab01_ID1_ID2_ID3_ID4_ID5/
├── src/                    # Mã nguồn chính
│   ├── crypto.py           # Ed25519 signatures, domain separation
│   ├── models.py           # Transaction, Block, Vote models
│   ├── state.py            # State Machine với nonce protection
│   ├── consensus.py        # Two-phase voting engine
│   ├── node.py             # Node logic, message handling
│   ├── simulator.py        # Network simulator (delay, drop, duplicate)
│   └── utils.py            # Deterministic encoding, hashing
├── tests/                  # Các file kiểm thử
│   ├── test_unit_crypto.py       # Unit tests crypto
│   ├── test_state_machine.py     # Unit tests state
│   ├── test_consensus_flow.py    # Integration tests
│   ├── test_e2e_complete.py      # Complete E2E test suite
│   └── test_e2e_scenarios.py     # Chaos network tests
├── logs/                   # Nhật ký mô phỏng
│   ├── network.log         # Network events log
│   ├── run1.log            # Determinism check log 1
│   └── run2.log            # Determinism check log 2
├── config/                 # Cấu hình hệ thống
│   └── node_config.py      # Network, consensus, simulation config
├── run_determinism_check.py  # Script kiểm tra determinism
├── requirements.txt        # Dependencies
├── README.md               # Hướng dẫn này
└── REPORT.pdf              # Báo cáo chi tiết
```

## 6. Các Test Case theo yêu cầu đề bài

| # | Test Case | File | Mô tả |
|---|-----------|------|-------|
| 1 | Only one block finalized per height | test_e2e_complete.py | Đảm bảo Safety |
| 2 | Invalid signatures rejected | test_e2e_complete.py | TX, Block, Vote với chữ ký sai bị từ chối |
| 3 | Wrong context rejected | test_unit_crypto.py | Domain Separation hoạt động |
| 4 | Duplicates ignored | test_e2e_complete.py | Vote/TX trùng lặp không phá Safety |
| 5 | Delayed/dropped no conflict | test_e2e_complete.py | Network issues không gây conflict |
| 6 | Identical runs identical output | test_e2e_complete.py | Determinism verification |
| 7 | Replay attack rejected | test_state_machine.py | Nonce protection chống replay |
| 8 | 8-node consensus | test_e2e_complete.py | Đủ 8 nodes theo yêu cầu |

## 7. Cấu hình (config/node_config.py)

```python
CONFIG = {
    "network": {
        "min_delay": 0.01,      # Độ trễ tối thiểu (giây)
        "max_delay": 0.1,       # Độ trễ tối đa (giây)
        "drop_prob": 0.1,       # Xác suất mất gói tin
        "duplicate_prob": 0.05, # Xác suất nhân đôi
        "rate_limit": {...}     # Giới hạn tốc độ gửi
    },
    "consensus": {
        "retry_count": 4        # Số lần gửi lại tin nhắn
    },
    "nodes": ["Node0", ..., "Node7"],  # 8 nodes
    "simulation": {
        "max_time": 10.0,
        "seed": 123456          # Seed cho determinism
    }
}
```

## 8. Tài liệu tham khảo

- Tendermint Consensus: https://docs.tendermint.com/master/spec/consensus/consensus.html
- HotStuff BFT: https://arxiv.org/abs/1803.05069
- Ed25519 Signatures: https://ed25519.cr.yp.to/
- PyNaCl Documentation: https://pynacl.readthedocs.io/
