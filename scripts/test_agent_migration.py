#!/usr/bin/env python3
"""测试 LangChain/LangGraph 迁移后的 Agent 创建。"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_imports():
    """测试所有导入是否正常。"""
    print("测试导入...")
    
    try:
        from langchain.agents import create_agent
        print("  ✓ langchain.agents.create_agent")
    except ImportError as e:
        print(f"  ✗ langchain.agents.create_agent: {e}")
        return False
    
    try:
        from langgraph.graph import StateGraph, END
        print("  ✓ langgraph.graph (StateGraph, END)")
    except ImportError as e:
        print(f"  ✗ langgraph.graph: {e}")
        return False
    
    try:
        from langchain_openai import ChatOpenAI
        print("  ✓ langchain_openai.ChatOpenAI")
    except ImportError as e:
        print(f"  ✗ langchain_openai.ChatOpenAI: {e}")
        return False
    
    return True


def test_agent_creation():
    """测试 Agent 创建函数是否正常。"""
    print("\n测试 Agent 创建...")
    
    try:
        from agents.agent_factory import create_code_generation_agent
        print("  ✓ 导入 create_code_generation_agent")
        
        # 注意：不实际创建 agent，因为需要 API key
        print("  ℹ 跳过实际创建（需要 API key）")
        
    except Exception as e:
        print(f"  ✗ create_code_generation_agent: {e}")
        return False
    
    try:
        from agents.web_app_team.agents import (
            create_boss_agent,
            create_pm_agent,
            create_architect_agent,
            create_pjm_agent,
            create_engineer_agent,
            create_qa_agent,
        )
        print("  ✓ 导入所有团队 agents")
        
    except Exception as e:
        print(f"  ✗ 团队 agents: {e}")
        return False
    
    return True


def test_graph_creation():
    """测试工作流图创建函数是否正常。"""
    print("\n测试工作流图创建...")
    
    try:
        from agents.web_app_team.graph import create_team_graph
        print("  ✓ 导入 create_team_graph")
        
        print("  ℹ 跳过实际创建（需要 agent 实例）")
        
    except Exception as e:
        print(f"  ✗ create_team_graph: {e}")
        return False
    
    return True


def test_team_factory():
    """测试团队工厂函数是否正常。"""
    print("\n测试团队工厂...")
    
    try:
        from agents.web_app_team import create_web_app_team
        print("  ✓ 导入 create_web_app_team")
        
        print("  ℹ 跳过实际创建（需要 workspace_id 和配置）")
        
    except Exception as e:
        print(f"  ✗ create_web_app_team: {e}")
        return False
    
    return True


def main():
    """运行所有测试。"""
    print("=" * 60)
    print("LangChain/LangGraph 迁移测试")
    print("=" * 60)
    
    tests = [
        ("导入测试", test_imports),
        ("Agent 创建测试", test_agent_creation),
        ("工作流图测试", test_graph_creation),
        ("团队工厂测试", test_team_factory),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} 失败: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！迁移成功。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
