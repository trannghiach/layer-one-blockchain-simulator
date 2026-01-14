# tests/test_e2e_complete.py
"""
Comprehensive End-to-End Tests theo yêu cầu đề bài Lab01:
1. Only one block becomes finalized at each height
2. Messages/transactions with invalid signatures or wrong contexts are rejected
3. Replays/duplicates are ignored without breaking safety
4. Delayed or dropped messages do not cause conflicting finalization
5. Identical runs produce identical logs and final state
"""

import sys
import os
import hashlib
import logging
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.node import Node
from src.simulator import Simulator
from src.crypto import KeyPair, CTX_TX, CTX_BLOCK, CTX_VOTE, verify_signature
from src.models import Transaction, Block, Vote
from config.node_config import CONFIG


def setup_network(config_override=None):
    """Helper function để setup mạng với 8 nodes"""
    network_config = CONFIG["network"].copy()
    if config_override:
        network_config.update(config_override)
    
    sim = Simulator(network_config)
    
    node_names = CONFIG["nodes"]
    num_nodes = len(node_names)
    
    nodes = []
    validator_keys = []
    for i in range(num_nodes):
        n = Node(node_names[i], sim, [], config=CONFIG)
        nodes.append(n)
        validator_keys.append(n.key_pair.pub_key_str)
        sim.register_node(n)
    
    threshold = (num_nodes * 2) // 3 + 1
    
    for n in nodes:
        n.consensus.validators = validator_keys
        n.consensus.n = num_nodes
        n.consensus.threshold = threshold
        for peer in nodes:
            n.add_peer(peer.node_id)
    
    return sim, nodes, threshold


class TestSafety:
    """Test 1: Only one block becomes finalized at each height (Safety)"""
    
    def test_single_block_finalized_per_height(self):
        """Đảm bảo chỉ có 1 block được finalize ở mỗi height"""
        sim, nodes, _ = setup_network({"drop_prob": 0.0})
        
        nodes[0].start_consensus()
        sim.run(max_time=10.0)
        
        # Thu thập tất cả block hash đã finalize ở height 1
        finalized_hashes = set()
        for n in nodes:
            if n.finalized_height >= 1 and 1 in n.blocks:
                finalized_hashes.add(n.blocks[1].get_hash())
        
        assert len(finalized_hashes) == 1, "FAIL: Nhiều block khác nhau được finalize ở height 1!"
        print("PASS: Chỉ có 1 block được finalize ở height 1")
    
    def test_no_conflicting_finalization_with_network_issues(self):
        """Test với mạng có drop/delay cao vẫn đảm bảo Safety"""
        sim, nodes, threshold = setup_network({
            "drop_prob": 0.3,  # 30% drop rate
            "max_delay": 0.5
        })
        
        nodes[0].start_consensus()
        sim.run(max_time=30.0)  # Chạy lâu hơn
        
        # Thu thập các block đã finalize
        finalized_blocks = {}
        for n in nodes:
            if n.finalized_height >= 1 and 1 in n.blocks:
                block_hash = n.blocks[1].get_hash()
                if block_hash not in finalized_blocks:
                    finalized_blocks[block_hash] = []
                finalized_blocks[block_hash].append(n.node_id)
        
        # Safety: Không thể có 2 block khác nhau cùng được finalize
        assert len(finalized_blocks) <= 1, f"FAIL: Safety broken! {len(finalized_blocks)} different blocks finalized"
        print(f"PASS: Safety maintained even with 30% drop rate")


