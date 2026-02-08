"""Docker container management service."""
import asyncio
import time
from pathlib import Path

import aiofiles
import docker
from docker.models.containers import Container

from shared.config import settings
from shared.config.docker_images import get_framework_docker_image, get_framework_docker_port
from mgx_api.dao import SessionDAO
from .apisix_service import ApisixService

from .dev_server_lock import dev_server_lock


class DockerService:
    """Docker container management business logic."""

    def __init__(self):
        """Initialize DockerService."""
        self.client = docker.from_env()

    async def _get_container_info(self, container: Container) -> dict:
        """Extract container info."""
        await asyncio.to_thread(container.reload)

        ports_info = {}
        if container.ports:
            for container_port, host_bindings in container.ports.items():
                if host_bindings:
                    ports_info[container_port] = host_bindings[0]["HostPort"]

        return {
            "container_id": container.id,
            "container_name": container.name,
            "status": container.status,
            "ports": ports_info,
        }

    async def _ensure_dev_container(
        self,
        workspace_id: str,
        framework: str,
    ) -> None:
        """
        Ensure dev container exists and is running. Dev server is accessed directly via host port.
        """
        container_name = f"mgx-dev-{workspace_id}"

        # Check if container already exists
        try:
            existing = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            if existing.status != "running":
                await asyncio.to_thread(existing.start)
            return
        except docker.errors.NotFound:
            pass

        image = get_framework_docker_image(framework)
        ports = {f"{get_framework_docker_port(framework)}/tcp": None}
        # Docker bind mount 需要宿主机路径（mgx-api 在容器内，Docker daemon 在 host 上执行）
        workspace_path = str((Path(settings.host_workspaces_root) / workspace_id).resolve())
        volumes = {workspace_path: {"bind": settings.agent_workspace_root_in_container, "mode": "rw"}}

        await asyncio.to_thread(
            self.client.containers.run,
            image=image,
            command='tail -f /dev/null',
            name=container_name,
            volumes=volumes,
            ports=ports,
            detach=True,
            remove=False,
            network_mode="bridge",
        )

    async def _save_dev_server_params(
        self,
        workspace_id: str,
        command: str,
        working_dir: str,
        port: int,
        framework: str,
    ) -> None:
        """Persist dev server params to session (workspace_id = session_id)."""
        try:
            session_dao = SessionDAO()
            await session_dao.update(
                workspace_id,
                {
                    "dev_server_params": {
                        "command": command,
                        "working_dir": working_dir,
                        "port": port,
                        "framework": framework,
                    },
                    "updated_at": time.time(),
                },
            )
        except Exception as e:
            print(f"⚠️ Failed to save dev_server_params to session: {e}")

    async def stop_agent_container(self, session_id: str) -> bool:
        """
        Stop agent container for a session.

        Args:
            session_id: Session ID (container name is mgx-agent-{session_id})

        Returns:
            True if container was found and stopped, False if not found
        """
        container_name = f"mgx-agent-{session_id}"
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            await asyncio.to_thread(container.stop, timeout=10)
            return True
        except docker.errors.NotFound:
            return False

    async def wait_agent_container_exit(
        self, session_id: str, timeout_seconds: float = 60
    ) -> bool:
        """
        Wait for agent container to exit after stop signal.

        Polls container status until it exits (or is removed with remove=True).
        Returns True if container exited within timeout, False on timeout.

        Args:
            session_id: Session ID
            timeout_seconds: Max seconds to wait

        Returns:
            True if container exited, False if timeout
        """
        import time

        container_name = f"mgx-agent-{session_id}"
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
        except docker.errors.NotFound:
            return True  # already gone

        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout_seconds:
                return False

            try:
                await asyncio.to_thread(container.reload)
                if container.status in ("exited", "dead"):
                    return True
            except docker.errors.NotFound:
                return True  # container exited and was removed (remove=True)

            await asyncio.sleep(0.5)
    
    async def get_dev_container_status(self, workspace_id: str) -> dict | None:
        """Get dev container status."""
        container_name = f"mgx-dev-{workspace_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            return await self._get_container_info(container)
        except docker.errors.NotFound:
            return None
    
    async def build_prod_image(
        self,
        workspace_id: str,
        framework: str,
    ) -> dict:
        """
        Build production image for an app.
        
        Args:
            workspace_id: Workspace ID
            framework: Framework type
            
        Returns:
            Build result with image_id
        """
        # 写文件：容器内路径；build context：宿主机路径（Docker daemon 在 host 上读取）
        workspace_path_container = str((Path(settings.workspaces_root) / workspace_id).resolve())
        workspace_path_host = str((Path(settings.host_workspaces_root) / workspace_id).resolve())
        image_tag = f"mgx-prod:{workspace_id}"

        # Generate Dockerfile based on framework template
        dockerfile_content = self._generate_dockerfile(framework)

        # Write Dockerfile to workspace（容器内路径，通过 volume 挂载）
        dockerfile_path = f"{workspace_path_container}/Dockerfile"
        async with aiofiles.open(dockerfile_path, "w") as f:
            await f.write(dockerfile_content)

        # Build image（Docker daemon 需要宿主机路径）
        try:
            def _build():
                result = self.client.images.build(
                    path=workspace_path_host,
                    tag=image_tag,
                    rm=True,
                    forcerm=True,
                )
                image, build_logs = result
                return image, [line for line in build_logs]

            image, logs = await asyncio.to_thread(_build)
            
            return {
                "image_id": image.id,
                "image_tag": image_tag,
                "status": "success",
                "logs": str(logs)[:500],
            }
        except docker.errors.BuildError as e:
            return {
                "status": "failed",
                "error": str(e),
            }
    
    def _generate_dockerfile(self, framework: str) -> str:
        """Generate Dockerfile content based on framework."""
        if framework == "nextjs":
            return """FROM node:20-alpine
WORKDIR /app
COPY . .
RUN npm install
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
"""
        elif framework == "fastapi-vite":
            return """FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN cd frontend && npm install && npm run build
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
        else:
            return """FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt || true
