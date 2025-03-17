import os
import functools
import inspect
from mcp.server.fastmcp import FastMCP
from typing import Dict, List, Any, Optional, Callable
import time

mcp = FastMCP("Codebase Knowledge Server")

# Cache configuration
CACHE_TIMEOUT = 300  # Cache timeout in seconds
_cache = {}  # Global cache dictionary

def cache_with_timeout(timeout: int) -> Callable:
    """
    Decorator that caches function results with a timeout.
    
    Args:
        timeout: Cache timeout in seconds
        
    Returns:
        Decorated function with caching
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key from function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            current_time = time.time()
            
            # Check if result is in cache and not expired
            if key in _cache and current_time - _cache[key]['timestamp'] < timeout:
                return _cache[key]['result']
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            _cache[key] = {'result': result, 'timestamp': current_time}
            return result
        return wrapper
    return decorator

@cache_with_timeout(CACHE_TIMEOUT)
def analyze_codebase(path: str = "./") -> str:
    """
    Analyze the codebase by counting files and lines.
    
    Args:
        path: Root directory to analyze
        
    Returns:
        Summary of the codebase analysis
    """
    summary_lines = []
    total_files = 0
    total_lines = 0
    
    # Skip directories that should be ignored
    skip_dirs = {'.venv', '.git', '__pycache__', 'node_modules'}
    
    for root, dirs, files in os.walk(path):
        # Skip unwanted directories (modify dirs in-place to avoid traversing them)
        dirs[:] = [d for d in dirs if d not in skip_dirs]
            
        py_files = [f for f in files if f.endswith('.py')]
        total_files += len(py_files)
        
        for file in py_files:
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    num_lines = len(lines)
                    total_lines += num_lines
                    summary_lines.append(f"{filepath} - {num_lines} lines")
            except Exception as e:
                summary_lines.append(f"{filepath} - Error: {e}")

    # Use join operations for better string performance
    summary_parts = [
        "Codebase Summary:",
        f"Total files: {total_files}",
        f"Total lines: {total_lines}",
        "",
        "File Details:"
    ]
    
    return "\n".join(summary_parts + summary_lines)

@cache_with_timeout(CACHE_TIMEOUT)
def get_main_py_content() -> str:
    """Get the content of the main.py file"""
    try:
        with open("main.py", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading main.py: {str(e)}"

@cache_with_timeout(CACHE_TIMEOUT)
def analyze_main_py() -> Dict[str, Any]:
    """
    Analyze the content and structure of main.py
    
    Returns:
        Dictionary containing analysis results
    """
    content = get_main_py_content()
    lines = content.split("\n")
    
    # Basic analysis
    analysis = {
        "filename": "main.py",
        "line_count": len(lines),
        "functions": [],
        "imports": [],
        "resources": []
    }
    
    # Extract imports with list comprehension for better performance
    analysis["imports"] = [
        line.strip() for line in lines 
        if line.startswith("import ") or line.startswith("from ")
    ]
    
    # Current file functions
    current_globals = globals().copy()
    for name, obj in current_globals.items():
        if inspect.isfunction(obj) and obj.__module__ == "__main__":
            # Get function details
            signature = str(inspect.signature(obj))
            is_resource = hasattr(obj, "__mcp_resource__")
            resource_path = getattr(obj, "__mcp_resource__", None)
            
            func_info = {
                "name": name,
                "signature": signature,
                "is_resource": is_resource,
                "resource_path": resource_path
            }
            
            analysis["functions"].append(func_info)
            if is_resource:
                analysis["resources"].append(f"{resource_path} -> {name}{signature}")
    
    return analysis

@mcp.resource("codebase://summary")
def codebase_summary() -> str:
    return analyze_codebase()

@mcp.resource("code://main.py/{detail}")
def main_py_info(detail: str = "content") -> str:
    """
    Get information about main.py
    
    Args:
        detail: Type of information requested (content, analysis, functions, imports, resources)
        
    Returns:
        str: The requested information about main.py
    """
    # Using a dictionary dispatch instead of if-elif chains for better performance
    analysis = analyze_main_py()
    
    detail_handlers = {
        "content": lambda: get_main_py_content(),
        "analysis": lambda: str(analysis),
        "functions": lambda: str([f["name"] + f["signature"] for f in analysis["functions"]]),
        "imports": lambda: str(analysis["imports"]),
        "resources": lambda: str(analysis["resources"])
    }
    
    handler = detail_handlers.get(detail)
    if handler:
        return handler()
    
    return f"Unknown detail type: {detail}. Available options: {', '.join(detail_handlers.keys())}"

@mcp.resource("prompt://question/{prompt}")
def handle_prompt(prompt: str) -> str:
    """
    Handle arbitrary prompts or questions.
    
    Args:
        prompt: The question or prompt from the user
        
    Returns:
        str: The response to the prompt
    """
    prompt_lower = prompt.lower()
    analysis = None
    
    # Questions about main.py - only analyze once if needed
    if "main.py" in prompt_lower:
        # Use a dictionary dispatch for better performance and maintainability
        if any(term in prompt_lower for term in ["function", "def", "import", "resource", 
                                                "endpoint", "analyze", "structure"]):
            analysis = analyze_main_py()
            
        if "content" in prompt_lower or "show" in prompt_lower:
            return get_main_py_content()
        elif "function" in prompt_lower or "def" in prompt_lower:
            return f"Functions in main.py:\n" + "\n".join(
                [f"{f['name']}{f['signature']}" for f in analysis["functions"]]
            )
        elif "import" in prompt_lower:
            return f"Imports in main.py:\n" + "\n".join(analysis["imports"])
        elif "resource" in prompt_lower or "endpoint" in prompt_lower:
            return f"Resources in main.py:\n" + "\n".join(analysis["resources"])
        elif "analyze" in prompt_lower or "structure" in prompt_lower:
            return f"Analysis of main.py:\n{analysis}"
        else:
            return f"I can answer questions about main.py. Try asking about its content, functions, imports, resources, or structure."
    
    # Other types of queries
    elif "codebase" in prompt_lower:
        return analyze_codebase()
    elif "file" in prompt_lower:
        return "I can help with file operations. Please specify which file you're interested in."
    else:
        return f"You asked: {prompt}\nI'm your MCP server. I can analyze your codebase and answer questions about it, especially about main.py."

def clear_cache() -> None:
    """Clear the internal function cache"""
    global _cache
    _cache = {}

@mcp.resource("system://cache/clear")
def clear_cache_endpoint() -> str:
    """Endpoint to clear the cache"""
    clear_cache()
    return "Cache cleared successfully"

if __name__ == "__main__":
    mcp.run()
