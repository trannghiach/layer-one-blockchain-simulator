# Layer 1 Blockchain Simulator

## 1. Giới thiệu
Dự án mô phỏng một mạng lưới Blockchain Layer 1 với cơ chế đồng thuận dựa trên biểu quyết (Voting-based Consensus), đảm bảo tính an toàn (Safety) và tính sống (Liveness) ngay cả trong điều kiện mạng không tin cậy (mất gói tin, độ trễ ngẫu nhiên).

## 2. Cài đặt môi trường
Yêu cầu: Python 3.8 trở lên.
```bash
# Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

```

## 3. Hướng dẫn chạy

### Cách 1: Chạy kiểm thử tự động (Khuyên dùng)

Hệ thống bao gồm các bài test Unit, Integration và End-to-End (E2E).
Lệnh dưới đây sẽ chạy toàn bộ kịch bản, bao gồm cả kịch bản mạng rớt gói tin (Chaos Network):

```bash
pytest

```

*Kết quả mong đợi: `8 passed`.*

### Cách 2: Kiểm chứng tính Đơn định (Determinism Check)

Đây là yêu cầu quan trọng của đồ án. Script này chạy mô phỏng 2 lần độc lập với cùng một Seed và so sánh Hash của Trạng thái cuối cùng.

```bash
python run_determinism_check.py

```

*Kết quả mong đợi:*

```text
>>> SUCCESS: Determinism Verified! (10/10)

```

## 5. Cấu trúc thư mục

* `src/`: Mã nguồn chính (Node, Consensus, Simulator, Crypto).
* `tests/`: Các file kiểm thử (Unit test & E2E).
* `logs/`: Nơi lưu nhật ký chạy mô phỏng.
* `run_determinism_check.py`: Script chứng minh tính đúng đắn.
