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

    def receive(self, sender_id: str, message: dict):
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
            if not vote.validate(): return
            
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