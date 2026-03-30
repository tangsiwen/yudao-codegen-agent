import os
import json
import requests
import sys
from datetime import datetime

# 静态变量配置
YUDAO_BASE_URL = 'http://localhost:48070/admin-api'
TENANT_NAME = '芋道源码'
USERNAME = 'admin'
PASSWORD = 'admin123'
TENANT_ID = '1'

# Token存储文件
TOKEN_FILE = 'yudao_token.json'


def load_token():
    """从本地文件加载token"""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            # 检查token是否过期
            if 'expiresTime' in token_data:
                expires_time_val = token_data['expiresTime']
                if isinstance(expires_time_val, str):
                    # 字符串格式的时间
                    expires_time = datetime.fromisoformat(expires_time_val)
                elif isinstance(expires_time_val, (int, float)):
                    # 时间戳格式的时间
                    expires_time = datetime.fromtimestamp(expires_time_val / 1000)  # 转换为秒
                else:
                    return None
                if datetime.now() < expires_time:
                    return token_data['accessToken']
    except Exception as e:
        print(f"加载token失败: {e}", file=sys.stderr)
    return None


def save_token(token_data):
    """保存token到本地文件"""
    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(token_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存token失败: {e}", file=sys.stderr)


def login():
    """登录获取token"""
    url = f"{YUDAO_BASE_URL}/system/auth/login"
    payload = {
        "tenantName": TENANT_NAME,
        "username": USERNAME,
        "password": PASSWORD,
        "rememberMe": True
    }
    headers = {
        'Content-Type': 'application/json',
        'tenant-id': TENANT_ID
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        print(f"登录接口返回: {json.dumps(result, ensure_ascii=False, indent=2)}", file=sys.stderr)
        if result.get('code') == 0:
            token_data = result.get('data')
            save_token(token_data)
            return token_data['accessToken']
        else:
            print(f"登录失败: {result.get('msg')}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"登录请求失败: {e}", file=sys.stderr)
        return None


def call_codegen_create_list(table_name):
    """调用代码生成-导入数据表接口"""
    # 尝试从本地加载token
    token = load_token()
    if not token:
        token = login()

    if not token:
        print("获取token失败，无法调用接口", file=sys.stderr)
        return None

    url = f"{YUDAO_BASE_URL}/infra/codegen/create-list"
    payload = {
        "dataSourceConfigId": 0,
        "tableNames": [table_name]
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
        'tenant-id': TENANT_ID
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        # 如果返回401或400，可能是token过期或无效，重新登录
        if response.status_code in [400, 401]:
            print("token可能过期，重新登录...", file=sys.stderr)
            token = login()
            if not token:
                print("重新登录失败", file=sys.stderr)
                return None
            # 使用新token重新请求
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'tenant-id': TENANT_ID
            }
            response = requests.post(url, json=payload, headers=headers)

        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        print(f"调用接口失败: {e}", file=sys.stderr)
        return None


def call_codegen_download(table_id, className, downloadPath=None):
    """调用代码生成-下载代码接口"""
    # 尝试从本地加载token
    token = load_token()
    if not token:
        token = login()

    if not token:
        print("获取token失败，无法调用接口", file=sys.stderr)
        return None

    url = f"{YUDAO_BASE_URL}/infra/codegen/download"
    params = {
        "tableId": table_id
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'tenant-id': TENANT_ID
    }

    try:
        response = requests.get(url, params=params, headers=headers, stream=True)

        # 如果返回401或400，可能是token过期或无效，重新登录
        if response.status_code in [400, 401]:
            print("token可能过期，重新登录...", file=sys.stderr)
            token = login()
            if not token:
                print("重新登录失败", file=sys.stderr)
                return None
            # 使用新token重新请求
            headers = {
                'Authorization': f'Bearer {token}',
                'tenant-id': TENANT_ID
            }
            response = requests.get(url, params=params, headers=headers, stream=True)

        response.raise_for_status()
        
        # 确定保存路径
        save_dir = downloadPath if downloadPath else '.'
        # 确保目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        # 保存文件
        file_name = f"codegen_{className}.zip"
        file_path = os.path.join(save_dir, file_name)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # 解压缩文件
        import zipfile
        extract_dir = os.path.join(save_dir, f"codegen_{className}")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        return {
            "success": True,
            "message": f"代码生成成功，文件已保存为 {file_name} 并解压缩到 {extract_dir} 文件夹",
            "file_path": os.path.abspath(file_path),
            "extract_dir": os.path.abspath(extract_dir)
        }
    except Exception as e:
        error_msg = f"调用接口失败: {e}"
        print(error_msg, file=sys.stderr)
        return {
            "success": False,
            "message": error_msg
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
                    "name": "yudao-codegen",
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
                        "name": "codegen_create_list",
                        "description": "导入数据表到芋道代码生成器",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "tableName": {
                                    "type": "string",
                                    "description": "要导入的数据表名称"
                                }
                            },
                            "required": ["tableName"]
                        }
                    },
                    {
                        "name": "codegen_download",
                        "description": "下载生成的代码",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "tableId": {
                                    "type": "string",
                                    "description": "表编号"
                                },
                                "className": {
                                    "type": "string",
                                    "description": "类名"
                                },
                                "downloadPath": {
                                    "type": "string",
                                    "description": "下载路径，默认为当前目录"
                                }
                            },
                            "required": ["tableId", "className"]
                        }
                    }
                ]
            }
        }
    elif method == 'tools/call':
        params = request.get('params', {})
        tool_name = params.get('name')
        arguments = params.get('arguments', {})

        if tool_name == 'codegen_create_list':
            table_name = arguments.get('tableName')
            if not table_name:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "缺少tableName参数"
                    }
                }

            result = call_codegen_create_list(table_name)
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
                        "message": "调用接口失败"
                    }
                }
        elif tool_name == 'codegen_download':
            table_id = arguments.get('tableId')
            className = arguments.get('className')
            downloadPath = arguments.get('downloadPath')
            if table_id is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "缺少tableId参数"
                    }
                }
            if not className:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "缺少className参数"
                    }
                }

            result = call_codegen_download(table_id, className, downloadPath)
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
                        "message": "调用接口失败"
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
    elif len(sys.argv) > 1:
        # 命令行模式
        table_name = sys.argv[1]
        result = call_codegen_create_list(table_name)
        print(f"接口返回结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    else:
        # 默认 MCP 服务器模式
        run_mcp_server()
