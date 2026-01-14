import hashlib
from src.crypto import KeyPair, CTX_VOTE, CTX_BLOCK, CTX_TX
from src.state import StateMachine
from src.models import Block, Transaction, Vote
from src.consensus import ConsensusEngine

class Node:
    # Giá trị mặc định cho retry_count
    DEFAULT_RETRY_COUNT = 4
    
    def __init__(self, node_id: str, simulator, validators: list, key_seed=None, config=None):
        self.node_id = node_id
        self.sim = simulator
        self.config = config or {}
        
        # Lấy cấu hình consensus
        consensus_config = self.config.get("consensus", {})
        self.retry_count = consensus_config.get("retry_count", self.DEFAULT_RETRY_COUNT)
        
        # Nếu có key_seed, tạo key pair cố định để đảm bảo tính đơn định (Determinism)
        if key_seed:
            seed_bytes = hashlib.sha256(str(key_seed).encode()).digest()
            self.key_pair = KeyPair(seed_bytes)
        else:
            self.key_pair = KeyPair()
            
        self.peers = []
        
        # Core components
        self.state_machine = StateMachine()
        self.consensus = ConsensusEngine(self.key_pair.pub_key_str, validators)
        
        # Storage
        self.blocks = {} 
        self.mempool = [] 
        
        # Consensus State
        self.current_height = 1
        self.has_prevoted = False
        self.has_precommitted = False
        self.finalized_height = 0
        
        # Pending block bodies (waiting for header acceptance)
        self.pending_headers = {}  # {block_hash: header_data}
        self.received_bodies = {}  # {block_hash: body_data}
        
        # Tracking để loại bỏ duplicates
        self.seen_votes = set()  # {(vote_type, height, block_hash, voter)}
        self.seen_txs = set()    # {tx_signature}

    def add_peer(self, peer_id: str):
        if peer_id not in self.peers and peer_id != self.node_id:
            self.peers.append(peer_id)

    def send_to_network(self, target_id: str, message: dict):
        self.sim.send_message(self.node_id, target_id, message)

    def broadcast(self, message: dict):
        for peer_id in self.peers:
            # Gửi lặp lại theo cấu hình retry_count để đảm bảo độ tin cậy trong mạng giả lập có tỷ lệ drop cao
            for _ in range(self.retry_count):
                self.send_to_network(peer_id, message)

    def broadcast_block_header_body(self, block: Block):
        """Broadcast block theo cơ chế Header trước, Body sau (theo yêu cầu đề bài)"""
        header = {
            "msg_type": "HEADER",
            "height": block.height,
            "parent_hash": block.parent_hash,
            "state_hash": block.state_hash,
            "proposer": block.proposer,
            "signature": block.signature,
            "timestamp": block.timestamp,
            "block_hash": block.get_hash()
        }
        
        body = {
            "msg_type": "BODY",
            "block_hash": block.get_hash(),
            "txs": [tx.to_dict() for tx in block.txs]
        }
        
        block_hash = block.get_hash()
        
        for peer_id in self.peers:
            for _ in range(self.retry_count):
                # Gửi header trước
                self.sim.send_header(self.node_id, peer_id, header)
                # Gửi body sau (simulator sẽ đợi header được accept)
                self.sim.send_body(self.node_id, peer_id, body, block_hash)

    def receive_header(self, sender_id: str, header: dict):
        """Xử lý khi nhận được block header"""
        try:
            block_hash = header.get("block_hash")
            height = header.get("height")
            
            if height != self.current_height:
                return
                
            # Verify header signature
            header_data = {
                "height": header["height"],
                "parent_hash": header["parent_hash"],
                "txs": [],  # Header không có txs
                "state_hash": header["state_hash"],
                "proposer": header["proposer"],
                "timestamp": header["timestamp"]
            }
            
            from src.crypto import verify_signature
            if not verify_signature(header["proposer"], header_data, header["signature"], CTX_BLOCK):
                print(f"Invalid header signature from {sender_id}")
                return
            
            # Lưu header và accept nó
            self.pending_headers[block_hash] = header
            self.sim.accept_header(self.node_id, block_hash)
            
            # Nếu đã có body, xử lý ngay
            if block_hash in self.received_bodies:
                self._process_complete_block(block_hash)
                
        except Exception as e:
            print(f"Error handling header: {e}")

    def receive_body(self, sender_id: str, body: dict):
        """Xử lý khi nhận được block body"""
        try:
            block_hash = body.get("block_hash")
            
            # Lưu body
            self.received_bodies[block_hash] = body
            
            # Nếu đã có header, xử lý ngay
            if block_hash in self.pending_headers:
                self._process_complete_block(block_hash)
                
        except Exception as e:
            print(f"Error handling body: {e}")

    def _process_complete_block(self, block_hash: str):
        """Xử lý khi đã có cả header và body của block"""
        header = self.pending_headers.get(block_hash)
        body = self.received_bodies.get(block_hash)
        
        if not header or not body:
            return
            
        # Tạo block message đầy đủ và xử lý
        full_msg = {
            "height": header["height"],
            "parent_hash": header["parent_hash"],
            "txs": body["txs"],
            "state_hash": header["state_hash"],
            "proposer": header["proposer"],
            "signature": header["signature"],
            "timestamp": header["timestamp"]
        }
        
        self.handle_block(full_msg)
        
        # Cleanup
        del self.pending_headers[block_hash]
        del self.received_bodies[block_hash]

    def receive(self, sender_id: str, message: dict):
        # Xử lý header/body riêng nếu có msg_type
        if message.get("msg_type") == "HEADER":
            self.receive_header(sender_id, message)
            return
        elif message.get("msg_type") == "BODY":
            self.receive_body(sender_id, message)
            return
            
        if "txs" in message:
            self.handle_block(message)
        elif "type" in message and message["type"] in [Vote.PREVOTE, Vote.PRECOMMIT]:
            self.handle_vote(message)
        elif "key" in message and "value" in message:
            self.handle_transaction(sender_id, message)

    def create_transaction(self, key: str, value: str):
        my_nonce = self.state_machine.nonces.get(self.key_pair.pub_key_str, -1) + 1
        tx = Transaction(self.key_pair.pub_key_str, key, value, my_nonce)
        tx.signature = self.key_pair.sign(tx.to_dict(include_sig=False), CTX_TX)
        self.broadcast(tx.to_dict())
        return tx

    def handle_transaction(self, sender_id: str, msg: dict):
        try:
            tx = Transaction(msg['sender'], msg['key'], msg['value'], msg['nonce'], msg['signature'])
            if self.state_machine.validate_transaction(tx):
                if not any(t.signature == tx.signature for t in self.mempool):
                    self.mempool.append(tx)
        except Exception:
            pass

    def start_consensus(self):
        if not self.consensus.validators: return
        proposer_idx = (self.current_height - 1) % len(self.consensus.validators)
        proposer_pub = self.consensus.validators[proposer_idx]
        
        if proposer_pub == self.key_pair.pub_key_str:
            self.create_and_propose_block()

    def create_and_propose_block(self):
        parent_hash = "GENESIS_HASH"
        if self.current_height > 1:
            prev_block = self.blocks.get(self.current_height - 1)
            if prev_block:
                parent_hash = prev_block.get_hash()
        
        current_state_hash = self.state_machine.get_state_hash()
        txs_to_include = self.mempool[:] 
        
        # Block timestamp phải lấy từ Simulator để đảm bảo tính đơn định giữa các lần chạy
        block = Block(
            height=self.current_height,
            parent_hash=parent_hash,
            txs=txs_to_include,
            state_hash=current_state_hash,
            proposer=self.key_pair.pub_key_str,
            timestamp=self.sim.current_time 
        )
        
        block.signature = self.key_pair.sign(block.to_dict(include_sig=False), CTX_BLOCK)
        
        print(f"[{self.sim.current_time:.2f}] Node {self.node_id} PROPOSING block {block.height}")
        block_msg = block.to_dict()
        self.broadcast(block_msg)
        self.handle_block(block_msg)

    def handle_block(self, msg: dict):
        try:
            tx_objs = [Transaction(t['sender'], t['key'], t['value'], t['nonce'], t['signature']) for t in msg['txs']]
            block = Block(msg['height'], msg['parent_hash'], tx_objs, msg['state_hash'], msg['proposer'], msg['signature'], timestamp=msg.get('timestamp'))
            
            if block.height != self.current_height: return
            if not block.validate_signature(): return

            self.blocks[block.height] = block
            
            if not self.has_prevoted:
                self.broadcast_vote(Vote.PREVOTE, block.get_hash())
                self.has_prevoted = True
        except Exception as e:
            print(f"Error handling block: {e}")

    def handle_vote(self, msg: dict):
        try:
            vote = Vote(msg['type'], msg['height'], msg['block_hash'], msg['voter'], msg['signature'])
            
            # Kiểm tra duplicate vote
            vote_key = (vote.type, vote.height, vote.block_hash, vote.voter)
            if vote_key in self.seen_votes:
                return  # Bỏ qua vote trùng lặp
            
            if not vote.validate(): return
            
            # Đánh dấu đã thấy vote này
            self.seen_votes.add(vote_key)
            
            is_new = self.consensus.add_vote(vote)
            if not is_new: return
            
            block_hash = vote.block_hash
            
            if vote.type == Vote.PREVOTE:
                if self.consensus.check_threshold(vote.height, Vote.PREVOTE, block_hash):
                    if not self.has_precommitted and vote.height == self.current_height:
                        print(f"[{self.sim.current_time:.2f}] Node {self.node_id} reached 2/3 PREVOTE -> PRECOMMIT")
                        self.broadcast_vote(Vote.PRECOMMIT, block_hash)
                        self.has_precommitted = True

            elif vote.type == Vote.PRECOMMIT:
                if self.consensus.check_threshold(vote.height, Vote.PRECOMMIT, block_hash):
                    if self.finalized_height < vote.height:
                        self.finalize_block(vote.height, block_hash)
        except Exception as e:
            print(f"Error handling vote: {e}")

    def broadcast_vote(self, vote_type, block_hash):
        vote = Vote(vote_type, self.current_height, block_hash, self.key_pair.pub_key_str)
        vote.signature = self.key_pair.sign(vote.to_dict(include_sig=False), CTX_VOTE)
        msg = vote.to_dict()
        self.broadcast(msg)
        self.handle_vote(msg)

    def finalize_block(self, height, block_hash):
        print(f"[{self.sim.current_time:.2f}] Node {self.node_id} FINALIZED block {height}")
        self.finalized_height = height
        
        if height in self.blocks:
            block = self.blocks[height]
            if block.get_hash() == block_hash:
                success = self.state_machine.apply_block(block)
                if success: 
                    self.mempool = [] 
        
        self.current_height += 1
        self.has_prevoted = False
        self.has_precommitted = False