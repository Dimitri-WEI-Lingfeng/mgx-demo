#!/usr/bin/env python3
"""测试开发服务器管理工具。

这个脚本演示如何使用新的开发服务器管理工具。
"""

import asyncio
from agents.context import set_context
from agents.context.memory import InMemoryContext
from agents.web_app_team.tools.docker_tools import (
    start_dev_server,
    get_dev_server_status,
    get_dev_server_logs,
    stop_dev_server,
)


async def test_dev_server_tools():
    """测试开发服务器管理工具。"""
    
    # 创建上下文
    context = InMemoryContext(
        workspace_path='./workspace',
        auto_create_container=True,
    )
    
    async with context:
        # 设置上下文
        set_context(context)
        
        print("=" * 60)
        print("测试开发服务器管理工具")
        print("=" * 60)
        
        # 1. 检查初始状态
        print("\n1. 检查初始状态...")
        print("-" * 60)
        result = get_dev_server_status.invoke({})
        print(result)
        
        # 2. 启动开发服务器
        print("\n2. 启动开发服务器...")
        print("-" * 60)
        result = start_dev_server.invoke({
            "command": "npm run dev",
            "port": 3000
        })
        print(result)
        
        # 等待服务器启动
        print("\n等待服务器启动（5 秒）...")
        await asyncio.sleep(5)
        
        # 3. 再次检查状态
        print("\n3. 检查运行状态...")
        print("-" * 60)
        result = get_dev_server_status.invoke({})
        print(result)
        
        # 4. 查看日志
        print("\n4. 查看最近的日志（最后 20 行）...")
        print("-" * 60)
        result = get_dev_server_logs.invoke({"tail": 20})
        print(result)
        
        # 5. 停止开发服务器
        print("\n5. 停止开发服务器...")
        print("-" * 60)
        result = stop_dev_server.invoke({})
        print(result)
        
        # 6. 确认已停止
        print("\n6. 确认已停止...")
        print("-" * 60)
        result = get_dev_server_status.invoke({})
        print(result)
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)


async def test_restart_scenario():
    """测试重启场景。"""
    
    context = InMemoryContext(
        workspace_path='./workspace',
        auto_create_container=True,
    )
    
    async with context:
        set_context(context)
        
        print("\n" + "=" * 60)
        print("测试重启场景")
        print("=" * 60)
        
        # 1. 启动
        print("\n1. 首次启动...")
        result = start_dev_server.invoke({"command": "npm run dev"})
        print(result)
        
        await asyncio.sleep(3)
        
        # 2. 尝试再次启动（应该提示已在运行）
        print("\n2. 尝试再次启动（应该提示已在运行）...")
        result = start_dev_server.invoke({"command": "npm run dev"})
        print(result)
        
        # 3. 停止
        print("\n3. 停止服务器...")
        result = stop_dev_server.invoke({})
        print(result)
        
        # 4. 重新启动
        print("\n4. 重新启动...")
        result = start_dev_server.invoke({"command": "pnpm dev"})
        print(result)
        
        # 5. 清理
        print("\n5. 清理...")
        result = stop_dev_server.invoke({})
        print(result)
        
        print("\n测试完成！")


def main():
    """主函数。"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "restart":
        asyncio.run(test_restart_scenario())
    else:
        asyncio.run(test_dev_server_tools())


if __name__ == '__main__':
    main()
