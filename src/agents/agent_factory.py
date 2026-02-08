"""Agent factory for creating langchain agents."""
from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph

from shared.config import settings


def create_code_generation_agent(
    framework: str = "fastapi-vite",
    callbacks: list[Any] | None = None
):
    """Create a code generation agent.
    
    Args:
        framework: Target framework (nextjs, fastapi-vite)
        callbacks: Optional callback handlers (e.g., langfuse)
    
    Returns:
        Compiled agent graph
    """
    # Define tools
    @tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file in the workspace.
        
        Args:
            path: File path relative to workspace root
            content: File content to write
        
        Returns:
            Success message
        """
        # TODO: Implement actual file writing
        return f"File {path} written successfully (stub implementation)"
    
    @tool
    def read_file(path: str) -> str:
        """Read content from a file in the workspace.
        
        Args:
            path: File path relative to workspace root
        
        Returns:
            File content
        """
        # TODO: Implement actual file reading
        return f"Content of {path} (stub implementation)"
    
    @tool
    def list_files(directory: str = ".") -> list[str]:
        """List files in a directory.
        
        Args:
            directory: Directory path relative to workspace root
        
        Returns:
            List of file paths
        """
        # TODO: Implement actual directory listing
        return ["file1.py", "file2.py", "stub implementation"]
    
    tools = [write_file, read_file, list_files]
    
    # Create LLM
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        streaming=True,  # Enable streaming
        callbacks=callbacks
    )
    
    # Create system prompt
    system_prompt = f"""You are an expert full-stack developer assistant.
You are helping to generate code for a {framework} application.

Your responsibilities:
1. Understand the user's requirements
2. Plan the code structure
3. Write clean, well-documented code
4. Follow best practices for {framework}

Use the provided tools to interact with the workspace files.
"""
    
    # Create agent using new API
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )
    
    return agent


# Placeholder for other agent types
def create_planning_agent(callbacks: list[Any] | None = None):
    """Create a planning agent (placeholder).
    
    Args:
        callbacks: Optional callback handlers
    
    Returns:
        Compiled agent graph
    """
    # TODO: Implement planning agent
    return create_code_generation_agent("fastapi-vite", callbacks)


def create_team_agent(
    framework: str,
    callbacks: list[Any] | None = None,
) -> CompiledStateGraph:
    """Create a multi-agent team for web app development.
    
    Args:
        framework: Target framework (nextjs, fastapi-vite)
        callbacks: Optional callback handlers (e.g., langfuse)
    
    Returns:
        CompiledGraph: Configured team workflow graph
    
    Note:
        需要通过 context.set_context() 设置 AgentContext 后才能使用
    """
    from agents.web_app_team import create_web_app_team
    
    return create_web_app_team(
        framework=framework,
        callbacks=callbacks,
    )
