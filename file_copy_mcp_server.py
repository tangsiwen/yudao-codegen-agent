import os
import json
import shutil
import sys


def copy_directory(source_dir, target_dir, overwrite=False):
    """复制目录及其所有内容
    
    Args:
        source_dir: 源目录绝对路径
        target_dir: 目标目录绝对路径
        overwrite: 是否覆盖已存在的文件
    
    Returns:
        dict: 复制结果
    """
    try:
        # 检查源目录是否存在
        if not os.path.exists(source_dir):
            return {
                "success": False,
                "message": f"源目录不存在: {source_dir}"
            }
        
        # 确保目标目录存在
        os.makedirs(target_dir, exist_ok=True)
        
        # 遍历源目录中的所有文件和子目录
        for root, dirs, files in os.walk(source_dir):
            # 计算相对路径
            relative_path = os.path.relpath(root, source_dir)
            if relative_path == '.':
                relative_path = ''
            
            # 构建目标子目录路径
            target_subdir = os.path.join(target_dir, relative_path)
            
            # 创建目标子目录
            os.makedirs(target_subdir, exist_ok=True)
            
            # 复制文件
            for file in files:
                source_file = os.path.join(root, file)
                target_file = os.path.join(target_subdir, file)
                
                # 检查目标文件是否存在
                if os.path.exists(target_file):
                    if overwrite:
                        # 覆盖已存在的文件
                        shutil.copy2(source_file, target_file)
                    else:
                        # 跳过已存在的文件
                        continue
                else:
                    # 复制新文件
                    shutil.copy2(source_file, target_file)
        
        return {
            "success": True,
            "message": f"成功将 {source_dir} 复制到 {target_dir}",
            "source": source_dir,
            "target": target_dir
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"复制失败: {str(e)}"
        }


# MCP 协议处理
def send_message(message):
    """发送 MCP 消息到 stdout"""
    json_str = json.dumps(message)
    print(json_str, flush=True)


def handle_request(request):
    """处理 MCP 请求"""
    method = request.get('method')
    request_id = request.get('id')

    if method == 'initialize':
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "file-copy-server",
                    "version": "1.0.0"
                }
            }
        }
    elif method == 'tools/list':
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "copy_directory",
                        "description": "复制目录及其所有内容",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "sourceDir": {
                                    "type": "string",
                                    "description": "源目录绝对路径"
                                },
                                "targetDir": {
                                    "type": "string",
                                    "description": "目标目录绝对路径"
                                },
                                "overwrite": {
                                    "type": "boolean",
                                    "description": "是否覆盖已存在的文件",
                                    "default": False
                                }
                            },
                            "required": ["sourceDir", "targetDir"]
                        }
                    }
                ]
            }
        }
    elif method == 'tools/call':
        params = request.get('params', {})
        tool_name = params.get('name')
        arguments = params.get('arguments', {})

        if tool_name == 'copy_directory':
            source_dir = arguments.get('sourceDir')
            target_dir = arguments.get('targetDir')
            overwrite = arguments.get('overwrite', False)
            
            if not source_dir:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "缺少sourceDir参数"
                    }
                }
            
            if not target_dir:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "缺少targetDir参数"
                    }
                }

            result = copy_directory(source_dir, target_dir, overwrite)
            if result:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, ensure_ascii=False, indent=2)
                            }
                        ]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": "复制失败"
                    }
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"未知工具: {tool_name}"
                }
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"未知方法: {method}"
            }
        }


def run_mcp_server():
    """运行 MCP 服务器"""
    while True:
        try:
            line = input()
            if not line:
                continue
            request = json.loads(line)
            response = handle_request(request)
            if response:
                send_message(response)
        except EOFError:
            break
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}", file=sys.stderr)
        except Exception as e:
            print(f"处理请求错误: {e}", file=sys.stderr)


if __name__ == "__main__":
    # 检查是否是 MCP 模式（通过环境变量或参数）
    if len(sys.argv) > 1 and sys.argv[1] == '--mcp':
        # MCP 服务器模式
        run_mcp_server()
    elif len(sys.argv) > 3:
        # 命令行模式
        source_dir = sys.argv[1]
        target_dir = sys.argv[2]
        overwrite = sys.argv[3].lower() == 'true'
        result = copy_directory(source_dir, target_dir, overwrite)
        print(f"复制结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    else:
        # 默认 MCP 服务器模式
        run_mcp_server()
