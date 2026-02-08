"""Filesystem utility functions."""
from pathlib import Path


def safe_join(root: Path, relative_path: str) -> Path:
    """
    Safely join a relative path to a root directory.
    
    Ensures the result is within the root directory (prevents directory traversal).
    
    Args:
        root: Root directory path
        relative_path: Relative path to join
        
    Returns:
        Resolved absolute path
        
    Raises:
        ValueError: If the result would be outside root
    """
    # Normalize and resolve paths
    root_resolved = root.resolve()
    candidate = (root / relative_path).resolve()
    
    # Check if candidate is within root
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        raise ValueError(f"Path {relative_path} would escape root directory")
    
    return candidate