EXPOSE 8000
CMD ["python", "-m", "http.server", "8000"]
"""
    
    async def start_prod_container(
        self,
        workspace_id: str,
        image_tag: str,
    ) -> dict:
        """
        Start production container.
        
        Args:
            workspace_id: Workspace ID
            image_tag: Docker image tag
            
        Returns:
            Container info
        """
        container_name = f"mgx-prod-{workspace_id}"

        # Check if container already exists
        try:
            existing = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            await asyncio.to_thread(existing.stop)
            await asyncio.to_thread(existing.remove)
        except docker.errors.NotFound:
            pass

        # Start new container
        container = await asyncio.to_thread(
            self.client.containers.run,
            image=image_tag,
            name=container_name,
            ports={"8000/tcp": None, "3000/tcp": None},
            detach=True,
            remove=False,
            network_mode="bridge",
        )

        container_info = await self._get_container_info(container)
        
        # Create Apisix route for production container
        if container_info.get("ports"):
            try:
                # Get the first port mapping (host port)
                port_mappings = container_info["ports"]
                if port_mappings:
                    host_port = int(list(port_mappings.values())[0])
                    # Prod container uses network_mode=bridge; use host.docker.internal
                    apisix_service = ApisixService()
                    await apisix_service.create_or_update_route(
                        workspace_id=workspace_id,
                        target_type="prod",
                        upstream_host="host.docker.internal",
                        upstream_port=host_port,
                    )
                    print(f"✅ Created Apisix route for {workspace_id} (prod)")
            except Exception as e:
                print(f"⚠️ Failed to create Apisix route: {e}")
                # Don't fail the entire operation if route creation fails
        
        return container_info
    
    async def stop_prod_container(self, workspace_id: str) -> None:
        """
        Stop production container and remove its Apisix route.

        Args:
            workspace_id: Workspace ID
        """
        container_name = f"mgx-prod-{workspace_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            await asyncio.to_thread(container.stop)

            try:
                apisix_service = ApisixService()
                await apisix_service.delete_route(workspace_id, "prod")
                print(f"✅ Deleted Apisix route for {workspace_id} (prod)")
            except Exception as e:
                print(f"⚠️ Failed to delete Apisix route: {e}")
        except docker.errors.NotFound:
            pass
    
    async def get_prod_container_status(self, workspace_id: str) -> dict | None:
        """Get production container status."""
        container_name = f"mgx-prod-{workspace_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            return await self._get_container_info(container)
        except docker.errors.NotFound:
            return None
    
    async def exec_command(
        self,
        workspace_id: str,
        command: str,
        working_dir: str = "/workspace",
    ) -> str:
        """
        Execute a shell command in the dev container.

        Args:
            workspace_id: Workspace ID
            command: Shell command to execute
            working_dir: Working directory, default /workspace

        Returns:
            Combined stdout/stderr output as string
        """
        container_name = f"mgx-dev-{workspace_id}"
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            await asyncio.to_thread(container.reload)
            if container.status != "running":
                return f"错误：dev container 状态为 {container.status}，需要处于 running 状态"
            exit_code, output = await asyncio.to_thread(
                container.exec_run,
                cmd=["sh", "-c", command],
                workdir=working_dir,
                demux=True,
            )
            stdout, stderr = output
            result_parts = []
            if stdout:
                result_parts.append(f"输出:\n{stdout.decode('utf-8', errors='replace')}")
            if stderr:
                result_parts.append(f"错误输出:\n{stderr.decode('utf-8', errors='replace')}")
            if exit_code != 0:
                result_parts.append(f"\n退出码: {exit_code}")
            if not result_parts:
                return "命令执行成功（无输出）"
            return "\n".join(result_parts)
        except docker.errors.NotFound:
            return f"错误：dev container {container_name} 不存在或未启动"
        except Exception as e:
            return f"错误：执行命令失败 - {str(e)}"

    async def get_container_status_str(self, workspace_id: str) -> str:
        """
        Get dev container status as human-readable string.

        Args:
            workspace_id: Workspace ID

        Returns:
            Status string (name, status, image, ports)
        """
        info = await self.get_dev_container_status(workspace_id)
        if not info:
            return f"dev container mgx-dev-{workspace_id} 不存在"
        parts = [
            f"容器名称: {info['container_name']}",
            f"状态: {info['status']}",
        ]
        if info.get("ports"):
            ports = [f"{k} -> {v}" for k, v in info["ports"].items()]
            parts.append(f"端口映射: {', '.join(ports)}")
        return "\n".join(parts)

    async def start_dev_server(
        self,
        workspace_id: str,
        command: str = "npm run dev",
        working_dir: str = "/workspace",
        port: int = 3000,
        framework: str = "nextjs",
    ) -> str:
        """
        Start dev server in the dev container (background).
        Creates dev container and Apisix route if they do not exist.

        Args:
            workspace_id: Workspace ID
            command: Start command (e.g. npm run dev)
            working_dir: Working directory
            port: Dev server port
            framework: Framework (nextjs, fastapi-vite) for container creation

        Returns:
            Start result string
        """
        async with dev_server_lock(workspace_id):
            return await self._start_dev_server_impl(
                workspace_id, command, working_dir, port, framework
            )

    async def _start_dev_server_impl(
        self,
        workspace_id: str,
        command: str = "npm run dev",
        working_dir: str = "/workspace",
        port: int = 3000,
        framework: str = "nextjs",
    ) -> str:
        """Internal: start dev server (caller must hold workspace lock)."""
        container_name = f"mgx-dev-{workspace_id}"
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            await asyncio.to_thread(container.reload)
            if container.status != "running":
                return f"错误：dev container 状态为 {container.status}，需要处于 running 状态"
        except docker.errors.NotFound:
            await self._ensure_dev_container(workspace_id, framework)
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            await asyncio.to_thread(container.reload)

        try:

            check_pid_cmd = "[ -f /workspace/.dev-server.pid ] && kill -0 $(cat /workspace/.dev-server.pid) 2>/dev/null && echo 'running' || echo 'stopped'"
            exit_code, output = await asyncio.to_thread(
                container.exec_run,
                cmd=["sh", "-c", check_pid_cmd],
                workdir=working_dir,
            )
            if output and b"running" in output:
                exit_code, cmd_output = await asyncio.to_thread(
                    container.exec_run,
                    cmd=["sh", "-c", "cat /workspace/.dev-server.cmd 2>/dev/null || echo 'unknown'"],
                    workdir=working_dir,
                )
                current_cmd = cmd_output.decode("utf-8", errors="replace").strip()
                await self._save_dev_server_params(workspace_id, command, working_dir, port, framework)
                return f"提示：开发服务器已在运行中\n当前命令: {current_cmd}\n如需重启，请先使用 stop_dev_server 停止"

            bg_command = f"""
