import nacl.signing
import nacl.encoding
import nacl.exceptions
from src.utils import deterministic_encode

# Context strings for Domain Separation
CTX_TX = "TX: CHAIN_2025"      
CTX_BLOCK = "HEADER: CHAIN_2025" 
CTX_VOTE = "VOTE: CHAIN_2025"    

class KeyPair:
    def __init__(self, seed_bytes: bytes = None):
        """
        Khởi tạo cặp khóa Ed25519.
        Nếu có seed_bytes, khóa sẽ được tạo đơn định (dùng cho testing/reproducibility).
        Nếu không, khóa sẽ được tạo ngẫu nhiên.
        """
        if seed_bytes:
            self.signing_key = nacl.signing.SigningKey(seed_bytes)
        else:
            self.signing_key = nacl.signing.SigningKey.generate()
            
        self.verify_key = self.signing_key.verify_key
        self.pub_key_str = self.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')

    def sign(self, message: dict, context: str) -> str:
        msg_bytes = deterministic_encode(message)
        full_payload = context.encode('utf-8') + msg_bytes
        signed = self.signing_key.sign(full_payload)
        return signed.signature.hex()

def verify_signature(pub_key_hex: str, message: dict, signature_hex: str, context: str) -> bool:
    try:
        verify_key = nacl.signing.VerifyKey(pub_key_hex, encoder=nacl.encoding.HexEncoder)
        msg_bytes = deterministic_encode(message)
        full_payload = context.encode('utf-8') + msg_bytes
        verify_key.verify(full_payload, bytes.fromhex(signature_hex))
        return True
    except (nacl.exceptions.BadSignatureError, ValueError):
        return False