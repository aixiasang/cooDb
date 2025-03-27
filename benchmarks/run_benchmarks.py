#!/usr/bin/env python
"""
CoolDB Redis基准测试运行脚本

这个脚本简化了基准测试的运行过程，提供了多种预设的测试配置。

使用方法:
    python run_benchmarks.py [选项]

选项:
    --profile PROFILE   预设配置文件，可选值: quick, standard, comprehensive
                        默认为quick
    --compare           是否与标准Redis进行比较（需要标准Redis运行在6378端口）
    
示例:
    # 运行快速测试
    python run_benchmarks.py
    
    # 运行标准测试并与Redis比较
    python run_benchmarks.py --profile standard --compare
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# 确保可以导入benchmarks模块
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CoolDB Redis基准测试运行脚本")
    parser.add_argument("--profile", type=str, default="quick", 
                       help="测试配置文件 (quick, standard, comprehensive)")
    parser.add_argument("--compare", action="store_true", 
                       help="与标准Redis比较")
    
    args = parser.parse_args()
    
    # 获取脚本路径
    script_dir = Path(__file__).parent
    benchmark_script = script_dir / "redis_benchmark.py"
    
    # 检查基准测试脚本是否存在
    if not benchmark_script.exists():
        print(f"错误: 基准测试脚本不存在: {benchmark_script}")
        return 1
    
    # 预设配置
    profiles = {
        "quick": {
            "operations": 5000,
            "clients": 5,
            "value_size": 50,
            "tests": "string,hash"
        },
        "standard": {
            "operations": 20000,
            "clients": 10,
            "value_size": 100,
            "tests": "string,hash,set"
        },
        "comprehensive": {
            "operations": 50000,
            "clients": 20,
            "value_size": 200,
            "tests": "string,hash,set"
        }
    }
    
    # 获取选定的配置
    if args.profile not in profiles:
        print(f"错误: 不支持的配置: {args.profile}")
        print(f"可用配置: {', '.join(profiles.keys())}")
        return 1
    
    profile = profiles[args.profile]
    
    # 构建命令
    cmd = [
        sys.executable,
        str(benchmark_script),
        f"--operations={profile['operations']}",
        f"--clients={profile['clients']}",
        f"--value-size={profile['value_size']}",
        f"--tests={profile['tests']}"
    ]
    
    if args.compare:
        cmd.append("--compare")
    
    # 运行基准测试
    print(f"使用 {args.profile} 配置运行基准测试...")
    print(f"操作数: {profile['operations']}, 客户端: {profile['clients']}, 值大小: {profile['value_size']}字节")
    print(f"运行测试: {profile['tests']}")
    if args.compare:
        print("将会与标准Redis进行比较")
    print("\n" + "=" * 60)
    
    # 执行命令
    subprocess.run(cmd)
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 