cd {working_dir} && \
echo '{command}' > /workspace/.dev-server.cmd && \
nohup {command} > /workspace/.dev-server.log 2>&1 & \
echo $! > /workspace/.dev-server.pid && \
echo "Dev server started with PID: $(cat /workspace/.dev-server.pid)"
"""
            await asyncio.to_thread(
                container.exec_run,
                cmd=["sh", "-c", bg_command],
                workdir=working_dir,
            )
            await asyncio.sleep(2)

            check_cmd = f"""
if [ -f /workspace/.dev-server.pid ]; then
    PID=$(cat /workspace/.dev-server.pid)
    if kill -0 $PID 2>/dev/null; then
        echo "✓ Dev server 启动成功"
        echo "PID: $PID"
        echo "命令: $(cat /workspace/.dev-server.cmd)"
        echo "端口: {port}"
        echo "日志文件: /workspace/.dev-server.log"
        echo ""
        echo "最近日志："
        tail -n 10 /workspace/.dev-server.log 2>/dev/null || echo "暂无日志"
    else
        echo "✗ Dev server 启动失败（进程已退出）"
        echo "错误日志："
        tail -n 20 /workspace/.dev-server.log 2>/dev/null || echo "无日志文件"
    fi
else
    echo "✗ Dev server 启动失败（未创建 PID 文件）"