class TestInvalidSignatureRejection:
    """Test 2: Invalid signatures and wrong contexts are rejected"""
    
    def test_reject_invalid_transaction_signature(self):
        """Transaction với chữ ký sai phải bị từ chối"""
        sim, nodes, _ = setup_network({"drop_prob": 0.0})
        
        alice = KeyPair()
        bob = KeyPair()
        
        # Tạo TX hợp lệ
        tx = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/test", "value", 0)
        tx.signature = alice.sign(tx.to_dict(include_sig=False), CTX_TX)
        
        # Kẻ tấn công giả mạo signature
        fake_tx = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/test", "hacked", 0)
        fake_tx.signature = bob.sign(fake_tx.to_dict(include_sig=False), CTX_TX)  # Ký bằng key khác
        
        # TX thật phải valid
        assert tx.validate() == True, "Valid TX should pass"
        
        # TX giả phải fail
        assert fake_tx.validate() == False, "FAIL: Forged TX signature accepted!"
        print("PASS: Invalid transaction signature rejected")
    
    def test_reject_wrong_context_signature(self):
        """Chữ ký với context sai phải bị từ chối (Domain Separation)"""
        alice = KeyPair()
        
        tx_data = {"sender": alice.pub_key_str, "key": "test", "value": "123", "nonce": 0}
        
        # Ký với CTX_TX
        sig_as_tx = alice.sign(tx_data, CTX_TX)
        
        # Verify với CTX_TX -> OK
        assert verify_signature(alice.pub_key_str, tx_data, sig_as_tx, CTX_TX) == True
        
        # Verify với CTX_BLOCK -> FAIL (Domain Separation)
        assert verify_signature(alice.pub_key_str, tx_data, sig_as_tx, CTX_BLOCK) == False
        
        # Verify với CTX_VOTE -> FAIL
        assert verify_signature(alice.pub_key_str, tx_data, sig_as_tx, CTX_VOTE) == False
        
        print("PASS: Wrong context signatures rejected (Domain Separation works)")
    
    def test_reject_invalid_vote_signature(self):
        """Vote với chữ ký sai phải bị từ chối"""
        alice = KeyPair()
        bob = KeyPair()
        
        # Vote hợp lệ
        vote = Vote(Vote.PREVOTE, 1, "fake_block_hash", alice.pub_key_str)
        vote.signature = alice.sign(vote.to_dict(include_sig=False), CTX_VOTE)
        assert vote.validate() == True
        
        # Vote với signature sai
        forged_vote = Vote(Vote.PREVOTE, 1, "fake_block_hash", alice.pub_key_str)
        forged_vote.signature = bob.sign(forged_vote.to_dict(include_sig=False), CTX_VOTE)
        assert forged_vote.validate() == False, "FAIL: Forged vote accepted!"
        
        print("PASS: Invalid vote signatures rejected")
    
    def test_reject_invalid_block_signature(self):
        """Block với chữ ký sai phải bị từ chối"""
        alice = KeyPair()
        bob = KeyPair()
        
        block = Block(1, "parent_hash", [], "state_hash", alice.pub_key_str, timestamp=0)
        block.signature = alice.sign(block.to_dict(include_sig=False), CTX_BLOCK)
        
        assert block.validate_signature() == True
        
        # Block với signature của người khác
        forged_block = Block(1, "parent_hash", [], "state_hash", alice.pub_key_str, timestamp=0)
        forged_block.signature = bob.sign(forged_block.to_dict(include_sig=False), CTX_BLOCK)
        
        assert forged_block.validate_signature() == False, "FAIL: Forged block accepted!"
        print("PASS: Invalid block signatures rejected")


class TestDuplicateHandling:
    """Test 3: Replays/duplicates are ignored without breaking safety"""
    
    def test_duplicate_votes_ignored(self):
        """Vote trùng lặp phải bị bỏ qua"""
        sim, nodes, _ = setup_network({"drop_prob": 0.0, "duplicate_prob": 0.5})  # 50% duplicate
        
        nodes[0].start_consensus()
        sim.run(max_time=10.0)
        
        # Kiểm tra Safety vẫn được đảm bảo
        finalized_hashes = set()
        for n in nodes:
            if n.finalized_height >= 1 and 1 in n.blocks:
                finalized_hashes.add(n.blocks[1].get_hash())
        
        assert len(finalized_hashes) == 1, "FAIL: Duplicate votes broke safety!"
        print("PASS: Duplicate votes ignored, safety preserved")
    
    def test_replay_transaction_rejected(self):
        """Transaction replay (cùng nonce) phải bị từ chối"""
        from src.state import StateMachine
        
        sm = StateMachine()
        alice = KeyPair()
        
        # TX đầu tiên với nonce 0
        tx1 = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/a", "100", 0)
        tx1.signature = alice.sign(tx1.to_dict(include_sig=False), CTX_TX)
        
        result1 = sm.apply_transaction(tx1)
        assert result1 == True, "First TX should succeed"
        
        # Replay TX với cùng nonce
        tx_replay = Transaction(alice.pub_key_str, f"{alice.pub_key_str}/a", "999", 0)
        tx_replay.signature = alice.sign(tx_replay.to_dict(include_sig=False), CTX_TX)
        
        result2 = sm.apply_transaction(tx_replay)
        assert result2 == False, "FAIL: Replay TX accepted!"
        
        # Giá trị không bị thay đổi
        assert sm.data[f"{alice.pub_key_str}/a"] == "100"
        print("PASS: Replay transactions rejected")


