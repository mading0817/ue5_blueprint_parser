"""
快照生成脚本
手动运行此脚本来生成/更新所有快照文件
"""

from snapshot_logic import SnapshotTester


if __name__ == "__main__":
    print("开始生成快照...")
    tester = SnapshotTester()
    tester.generate_snapshots()
    print("快照生成完成！") 