fi
""".format(port=port)
            exit_code, check_output = await asyncio.to_thread(
                container.exec_run,
                cmd=["sh", "-c", check_cmd],
                workdir=working_dir,
            )
            result = check_output.decode("utf-8", errors="replace") if check_output else "无输出"
            if result and "✓ Dev server 启动成功" in result:
                await self._save_dev_server_params(workspace_id, command, working_dir, port, framework)
            return result
        except docker.errors.NotFound:
            return f"错误：dev container {container_name} 不存在或未启动"
        except Exception as e:
            return f"错误：启动 dev server 失败 - {str(e)}"

    async def stop_dev_server(self, workspace_id: str) -> str:
        """
        Stop dev server in the dev container.

        Args:
            workspace_id: Workspace ID

        Returns:
            Stop result string
        """
        container_name = f"mgx-dev-{workspace_id}"
        stop_cmd = """
if [ ! -f /workspace/.dev-server.pid ]; then
    echo "Dev server 未启动（无 PID 文件）"
    exit 0
fi

PID=$(cat /workspace/.dev-server.pid)
CMD=$(cat /workspace/.dev-server.cmd 2>/dev/null || echo "unknown")

if kill -0 $PID 2>/dev/null; then
    echo "正在停止 dev server..."
    echo "PID: $PID"
    echo "命令: $CMD"
    kill $PID 2>/dev/null
    for i in 1 2 3 4 5; do
        if ! kill -0 $PID 2>/dev/null; then
            echo "✓ Dev server 已停止"
            rm -f /workspace/.dev-server.pid
            exit 0
        fi
        sleep 1
    done
    if kill -0 $PID 2>/dev/null; then
        echo "优雅停止超时，强制停止..."
        kill -9 $PID 2>/dev/null
        sleep 1
        if kill -0 $PID 2>/dev/null; then
            echo "✗ 无法停止进程"
            exit 1
        else
            echo "✓ Dev server 已强制停止"
            rm -f /workspace/.dev-server.pid
        fi
    fi
