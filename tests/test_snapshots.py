"""
快照测试模块
用于确保重构过程中解析器输出的一致性
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径，确保能正确导入模块
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from tests.snapshot_logic import SnapshotTester


# pytest测试用例
def test_snapshot_consistency():
    """测试快照一致性"""
    tester = SnapshotTester()
    mismatches = tester.verify_snapshots()
    
    if mismatches:
        error_msg = "快照测试失败，以下文件输出不一致:\n"
        for filename, expected, actual in mismatches:
            error_msg += f"\n文件: {filename}\n"
            if expected.startswith("快照文件不存在") or expected.startswith("处理错误"):
                error_msg += f"错误: {expected}\n"
            else:
                error_msg += f"期望输出长度: {len(expected)} 字符\n"
                error_msg += f"实际输出长度: {len(actual)} 字符\n"
                # 显示前100个字符的差异
                if len(expected) > 100:
                    error_msg += f"期望开头: {expected[:100]}...\n"
                else:
                    error_msg += f"期望内容: {expected}\n"
                if len(actual) > 100:
                    error_msg += f"实际开头: {actual[:100]}...\n"
                else:
                    error_msg += f"实际内容: {actual}\n"
        
        pytest.fail(error_msg)


if __name__ == "__main__":
    # 直接运行时生成快照
    tester = SnapshotTester()
    tester.generate_snapshots()
    print("快照生成完成") 