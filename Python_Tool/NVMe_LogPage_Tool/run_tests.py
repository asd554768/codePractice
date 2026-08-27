"""單元測試執行腳本。

使用方式: python run_tests.py
"""
import unittest
import sys
import os

# 加入專案目錄至 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_all_tests():
    """搜尋並執行 tests 目錄下的所有單元測試。"""
    test_loader = unittest.TestLoader()
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")
    test_suite = test_loader.discover(start_dir=test_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    print("=" * 70)
    print("開始執行 NVMe Log Page Tool 單元測試套件...")
    print("=" * 70)
    
    result = runner.run(test_suite)
    
    print("\n" + "=" * 70)
    print(f"測試總數: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗 (Failures): {len(result.failures)}")
    print(f"錯誤 (Errors): {len(result.errors)}")
    print("=" * 70)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