else
    echo "Dev server 已停止（进程不存在）"
    rm -f /workspace/.dev-server.pid
fi
"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            await asyncio.to_thread(container.reload)
            if container.status != "running":
                return f"错误：dev container 状态为 {container.status}，需要处于 running 状态"
            exit_code, output = await asyncio.to_thread(
                container.exec_run,
                cmd=["sh", "-c", stop_cmd],
                workdir="/workspace",
            )
            return output.decode("utf-8", errors="replace") if output else "无输出"
        except docker.errors.NotFound:
            return f"错误：dev container {container_name} 不存在或未启动"
        except Exception as e:
            return f"错误：停止 dev server 失败 - {str(e)}"

    async def get_container_logs(
        self,
        workspace_id: str,
        target: str = "dev",
        tail: int = 100,
    ) -> str:
        """
        Get container logs.
        
        Args:
            workspace_id: Workspace ID
            target: "dev" or "prod"
            tail: Number of log lines to return
            
        Returns:
            Log content as string
        """
        container_name = f"mgx-{target}-{workspace_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )
            logs = await asyncio.to_thread(
                container.logs, tail=tail, timestamps=True
            )
            return logs.decode("utf-8", errors="replace")
        except docker.errors.NotFound:
            return f"Container {container_name} not found"
        except Exception as e:
            return f"Error fetching logs: {str(e)}"
    
    async def get_dev_server_status(self, workspace_id: str) -> str:
        """
        Get development server status (inside the container).
        
        Checks if a dev server is running inside the dev container by
        examining the .dev-server.pid file.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Dev server status information as string
        """
        container_name = f"mgx-dev-{workspace_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )

            # Check if container is running
            await asyncio.to_thread(container.reload)
            if container.status != "running":
                return f"Dev container is not running (status: {container.status})"

            # Execute status check command
            status_cmd = """
if [ ! -f /workspace/.dev-server.pid ]; then
    echo "Status: Not started"
    echo "Use agent to start dev server with start_dev_server tool"
    exit 0
fi

PID=$(cat /workspace/.dev-server.pid)
CMD=$(cat /workspace/.dev-server.cmd 2>/dev/null || echo "unknown")

if kill -0 $PID 2>/dev/null; then
    echo "Status: Running"
    echo "PID: $PID"
    echo "Command: $CMD"
else
    echo "Status: Stopped (process not found)"
    echo "Last PID: $PID"
    echo "Last Command: $CMD"
fi
"""

            exit_code, output = await asyncio.to_thread(
                container.exec_run,
                cmd=["sh", "-c", status_cmd],
                workdir="/workspace",
            )

            return output.decode("utf-8", errors="replace") if output else "No output"

        except docker.errors.NotFound:
            return f"Container {container_name} not found"
        except Exception as e:
            return f"Error checking dev server status: {str(e)}"

    async def get_dev_server_logs(self, workspace_id: str, tail: int = 100) -> str:
        """
        Get development server logs (from inside the container).
        
        Reads the .dev-server.log file inside the dev container.
        
        Args:
            workspace_id: Workspace ID
            tail: Number of log lines to return
            
        Returns:
            Dev server log content as string
        """
        container_name = f"mgx-dev-{workspace_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get, container_name
            )

            # Check if container is running
            await asyncio.to_thread(container.reload)
            if container.status != "running":
                return f"Dev container is not running (status: {container.status})"

            # Read log file
            if tail == 0:
                log_cmd = "cat /workspace/.dev-server.log 2>/dev/null || echo 'Log file does not exist'"
            else:
                log_cmd = f"tail -n {tail} /workspace/.dev-server.log 2>/dev/null || echo 'Log file does not exist'"

            exit_code, output = await asyncio.to_thread(
                container.exec_run,
                cmd=["sh", "-c", log_cmd],
                workdir="/workspace",
            )

            return output.decode("utf-8", errors="replace") if output else "No output"

        except docker.errors.NotFound:
            return f"Container {container_name} not found"
        except Exception as e:
            return f"Error reading dev server logs: {str(e)}"
