import sys
import os
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.state import StateMachine
from src.models import Transaction, Block
from src.crypto import KeyPair, CTX_TX
from src.utils import get_hash

def test_apply_transaction_success():
    """Kiểm tra apply 1 TX hợp lệ"""
    sm = StateMachine()
    alice = KeyPair()
    
    # Alice tạo transaction: Set Alice/a = 100 (key bắt đầu bằng sender)
    tx = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/a", "100", 0)
    tx.signature = alice.sign(tx.to_dict(include_sig=False), CTX_TX)
    
    result = sm.apply_transaction(tx)
    
    assert result == True
    assert sm.data[f"{alice.pub_key_str}/a"] == "100"
    assert sm.nonces[alice.pub_key_str] == 0

def test_replay_attack():
    """Kiểm tra chống dùng lại Nonce cũ"""
    sm = StateMachine()
    alice = KeyPair()
    
    # TX 1: Nonce 0
    tx1 = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/a", "1", 0)
    tx1.signature = alice.sign(tx1.to_dict(include_sig=False), CTX_TX)
    sm.apply_transaction(tx1)
    
    # TX 2: Vẫn Nonce 0 (Replay) -> Phải Fail
    tx2 = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/a", "2", 0)
    tx2.signature = alice.sign(tx2.to_dict(include_sig=False), CTX_TX)
    
    result = sm.apply_transaction(tx2)
    assert result == False, "FAIL: StateMachine chấp nhận replay nonce"

def test_block_execution():
    """Kiểm tra State Hash khớp sau khi chạy cả block"""
    sm = StateMachine()
    alice = KeyPair()
    
    # Tạo 2 TX
    tx1 = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/x", "1", 0)
    tx1.signature = alice.sign(tx1.to_dict(include_sig=False), CTX_TX)
    
    tx2 = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/y", "2", 1)
    tx2.signature = alice.sign(tx2.to_dict(include_sig=False), CTX_TX)
    
    # Tính state hash mong đợi thủ công
    expected_data = {
        f"{alice.pub_key_str}/x": "1",
        f"{alice.pub_key_str}/y": "2"
    }
    expected_hash = get_hash(expected_data)
    
    # Tạo Block giả (Header cam kết expected_hash)
    block = Block(1, "parent", [tx1, tx2], expected_hash, "proposer")
    
    # Apply
    success = sm.apply_block(block)
    assert success == True
    assert sm.get_state_hash() == expected_hash

def test_ownership_violation():
    """Kiểm tra sender không thể sửa key của người khác (Section 7 requirement)"""
    sm = StateMachine()
    alice = KeyPair()
    bob = KeyPair()
    
    # Alice cố tình sửa key của Bob -> Phải bị từ chối
    malicious_tx = Transaction(alice.pub_key_str, f"{bob.pub_key_str}/balance", "0", 0)
    malicious_tx.signature = alice.sign(malicious_tx.to_dict(include_sig=False), CTX_TX)
    
    result = sm.apply_transaction(malicious_tx)
    assert result == False, "FAIL: Ownership violation accepted!"
    
    # Key của Bob không bị ảnh hưởng
    assert f"{bob.pub_key_str}/balance" not in sm.data

def test_state_hash_commitment():
    """Kiểm tra state hash là commitment đơn định"""
    sm1 = StateMachine()
    sm2 = StateMachine()
    alice = KeyPair()
    
    # Apply cùng transactions lên 2 state machines
    tx1 = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/a", "100", 0)
    tx1.signature = alice.sign(tx1.to_dict(include_sig=False), CTX_TX)
    
    tx2 = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/b", "200", 1)
    tx2.signature = alice.sign(tx2.to_dict(include_sig=False), CTX_TX)
    
    sm1.apply_transaction(tx1)
    sm1.apply_transaction(tx2)
    
    sm2.apply_transaction(tx1)
    sm2.apply_transaction(tx2)
    
    # State hash phải giống nhau
    assert sm1.get_state_hash() == sm2.get_state_hash(), "State hash should be deterministic"

if __name__ == "__main__":
    test_apply_transaction_success()
    test_replay_attack()
    test_block_execution()
    test_ownership_violation()
    test_state_hash_commitment()
    print("All State Machine tests passed!")