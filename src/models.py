import time
from src.utils import get_hash
from src.crypto import verify_signature, CTX_TX, CTX_BLOCK, CTX_VOTE

class Transaction:
    def __init__(self, sender_pub: str, key: str, value: str, nonce: int, signature: str = ""):
        self.sender = sender_pub
        self.key = key
        self.value = value
        self.nonce = nonce
        self.signature = signature

    def to_dict(self, include_sig=True):
        data = {
            "sender": self.sender,
            "key": self.key,
            "value": self.value,
            "nonce": self.nonce
        }
        if include_sig:
            data["signature"] = self.signature
        return data

    def validate(self) -> bool:
        payload = self.to_dict(include_sig=False)
        return verify_signature(self.sender, payload, self.signature, CTX_TX)

class Block:
    def __init__(self, height: int, parent_hash: str, txs: list, state_hash: str, proposer: str, signature: str = "", timestamp=None):
        self.height = height
        self.parent_hash = parent_hash
        self.txs = txs
        self.state_hash = state_hash
        self.proposer = proposer
        self.signature = signature
        
        # Sử dụng timestamp từ simulator nếu có, ngược lại dùng system time
        if timestamp is not None:
            self.timestamp = int(timestamp)
        else:
            self.timestamp = int(time.time())

    def to_dict(self, include_sig=True):
        data = {
            "height": self.height,
            "parent_hash": self.parent_hash,
            "txs": [tx.to_dict() for tx in self.txs],
            "state_hash": self.state_hash,
            "proposer": self.proposer,
            "timestamp": self.timestamp
        }
        if include_sig:
            data["signature"] = self.signature
        return data

    def get_hash(self) -> str:
        return get_hash(self.to_dict(include_sig=True))

    def validate_signature(self) -> bool:
        payload = self.to_dict(include_sig=False)
        return verify_signature(self.proposer, payload, self.signature, CTX_BLOCK)

class Vote:
    PREVOTE = "PREVOTE"
    PRECOMMIT = "PRECOMMIT"

    def __init__(self, vote_type: str, height: int, block_hash: str, voter: str, signature: str = ""):
        self.type = vote_type
        self.height = height
        self.block_hash = block_hash
        self.voter = voter
        self.signature = signature

    def to_dict(self, include_sig=True):
        data = {
            "type": self.type,
            "height": self.height,
            "block_hash": self.block_hash,
            "voter": self.voter
        }
        if include_sig:
            data["signature"] = self.signature
        return data

    def validate(self) -> bool:
        payload = self.to_dict(include_sig=False)
        return verify_signature(self.voter, payload, self.signature, CTX_VOTE)