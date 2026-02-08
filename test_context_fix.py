"""测试上下文在多线程环境下的传播。

这个脚本验证 contextvars 修复是否解决了 LangChain agent 在不同线程
执行工具时无法访问上下文的问题。
"""

import threading
import time
from src.agents.context import InMemoryContext, set_context, get_context, require_context


def test_basic_context():
    """测试基本的上下文设置和获取。"""
    print("\n=== 测试 1: 基本上下文 ===")
    
    context = InMemoryContext(
        workspace_path='./workspace',
        session_id='test-session',
        workspace_id='test-workspace'
    )
    set_context(context)
    
    retrieved = get_context()
    assert retrieved is not None
    assert retrieved.session_id == 'test-session'
    assert retrieved.workspace_id == 'test-workspace'
    
    print("✅ 基本上下文设置和获取成功")


def test_context_in_child_thread():
    """测试子线程是否能访问父线程的上下文。"""
    print("\n=== 测试 2: 子线程继承父线程上下文 ===")
    
    # 在主线程设置上下文
    context = InMemoryContext(
        workspace_path='./workspace',
        session_id='parent-session',
        workspace_id='parent-workspace'
    )
    set_context(context)
    
    result = {'success': False, 'error': None}
    
    def child_thread_task():
        """子线程任务 - 尝试获取上下文"""
        try:
            ctx = require_context()
            assert ctx.session_id == 'parent-session'
            assert ctx.workspace_id == 'parent-workspace'
            result['success'] = True
            print(f"  子线程成功访问上下文: {ctx.workspace_id}")
        except Exception as e:
            result['error'] = str(e)
            print(f"  ❌ 子线程访问上下文失败: {e}")
    
    # 创建并启动子线程
    thread = threading.Thread(target=child_thread_task)
    thread.start()
    thread.join()
    
    if result['success']:
        print("✅ 子线程成功继承父线程上下文")
    else:
        print(f"❌ 子线程无法访问上下文: {result['error']}")
        raise AssertionError(result['error'])


def test_multiple_threads_with_shared_context():
    """测试多个线程共享同一个上下文。"""
    print("\n=== 测试 3: 多线程共享上下文 ===")
    
    # 在主线程设置上下文
    context = InMemoryContext(
        workspace_path='./workspace',
        session_id='shared-session',
        workspace_id='shared-workspace'
    )
    set_context(context)
    
    results = []
    
    def worker(worker_id):
        """工作线程 - 访问共享上下文"""
        try:
            ctx = require_context()
            results.append({
                'worker_id': worker_id,
                'workspace_id': ctx.workspace_id,
                'success': True
            })
            print(f"  Worker {worker_id}: 成功访问 {ctx.workspace_id}")
        except Exception as e:
            results.append({
                'worker_id': worker_id,
                'error': str(e),
                'success': False
            })
            print(f"  Worker {worker_id}: ❌ {e}")
    
    # 启动 5 个工作线程
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # 检查结果
    success_count = sum(1 for r in results if r['success'])
    if success_count == 5:
        print(f"✅ 所有 5 个线程都成功访问了共享上下文")
    else:
        print(f"❌ 只有 {success_count}/5 个线程成功访问上下文")
        raise AssertionError("并非所有线程都能访问上下文")


def test_independent_contexts():
    """测试每个线程可以有独立的上下文。"""
    print("\n=== 测试 4: 线程独立上下文 ===")
    
    results = []
    
    def worker(worker_id):
        """工作线程 - 设置独立上下文"""
        try:
            context = InMemoryContext(
                workspace_path=f'./workspace-{worker_id}',
                workspace_id=f'workspace-{worker_id}'
            )
            set_context(context)
            
            # 短暂延迟以模拟实际工作
            time.sleep(0.01)
            
            ctx = require_context()
            results.append({
                'worker_id': worker_id,
                'workspace_id': ctx.workspace_id,
                'success': ctx.workspace_id == f'workspace-{worker_id}'
            })
            print(f"  Worker {worker_id}: {ctx.workspace_id}")
        except Exception as e:
            results.append({
                'worker_id': worker_id,
                'error': str(e),
                'success': False
            })
    
    # 启动 3 个工作线程
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # 检查结果
    if all(r['success'] for r in results):
        print(f"✅ 所有线程都有独立的上下文")
    else:
        print(f"❌ 某些线程的上下文不独立")
        for r in results:
            if not r['success']:
                print(f"   Worker {r['worker_id']}: {r.get('error', 'context mismatch')}")
        raise AssertionError("线程上下文不独立")


def main():
    """运行所有测试。"""
    print("开始测试上下文在多线程环境下的行为...")
    print("=" * 60)
    
    try:
        test_basic_context()
        test_context_in_child_thread()
        test_multiple_threads_with_shared_context()
        test_independent_contexts()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("\n总结：")
        print("- ✅ 基本上下文功能正常")
        print("- ✅ 子线程可以继承父线程上下文")
        print("- ✅ 多线程可以共享上下文")
        print("- ✅ 每个线程可以有独立上下文")
        print("\n修复成功！contextvars 替代 threading.local 后，")
        print("LangChain agent 在不同线程执行工具时可以正常访问上下文了。")
        
    except AssertionError as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        raise


if __name__ == '__main__':
    main()
