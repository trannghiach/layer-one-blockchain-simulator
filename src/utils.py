import json
import hashlib

def deterministic_encode(data: dict) -> bytes:
    """
    Chuyển dictionary thành bytes theo chuẩn JSON.
    Bắt buộc sort_keys=True để đảm bảo tính đơn định.
    separators=(',', ':') loại bỏ khoảng trắng thừa.
    """
    if data is None:
        return b'null'
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')

def get_hash(data: dict) -> str:
    """
    Trả về chuỗi hex SHA-256 của data.
    """
    encoded = deterministic_encode(data)
    return hashlib.sha256(encoded).hexdigest()