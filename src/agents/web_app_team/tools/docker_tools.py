"""Docker 容器命令执行工具。

为 agent 提供在 dev container 中执行 shell 命令的能力。
通过 MCP 协议调用 mgx-api，而非直接使用 Docker SDK。
"""

from langchain.tools import tool

from . import mcp_docker_client


def _get_workspace_id() -> str:
    """获取 workspace ID。"""
    from agents.context import require_context

    context = require_context()
    return context.workspace_id


def _is_safe_command(command: str) -> tuple[bool, str]:
    """检查命令是否安全。

    Args:
        command: 要执行的命令

    Returns:
        (是否安全, 错误信息)
    """
    dangerous_patterns = [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "mkfs",
        "dd if=",
        "> /dev/",
        ":(){ :|:& };:",  # Fork bomb
        "curl | sh",
        "wget | sh",
        "curl | bash",
        "wget | bash",
    ]

    command_lower = command.lower().strip()

    for pattern in dangerous_patterns:
        if pattern in command_lower:
            return False, f"禁止执行危险命令：{pattern}"

    if command_lower.startswith("rm") and "-rf" in command_lower:
        if " /" in command_lower or command_lower.endswith("/"):
            return False, "禁止删除根目录或重要系统目录"

    return True, ""


@tool
async def exec_command(command: str, working_dir: str = "/workspace") -> str:
    """在 dev container 中执行 shell 命令。

    **禁止用于编辑文件**：不要用此工具执行 cat >、echo >、sed -i、vim 等文件编辑命令。
    文件编辑必须使用 write_file 工具。此工具仅用于：
    - 安装依赖（npm install、pip install 等）
    - 调试与运行（启动服务、查看日志、运行测试等）
    - 其他非编辑类 shell 操作

    Args:
        command: 要执行的 shell 命令
        working_dir: 工作目录，默认为 /workspace

    Returns:
        命令输出结果（包含 stdout 和 stderr）
    """
    is_safe, error_msg = _is_safe_command(command)
    if not is_safe:
        return f"错误：{error_msg}"
    workspace_id = _get_workspace_id()
    return await mcp_docker_client.exec_command(workspace_id, command, working_dir)


@tool
async def get_container_logs(tail: int = 100) -> str:
    """获取 dev container 的日志。

    Args:
        tail: 返回最后 N 行日志，默认 100 行

    Returns:
        容器日志
    """
    workspace_id = _get_workspace_id()
    return await mcp_docker_client.get_container_logs(workspace_id, tail)


@tool
async def install_package(package_name: str, package_manager: str = "npm") -> str:
    """在 dev container 中安装依赖包。

    Args:
        package_name: 包名称
        package_manager: 包管理器（npm, pip, yarn, pnpm）

    Returns:
        安装结果
    """
    install_commands = {
        "npm": f"npm install {package_name}",
        "yarn": f"yarn add {package_name}",
        "pnpm": f"pnpm add {package_name}",
        "pip": f"pip install {package_name}",
    }
    if package_manager not in install_commands:
        return f"错误：不支持的包管理器 {package_manager}，支持：{', '.join(install_commands.keys())}"
    command = install_commands[package_manager]
    result = await exec_command.ainvoke({"command": command, "working_dir": "/workspace"})
    return f"安装 {package_name} ({package_manager}):\n{result}"


@tool
async def run_tests(test_command: str | None = None) -> str:
    """在 dev container 中运行测试。

    Args:
        test_command: 测试命令，如果不提供则自动检测（npm test, pytest 等）

    Returns:
        测试结果
    """
    if test_command:
        command = test_command
    else:
        check_npm = 'if [ -f package.json ]; then npm test; elif [ -f pytest.ini ] || [ -f setup.py ]; then pytest; else echo "未找到测试配置"; fi'
        command = check_npm
    result = await exec_command.ainvoke({"command": command, "working_dir": "/workspace"})
    return f"测试结果:\n{result}"


@tool
async def get_container_status() -> str:
    """获取 dev container 的状态信息。

    Returns:
        容器状态信息（状态、端口映射等）
    """
    workspace_id = _get_workspace_id()
    return await mcp_docker_client.get_container_status(workspace_id)


# ============================================================================
# Dev Server 管理工具
# ============================================================================


@tool
async def start_dev_server(
    command: str = "npm run dev",
    working_dir: str = "/workspace",
    port: int = 3000,
) -> str:
    """启动开发服务器（后台运行）。

    在 dev container 中启动开发服务器，并将其在后台运行。
    日志输出会重定向到 /workspace/.dev-server.log 文件。
    进程 PID 会保存到 /workspace/.dev-server.pid 文件。

    Args:
        command: 启动命令，如 'npm run dev', 'pnpm dev', 'yarn dev' 等
        working_dir: 工作目录，默认为 /workspace
        port: 开发服务器端口，默认 3000

    Returns:
        启动结果，包含 PID 和状态信息

    Examples:
        start_dev_server("npm run dev")
        start_dev_server("pnpm dev", port=3000)
        start_dev_server("yarn dev --port 3001", port=3001)
    """
    workspace_id = _get_workspace_id()
    return await mcp_docker_client.start_dev_server(workspace_id, command, working_dir, port)


@tool
async def get_dev_server_status() -> str:
    """获取开发服务器的运行状态。

    检查开发服务器是否正在运行，并返回相关信息。

    Returns:
        开发服务器状态信息（运行中/已停止、PID、端口等）
    """
    workspace_id = _get_workspace_id()
    return await mcp_docker_client.get_dev_server_status(workspace_id)


@tool
async def get_dev_server_logs(tail: int = 50, follow: bool = False) -> str:
    """获取开发服务器的日志输出。

    读取开发服务器的日志文件 (/workspace/.dev-server.log)。

    Args:
        tail: 返回最后 N 行日志，默认 50 行。设置为 0 获取全部日志
        follow: 是否持续跟踪日志（暂不支持，保留参数用于未来扩展）

    Returns:
        开发服务器的日志内容
    """
    workspace_id = _get_workspace_id()
    result = await mcp_docker_client.get_dev_server_logs(workspace_id, tail)
    header = f"=== Dev Server 日志（最后 {tail} 行）===\n\n"
    return header + result


@tool
async def stop_dev_server() -> str:
    """停止开发服务器。

    停止正在运行的开发服务器进程。

    Returns:
        停止结果
    """
    workspace_id = _get_workspace_id()
    return await mcp_docker_client.stop_dev_server(workspace_id)
