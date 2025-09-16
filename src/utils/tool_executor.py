import json
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from .tool_registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


class ToolCallExecutor:
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
    
    def parse_tool_calls(self, response_content: str) -> List[Dict[str, Any]]:
        tool_calls = []
        
        try:
            data = json.loads(response_content)
            
            if isinstance(data, dict):
                if "tool_calls" in data:
                    tool_calls = data["tool_calls"]
                elif "function" in data:
                    tool_calls = [data]
            elif isinstance(data, list):
                tool_calls = data
                
        except json.JSONDecodeError:
            tool_calls = self._parse_simple_function_calls(response_content)
        
        return tool_calls
    
    def _parse_simple_function_calls(self, content: str) -> List[Dict[str, Any]]:
        tool_calls = []
        
        import re
        
        pattern = r'(\w+)\s*\(\s*(.*?)\s*\)'
        matches = re.findall(pattern, content)
        
        for func_name, args_str in matches:
            arguments = {}
            if args_str:
                arg_pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|(\d+\.?\d*)|(\w+))'
                arg_matches = re.findall(arg_pattern, args_str)
                
                for arg_name, str_val, num_val, bool_val in arg_matches:
                    if str_val:
                        arguments[arg_name] = str_val
                    elif num_val:
                        if '.' in num_val:
                            arguments[arg_name] = float(num_val)
                        else:
                            arguments[arg_name] = int(num_val)
                    elif bool_val:
                        arguments[arg_name] = bool_val.lower() == 'true'
            
            tool_calls.append({
                "function": {
                    "name": func_name,
                    "arguments": json.dumps(arguments)
                }
            })
        
        return tool_calls
    
    async def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        
        for tool_call in tool_calls:
            try:
                tool_call_id = tool_call.get("id", str(uuid.uuid4()))
                function_info = tool_call.get("function", {})
                
                function_name = function_info.get("name")
                arguments_str = function_info.get("arguments", "{}")
                logger.debug("执行工具调用，tool_call_id: %s，函数: %s", tool_call_id, function_name)
                
                if not function_name:
                    results.append({
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "content": json.dumps({"error": "缺少函数名称"}, ensure_ascii=False)
                    })
                    continue
                
                try:
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError:
                    arguments = {}
                    logger.warning("工具调用参数非 JSON 格式，tool_call_id: %s", tool_call_id)
                
                result = await self.tool_registry.execute_tool(function_name, arguments)
                
                if result.success:
                    logger.debug("工具调用执行成功，tool_call_id: %s", tool_call_id)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "content": result.content
                    })
                else:
                    logger.warning("工具调用执行失败，tool_call_id: %s，错误: %s", tool_call_id, result.error)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "content": json.dumps({"error": result.error}, ensure_ascii=False)
                    })
                    
            except Exception as e:
                logger.error(f"工具调用执行失败: {e}")
                tool_call_id = tool_call.get("id", str(uuid.uuid4()))
                results.append({
                    "tool_call_id": tool_call_id,
                    "role": "tool",
                    "content": json.dumps({"error": f"工具调用异常: {str(e)}"}, ensure_ascii=False)
                })
        
        return results
    
    def format_tool_calls_for_response(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted_calls = []
        
        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", str(uuid.uuid4()))
            function_info = tool_call.get("function", {})
            
            formatted_call = {
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": function_info.get("name", ""),
                    "arguments": function_info.get("arguments", "{}")
                }
            }
            
            formatted_calls.append(formatted_call)
        
        return formatted_calls
    
    def should_continue_conversation(self, response_content: str) -> bool:
        tool_calls = self.parse_tool_calls(response_content)
        return len(tool_calls) > 0
    
    def create_tool_call_message(self, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": self.format_tool_calls_for_response(tool_calls)
        }
    
    def create_tool_result_messages(self, tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        messages = []
        
        for result in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": result.get("tool_call_id", ""),
                "content": result.get("content", "")
            })
        
        return messages
    
    async def handle_tool_call_conversation(self, 
                                          messages: List[Dict[str, Any]], 
                                          model_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        response_content = ""
        if "choices" in model_response:
            choice = model_response["choices"][0]
            if "message" in choice:
                message = choice["message"]
                response_content = message.get("content", "")
                
                if "tool_calls" in message:
                    tool_calls = message["tool_calls"]
                    results = await self.execute_tool_calls(tool_calls)
                    
                    messages.append(self.create_tool_call_message(tool_calls))
                    messages.extend(self.create_tool_result_messages(results))
                    
                    return messages
        
        if self.should_continue_conversation(response_content):
            tool_calls = self.parse_tool_calls(response_content)
            if tool_calls:
                results = await self.execute_tool_calls(tool_calls)
                
                messages.append(self.create_tool_call_message(tool_calls))
                messages.extend(self.create_tool_result_messages(results))
                
                return messages
        
        return messages
