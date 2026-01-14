# tests/test_unit_crypto.py
import sys
import os
import pytest

# Thêm thư mục gốc vào đường dẫn để import được src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.crypto import KeyPair, CTX_TX, CTX_BLOCK
from src.models import Transaction, Block
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
    from src.crypto import verify_signature
    is_valid_as_block = verify_signature(alice.pub_key_str, tx_data, sig, CTX_BLOCK)
    assert is_valid_as_block == False, "FAIL: Context separation bị hổng!"

def test_transaction_integrity():
    """Kiểm tra sửa đổi dữ liệu sẽ làm hỏng chữ ký"""
    alice = KeyPair()
    tx = Transaction(alice.pub_key_str, "A", "100", 1)
    # Ký transaction gốc
    tx.signature = alice.sign(tx.to_dict(include_sig=False), CTX_TX)
    
    # Kẻ tấn công sửa nonce
    tx.nonce = 2 
    assert tx.validate() == False, "FAIL: Transaction bị sửa nhưng vẫn validate thành công"

if __name__ == "__main__":
    # Cho phép chạy trực tiếp bằng python
    test_determinism()
    test_signature_context()
    test_transaction_integrity()
    print("All manual checks passed!")