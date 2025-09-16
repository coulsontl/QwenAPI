"""
工具注册和管理系统
"""
import json
import logging
import asyncio
import inspect
import uuid
from typing import Dict, Any, List, Callable, Optional, Union
from dataclasses import dataclass, field
from ..models.data_models import Tool, ToolType, FunctionDefinition, FunctionParameters

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    success: bool
    content: str
    error: Optional[str] = None


class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.tool_functions: Dict[str, Callable] = {}
        self.tool_schemas: Dict[str, Dict[str, Any]] = {}
    
    def register_tool(self, name: str, func: Callable, description: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        try:
            sig = inspect.signature(func)
            if parameters is None:
                parameters = self._generate_parameters_from_signature(sig)
            
            func_params = FunctionParameters(
                type="object",
                properties=parameters.get("properties", {}),
                required=parameters.get("required", [])
            )
            
            func_def = FunctionDefinition(
                name=name,
                description=description,
                parameters=func_params
            )
            
            tool = Tool(type=ToolType.FUNCTION, function=func_def)
            
            self.tools[name] = tool
            self.tool_functions[name] = func
            self.tool_schemas[name] = parameters
            
            logger.debug("注册工具成功，名称: %s", name)
            return True
            
        except Exception as e:
            logger.error(f"工具注册失败: {name}, 错误: {e}")
            return False
    
    def unregister_tool(self, name: str) -> bool:
        if name in self.tools:
            del self.tools[name]
            del self.tool_functions[name]
            del self.tool_schemas[name]
            logger.debug("已注销工具，名称: %s", name)
            return True
        return False
    
    def get_tool(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[Tool]:
        return list(self.tools.values())
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self.tools.values()]
    
    def has_tool(self, name: str) -> bool:
        return name in self.tools
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        if not self.has_tool(name):
            logger.warning("尝试执行不存在的工具: %s", name)
            return ToolResult(
                success=False,
                content="",
                error=f"工具不存在: {name}"
            )
        
        try:
            func = self.tool_functions[name]
            
            schema = self.tool_schemas[name]
            validation_result = self._validate_arguments(arguments, schema)
            if not validation_result.valid:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"参数验证失败: {validation_result.error}"
                )
            
            if asyncio.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)
            
            logger.debug("工具执行成功，名称: %s", name)
            if isinstance(result, dict):
                content = json.dumps(result, ensure_ascii=False)
            elif isinstance(result, (str, int, float, bool)):
                content = str(result)
            else:
                content = json.dumps({"result": str(result)}, ensure_ascii=False)
            
            return ToolResult(success=True, content=content)
            
        except Exception as e:
            logger.error(f"工具执行失败: {name}, 错误: {e}")
            return ToolResult(
                success=False,
                content="",
                error=f"工具执行错误: {str(e)}"
            )
    
    def _generate_parameters_from_signature(self, sig: inspect.Signature) -> Dict[str, Any]:
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
                
            param_type = param.annotation
            default = param.default

            type_str = "string"
            if param_type == int:
                type_str = "integer"
            elif param_type == float:
                type_str = "number"
            elif param_type == bool:
                type_str = "boolean"
            elif hasattr(param_type, '__origin__'):
                origin = getattr(param_type, '__origin__', None)
                if origin == list:
                    type_str = "array"
                elif origin == dict:
                    type_str = "object"

            param_property = {"type": type_str}
            
            if default != inspect.Parameter.empty:
                param_property["default"] = default
            else:
                required.append(param_name)
            
            properties[param_name] = param_property
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    def _validate_arguments(self, arguments: Dict[str, Any], schema: Dict[str, Any]) -> 'ValidationResult':
        try:
            required = schema.get("required", [])
            properties = schema.get("properties", {})
            
            for req_param in required:
                if req_param not in arguments:
                    return ValidationResult(
                        valid=False,
                        error=f"缺少必需参数: {req_param}"
                    )
            
            for param_name, param_value in arguments.items():
                if param_name in properties:
                    param_schema = properties[param_name]
                    expected_type = param_schema.get("type")
                    
                    if expected_type and not self._validate_type(param_value, expected_type):
                        return ValidationResult(
                            valid=False,
                            error=f"参数 {param_name} 类型错误，期望 {expected_type}"
                        )
            
            return ValidationResult(valid=True)
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"参数验证异常: {str(e)}"
            )
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True


@dataclass
class ValidationResult:
    valid: bool
    error: Optional[str] = None


tool_registry = ToolRegistry()


def tool(name: str = None, description: str = "", parameters: Dict[str, Any] = None):
    def decorator(func):
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        
        tool_registry.register_tool(
            name=tool_name,
            func=func,
            description=tool_desc,
            parameters=parameters
        )
        
        return func
    
    return decorator


def get_tool_registry() -> ToolRegistry:
    return tool_registry
