from collections import defaultdict

class ConsensusEngine:
    def __init__(self, node_id, validators):
        self.node_id = node_id
        self.validators = validators # Danh sách Public Key của các validators
        self.n = len(validators)
        # Ngưỡng đồng thuận: > 2/3 (Strict Majority)
        self.threshold = (self.n * 2) // 3 + 1
        
        # Kho lưu trữ phiếu bầu: votes[height][phase][block_hash] = {voter1, voter2}
        # Dùng set để tự động loại bỏ phiếu trùng lặp từ cùng 1 người
        self.votes = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        
        # Trạng thái hiện tại
        self.current_height = 1
        self.locked_block = None # Block mình đã vote (để đảm bảo Safety)

    def add_vote(self, vote) -> bool:
        """
        Lưu phiếu bầu vào kho.
        Trả về True nếu đây là phiếu mới hợp lệ.
        """
        # Kiểm tra voter có trong danh sách validator không
        if vote.voter not in self.validators:
            return False
            
        # Lưu phiếu
        self.votes[vote.height][vote.type][vote.block_hash].add(vote.voter)
        return True

    def check_threshold(self, height, phase, block_hash) -> bool:
        """Kiểm tra xem block_hash ở phase này đã đủ phiếu chưa"""
        count = len(self.votes[height][phase][block_hash])
        return count >= self.threshold

    def get_voting_power(self):
        return self.n