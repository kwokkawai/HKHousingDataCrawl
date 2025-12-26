#!/usr/bin/env python3
"""
依赖检查脚本
验证所有必需的依赖是否已安装在虚拟环境中
"""

import sys
from importlib import import_module
from typing import Dict, List, Tuple


# 定义依赖包及其用途
REQUIRED_PACKAGES = {
    "crawl4ai": {
        "required": True,
        "description": "核心爬虫框架",
        "used_in": ["feasibility_test.py", "efficiency_test.py"]
    }
}

OPTIONAL_PACKAGES = {
    "psutil": {
        "required": False,
        "description": "系统进程和系统利用率库，用于内存监控",
        "used_in": ["efficiency_test.py"]
    },
    "matplotlib": {
        "required": False,
        "description": "数据可视化库，用于生成图表",
        "used_in": ["visualize_results.py"]
    }
}

ALL_PACKAGES = {**REQUIRED_PACKAGES, **OPTIONAL_PACKAGES}


def check_package(package_name: str) -> Tuple[bool, str, str]:
    """
    检查包是否已安装
    
    Returns:
        (is_installed, version, error_message)
    """
    try:
        module = import_module(package_name)
        version = getattr(module, '__version__', 'unknown')
        return True, version, ""
    except ImportError as e:
        return False, "", str(e)
    except Exception as e:
        return False, "", f"Unexpected error: {str(e)}"


def check_dependencies() -> Dict[str, Dict]:
    """检查所有依赖"""
    results = {}
    
    for package_name, info in ALL_PACKAGES.items():
        is_installed, version, error = check_package(package_name)
        results[package_name] = {
            "installed": is_installed,
            "version": version,
            "required": info["required"],
            "description": info["description"],
            "used_in": info["used_in"],
            "error": error
        }
    
    return results


def print_report(results: Dict[str, Dict]):
    """打印检查报告"""
    print("=" * 70)
    print("依赖包检查报告")
    print("=" * 70)
    print(f"Python 版本: {sys.version}")
    print(f"Python 路径: {sys.executable}")
    print("=" * 70)
    
    # 必需依赖
    print("\n【必需依赖】")
    print("-" * 70)
    required_ok = True
    for package_name, result in results.items():
        if result["required"]:
            status = "✓ 已安装" if result["installed"] else "✗ 未安装"
            version_info = f" (版本: {result['version']})" if result["installed"] else ""
            print(f"{package_name:20} {status:15} {version_info}")
            print(f"  用途: {result['description']}")
            print(f"  使用位置: {', '.join(result['used_in'])}")
            if not result["installed"]:
                required_ok = False
                print(f"  错误: {result['error']}")
            print()
    
    # 可选依赖
    print("\n【可选依赖】")
    print("-" * 70)
    for package_name, result in results.items():
        if not result["required"]:
            status = "✓ 已安装" if result["installed"] else "○ 未安装（可选）"
            version_info = f" (版本: {result['version']})" if result["installed"] else ""
            print(f"{package_name:20} {status:15} {version_info}")
            print(f"  用途: {result['description']}")
            print(f"  使用位置: {', '.join(result['used_in'])}")
            if not result["installed"]:
                print(f"  说明: 未安装不影响核心功能，但相关功能将受限")
            print()
    
    # 总结
    print("=" * 70)
    print("检查总结")
    print("=" * 70)
    
    required_count = sum(1 for r in results.values() if r["required"])
    required_installed = sum(1 for r in results.values() if r["required"] and r["installed"])
    
    optional_count = sum(1 for r in results.values() if not r["required"])
    optional_installed = sum(1 for r in results.values() if not r["required"] and r["installed"])
    
    print(f"必需依赖: {required_installed}/{required_count} 已安装")
    print(f"可选依赖: {optional_installed}/{optional_count} 已安装")
    
    if required_ok:
        print("\n✓ 所有必需依赖已安装，项目可以正常运行")
    else:
        print("\n✗ 部分必需依赖未安装，请运行以下命令安装：")
        print("  pip install -r requirements.txt")
    
    print("=" * 70)
    
    return required_ok


def main():
    """主函数"""
    print("\n正在检查依赖包...\n")
    
    results = check_dependencies()
    all_required_ok = print_report(results)
    
    # 返回退出码
    sys.exit(0 if all_required_ok else 1)


if __name__ == "__main__":
    main()

