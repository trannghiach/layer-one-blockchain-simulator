# tests/test_unit_crypto.py
import sys
import os
import pytest

# Thêm thư mục gốc vào đường dẫn để import được src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.crypto import KeyPair, CTX_TX, CTX_BLOCK, CTX_VOTE, verify_signature
from src.models import Transaction, Block, Vote
from src.utils import get_hash

def test_determinism():
    """Kiểm tra tính đơn định của hàm băm (bắt buộc sort keys)"""
    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}
    h1 = get_hash(d1)
    h2 = get_hash(d2)
    assert h1 == h2, "FAIL: Hash không đơn định (Dictionary order ảnh hưởng hash)"

def test_signature_context():
    """Kiểm tra Domain Separation (Chữ ký TX không được dùng cho Block)"""
    alice = KeyPair()
    tx_data = {"sender": alice.pub_key_str, "key": "foo", "value": "bar", "nonce": 0}
    
    # 1. Ký với context TX -> Verify với context TX phải OK
    sig = alice.sign(tx_data, CTX_TX)
    tx_obj = Transaction(alice.pub_key_str, "foo", "bar", 0, sig)
    assert tx_obj.validate() == True
    
    # 2. Verify chữ ký đó với context BLOCK -> Phải Fail
    is_valid_as_block = verify_signature(alice.pub_key_str, tx_data, sig, CTX_BLOCK)
    assert is_valid_as_block == False, "FAIL: Context separation bị hổng!"
    
    # 3. Verify chữ ký đó với context VOTE -> Phải Fail
    is_valid_as_vote = verify_signature(alice.pub_key_str, tx_data, sig, CTX_VOTE)
    assert is_valid_as_vote == False, "FAIL: Context separation bị hổng!"

def test_transaction_integrity():
    """Kiểm tra sửa đổi dữ liệu sẽ làm hỏng chữ ký"""
    alice = KeyPair()
    tx = Transaction(alice.pub_key_str, "A", "100", 1)
    # Ký transaction gốc
    tx.signature = alice.sign(tx.to_dict(include_sig=False), CTX_TX)
    
    # Kẻ tấn công sửa nonce
    tx.nonce = 2 
    assert tx.validate() == False, "FAIL: Transaction bị sửa nhưng vẫn validate thành công"

def test_block_signature_validation():
    """Kiểm tra block signature validation"""
    proposer = KeyPair()
    attacker = KeyPair()
    
    # Block hợp lệ
    block = Block(1, "parent_hash", [], "state_hash", proposer.pub_key_str, timestamp=0)
    block.signature = proposer.sign(block.to_dict(include_sig=False), CTX_BLOCK)
    assert block.validate_signature() == True, "Valid block should pass"
    
    # Block với signature của người khác
    forged_block = Block(1, "parent_hash", [], "state_hash", proposer.pub_key_str, timestamp=0)
    forged_block.signature = attacker.sign(forged_block.to_dict(include_sig=False), CTX_BLOCK)
    assert forged_block.validate_signature() == False, "FAIL: Forged block accepted!"
    
    # Block với signature dùng sai context
    wrong_ctx_block = Block(1, "parent_hash", [], "state_hash", proposer.pub_key_str, timestamp=0)
    wrong_ctx_block.signature = proposer.sign(wrong_ctx_block.to_dict(include_sig=False), CTX_TX)  # Sai context
    assert wrong_ctx_block.validate_signature() == False, "FAIL: Wrong context signature accepted!"

def test_vote_signature_validation():
    """Kiểm tra vote signature validation"""
    voter = KeyPair()
    attacker = KeyPair()
    
    # Vote hợp lệ
    vote = Vote(Vote.PREVOTE, 1, "block_hash_123", voter.pub_key_str)
    vote.signature = voter.sign(vote.to_dict(include_sig=False), CTX_VOTE)
    assert vote.validate() == True, "Valid vote should pass"
    
    # Vote với signature của người khác
    forged_vote = Vote(Vote.PREVOTE, 1, "block_hash_123", voter.pub_key_str)
    forged_vote.signature = attacker.sign(forged_vote.to_dict(include_sig=False), CTX_VOTE)
    assert forged_vote.validate() == False, "FAIL: Forged vote accepted!"
    
    # Vote với height bị sửa
    tampered_vote = Vote(Vote.PREVOTE, 1, "block_hash_123", voter.pub_key_str)
    tampered_vote.signature = voter.sign(tampered_vote.to_dict(include_sig=False), CTX_VOTE)
    tampered_vote.height = 999  # Kẻ tấn công sửa height
    assert tampered_vote.validate() == False, "FAIL: Tampered vote accepted!"

def test_vote_counting():
    """Kiểm tra vote counting và threshold"""
    from src.consensus import ConsensusEngine
    
    # Tạo 8 validators
    validators = [KeyPair() for _ in range(8)]
    validator_keys = [v.pub_key_str for v in validators]
    
    engine = ConsensusEngine("node_id", validator_keys)
    
    # Threshold phải là 6 (8 * 2 // 3 + 1 = 6)
    assert engine.threshold == 6, f"Expected threshold 6, got {engine.threshold}"
    
    # Thêm 5 votes - chưa đủ threshold
    for i in range(5):
        vote = Vote(Vote.PREVOTE, 1, "block_hash", validators[i].pub_key_str)
        vote.signature = validators[i].sign(vote.to_dict(include_sig=False), CTX_VOTE)
        engine.add_vote(vote)
    
    assert engine.check_threshold(1, Vote.PREVOTE, "block_hash") == False, "5 votes should not meet threshold"
    
    # Thêm vote thứ 6 - đủ threshold
    vote6 = Vote(Vote.PREVOTE, 1, "block_hash", validators[5].pub_key_str)
    vote6.signature = validators[5].sign(vote6.to_dict(include_sig=False), CTX_VOTE)
    engine.add_vote(vote6)
    
    assert engine.check_threshold(1, Vote.PREVOTE, "block_hash") == True, "6 votes should meet threshold"

def test_non_validator_vote_rejected():
    """Kiểm tra vote từ non-validator bị từ chối"""
    from src.consensus import ConsensusEngine
    
    validators = [KeyPair() for _ in range(4)]
    validator_keys = [v.pub_key_str for v in validators]
    
    non_validator = KeyPair()  # Không có trong danh sách
    
    engine = ConsensusEngine("node_id", validator_keys)
    
    # Vote từ non-validator
    vote = Vote(Vote.PREVOTE, 1, "block_hash", non_validator.pub_key_str)
    vote.signature = non_validator.sign(vote.to_dict(include_sig=False), CTX_VOTE)
    
    result = engine.add_vote(vote)
    assert result == False, "Vote from non-validator should be rejected"

if __name__ == "__main__":
    # Cho phép chạy trực tiếp bằng python
    test_determinism()
    test_signature_context()
    test_transaction_integrity()
    test_block_signature_validation()
    test_vote_signature_validation()
    test_vote_counting()
    test_non_validator_vote_rejected()
    print("All manual checks passed!")