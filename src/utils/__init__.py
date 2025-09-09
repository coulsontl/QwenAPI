"""
Utilities module for Qwen Code API Server
"""
from .helpers import generate_state_id, get_token_id, generate_pkce_pair, verify_password
from .tool_registry import get_tool_registry

def initialize_tools():
    """初始化工具系统"""
    registry = get_tool_registry()
    
    # 工具系统已初始化，用户可以通过装饰器注册自己的工具
    # 例如：
    # from src.utils.tool_registry import tool
    # @tool(name="my_tool", description="我的工具")
    # async def my_tool(param: str) -> dict:
    #     return {"result": param}
    
    return registry