class TestNetworkResilience:
    """Test 4: Delayed or dropped messages do not cause conflicting finalization"""
    
    def test_high_latency_no_conflict(self):
        """Mạng delay cao vẫn không gây conflict"""
        sim, nodes, _ = setup_network({
            "min_delay": 0.5,
            "max_delay": 2.0,
            "drop_prob": 0.0
        })
        
        nodes[0].start_consensus()
        sim.run(max_time=30.0)
        
        finalized_hashes = set()
        for n in nodes:
            if n.finalized_height >= 1 and 1 in n.blocks:
                finalized_hashes.add(n.blocks[1].get_hash())
        
        assert len(finalized_hashes) <= 1, "FAIL: High latency caused conflicting finalization!"
        print("PASS: High latency network - no conflicting finalization")
    
    def test_partial_network_partition(self):
        """Mạng bị phân mảnh một phần vẫn đảm bảo Safety"""
        sim, nodes, threshold = setup_network({
            "drop_prob": 0.4,  # 40% drop simulates partition
            "max_delay": 0.3
        })
        
        nodes[0].start_consensus()
        sim.run(max_time=30.0)
        
        finalized_hashes = set()
        finalized_count = 0
        for n in nodes:
            if n.finalized_height >= 1:
                finalized_count += 1
                if 1 in n.blocks:
                    finalized_hashes.add(n.blocks[1].get_hash())
        
        # Safety: Không có 2 block khác nhau cùng finalize
        assert len(finalized_hashes) <= 1, "FAIL: Network partition caused safety violation!"
        print(f"PASS: Partial partition - {finalized_count} nodes finalized, safety OK")


class TestDeterminism:
    """Test 5: Identical runs produce identical logs and final state"""
    
    def test_deterministic_execution(self):
        """Chạy 2 lần với cùng seed phải cho kết quả giống nhau"""
        SEED = 999999
        
        def run_once(seed):
            config = {
                "min_delay": 0.01,
                "max_delay": 0.1,
                "drop_prob": 0.1,
                "duplicate_prob": 0.05,
                "seed": seed
            }
            sim = Simulator(config)
            
            node_names = CONFIG["nodes"]
            num_nodes = len(node_names)
            
            nodes = []
            validator_keys = []
            for i in range(num_nodes):
                node_seed = f"node_{i}_{seed}"
                n = Node(node_names[i], sim, [], key_seed=node_seed, config=CONFIG)
                nodes.append(n)
                validator_keys.append(n.key_pair.pub_key_str)
                sim.register_node(n)
            
            threshold = (num_nodes * 2) // 3 + 1
            for n in nodes:
                n.consensus.validators = validator_keys
                n.consensus.n = num_nodes
                n.consensus.threshold = threshold
                for peer in nodes:
                    n.add_peer(peer.node_id)
            
            nodes[0].start_consensus()
            sim.run(max_time=5.0)
            
            # Thu thập trạng thái cuối
            state_hashes = []
            for n in nodes:
                state_hashes.append(n.state_machine.get_state_hash())
            
            return state_hashes
        
        result1 = run_once(SEED)
        result2 = run_once(SEED)
        
        assert result1 == result2, "FAIL: Non-deterministic execution!"
        print("PASS: Deterministic execution verified")


class TestConsensusWithEightNodes:
    """Test consensus hoạt động đúng với 8 nodes (yêu cầu đề bài)"""
    
    def test_eight_node_consensus(self):
        """8 nodes phải đạt được đồng thuận"""
        sim, nodes, threshold = setup_network({"drop_prob": 0.0})
        
        assert len(nodes) == 8, f"Expected 8 nodes, got {len(nodes)}"
        assert threshold == 6, f"Expected threshold 6 (2/3 of 8 + 1), got {threshold}"
        
        nodes[0].start_consensus()
        sim.run(max_time=10.0)
        
        finalized_count = sum(1 for n in nodes if n.finalized_height >= 1)
        assert finalized_count == 8, f"FAIL: Only {finalized_count}/8 nodes finalized"
        
        print(f"PASS: All 8 nodes reached consensus (threshold={threshold})")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Running E2E Tests for Lab01 Requirements")
    print("="*60 + "\n")
    
    # Test Safety
    print("\n--- Test Safety ---")
    safety_tests = TestSafety()
    safety_tests.test_single_block_finalized_per_height()
    safety_tests.test_no_conflicting_finalization_with_network_issues()
    
    # Test Invalid Signature Rejection
    print("\n--- Test Invalid Signature Rejection ---")
    sig_tests = TestInvalidSignatureRejection()
    sig_tests.test_reject_invalid_transaction_signature()
    sig_tests.test_reject_wrong_context_signature()
    sig_tests.test_reject_invalid_vote_signature()
    sig_tests.test_reject_invalid_block_signature()
    
    # Test Duplicate Handling
    print("\n--- Test Duplicate Handling ---")
    dup_tests = TestDuplicateHandling()
    dup_tests.test_duplicate_votes_ignored()
    dup_tests.test_replay_transaction_rejected()
    
    # Test Network Resilience
    print("\n--- Test Network Resilience ---")
    net_tests = TestNetworkResilience()
    net_tests.test_high_latency_no_conflict()
    net_tests.test_partial_network_partition()
    
    # Test Determinism
    print("\n--- Test Determinism ---")
    det_tests = TestDeterminism()
    det_tests.test_deterministic_execution()
    
    # Test 8 Nodes
    print("\n--- Test 8 Node Consensus ---")
    eight_tests = TestConsensusWithEightNodes()
    eight_tests.test_eight_node_consensus()
    
    print("\n" + "="*60)
    print("ALL E2E TESTS PASSED!")
    print("="*60)
