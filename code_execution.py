import subprocess
import tempfile
import sys
import os
import signal
import asyncio
from typing import Dict, Any
import resource
import threading
import time
import http.server
import socketserver
from pathlib import Path

class CodeExecutionMCPServer:
    def __init__(self):
        self.max_execution_time = 30
        self.max_memory_mb = 512
        self.running_servers = {}
        
    async def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Main MCP request handler"""
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "tools/list":
            return self.list_tools()
        elif method == "tools/call":
            return await self.call_tool(params)
        else:
            return {"error": f"Unknown method: {method}"}
    
    def list_tools(self) -> Dict[str, Any]:
        return {
            "tools": [
                {
                    "name": "execute_python",
                    "description": "Execute Python code and return output",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "timeout": {"type": "integer", "optional": True, "default": 30}
                        },
                        "required": ["code"]
                    }
                },
                {
                    "name": "execute_javascript",
                    "description": "Execute JavaScript code with Node.js",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "timeout": {"type": "integer", "optional": True, "default": 30}
                        },
                        "required": ["code"]
                    }
                },
                {
                    "name": "serve_html",
                    "description": "Serve HTML content on local server",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "html": {"type": "string"},
                            "port": {"type": "integer", "optional": True, "default": 8080}
                        },
                        "required": ["html"]
                    }
                }
            ]
        }
    
    async def call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool calls"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            if tool_name == "execute_python":
                return await self.execute_python(arguments)
            elif tool_name == "execute_javascript":
                return await self.execute_javascript(arguments)
            elif tool_name == "serve_html":
                return await self.serve_html(arguments)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
    
    async def execute_python(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python code in subprocess"""
        code = args["code"]
        timeout = args.get("timeout", self.max_execution_time)
        
        # Add memory and import restrictions for safety
        safe_code = f"""
import resource
import sys

# Set memory limit
resource.setrlimit(resource.RLIMIT_AS, ({self.max_memory_mb * 1024 * 1024}, {self.max_memory_mb * 1024 * 1024}))

# Block dangerous imports
blocked_modules = {{'subprocess', 'os', 'shutil', 'socket', 'urllib', 'requests', 'pickle'}}
original_import = __builtins__.__import__

def safe_import(name, *args, **kwargs):
    if name in blocked_modules:
        raise ImportError(f"Import of '{{name}}' is blocked for security")
    return original_import(name, *args, **kwargs)

__builtins__.__import__ = safe_import

# User code starts here
{code}
"""
        
        # Write to temp script
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(safe_code)
            script_path = f.name
        
        try:
            # Run it with timeout and resource limits
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir()
            )
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Return code: {proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
                    }
                ]
            }
            
        except subprocess.TimeoutExpired:
            return {"error": f"Python execution timed out after {timeout} seconds"}
        except Exception as e:
            return {"error": f"Python execution failed: {str(e)}"}
        finally:
            # Clean up temp file
            if os.path.exists(script_path):
                os.unlink(script_path)
    
    async def execute_javascript(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute JavaScript code with Node.js"""
        code = args["code"]
        timeout = args.get("timeout", self.max_execution_time)
        
        # Add basic safety wrapper
        safe_code = f"""
// Set timeout for execution
setTimeout(() => {{
    console.error('Script timed out');
    process.exit(1);
}}, {timeout * 1000});

// Block dangerous modules
const originalRequire = require;
const blockedModules = ['fs', 'child_process', 'net', 'http', 'https', 'crypto'];

require = function(module) {{
    if (blockedModules.includes(module)) {{
        throw new Error(`Module '${{module}}' is blocked for security`);
    }}
    return originalRequire(module);
}};

// User code starts here
{code}
"""
        
        # Write to temp script
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(safe_code)
            script_path = f.name
        
        try:
            # Check if Node.js is available
            node_check = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                timeout=5
            )
            
            if node_check.returncode != 0:
                return {"error": "Node.js not found. Please install Node.js to execute JavaScript."}
            
            # Run JavaScript with Node.js
            proc = subprocess.run(
                ["node", script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir()
            )
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Return code: {proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
                    }
                ]
            }
            
        except subprocess.TimeoutExpired:
            return {"error": f"JavaScript execution timed out after {timeout} seconds"}
        except Exception as e:
            return {"error": f"JavaScript execution failed: {str(e)}"}
        finally:
            # Clean up temp file
            if os.path.exists(script_path):
                os.unlink(script_path)
    
    async def serve_html(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Serve HTML content on local server"""
        html_content = args["html"]
        port = args.get("port", 8080)
        
        # Create temp directory for serving
        temp_dir = tempfile.mkdtemp()
        html_path = os.path.join(temp_dir, "index.html")
        
        try:
            # Write HTML to file
            with open(html_path, "w") as f:
                f.write(html_content)
            
            # Start HTTP server in background thread
            def start_server():
                os.chdir(temp_dir)
                handler = http.server.SimpleHTTPRequestHandler
                
                # Try to bind to the port
                try:
                    with socketserver.TCPServer(("", port), handler) as httpd:
                        self.running_servers[port] = httpd
                        httpd.serve_forever()
                except OSError as e:
                    print(f"Port {port} already in use: {e}")
            
            # Start server in background
            server_thread = threading.Thread(target=start_server, daemon=True)
            server_thread.start()
            
            # Give server time to start
            await asyncio.sleep(1)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"HTML server started!\nAccess your page at: http://localhost:{port}\nServing from: {temp_dir}"
                    }
                ]
            }
            
        except Exception as e:
            return {"error": f"Failed to serve HTML: {str(e)}"}
    
    def stop_server(self, port: int):
        """Stop a running server"""
        if port in self.running_servers:
            self.running_servers[port].shutdown()
            del self.running_servers[port]
            return True
        return False

# Usage example and test
async def main():
    server = SimpleExecutionMCPServer()
    
    # Test Python execution
    print("Testing Python execution...")
    python_request = {
        "method": "tools/call",
        "params": {
            "name": "execute_python",
            "arguments": {
                "code": """
import math
print("Hello from Python!")
print(f"Pi is approximately {math.pi:.4f}")

# Test some computation
numbers = [1, 2, 3, 4, 5]
squared = [x**2 for x in numbers]
print(f"Squared: {squared}")
print(f"Sum of squares: {sum(squared)}")
"""
            }
        }
    }
    
    response = await server.handle_mcp_request(python_request)
    print("Python result:", response)
    print()
    
    # Test JavaScript execution
    print("Testing JavaScript execution...")
    js_request = {
        "method": "tools/call",
        "params": {
            "name": "execute_javascript",
            "arguments": {
                "code": """
console.log("Hello from JavaScript!");
console.log("Current time:", new Date().toISOString());

// Test some computation
const numbers = [1, 2, 3, 4, 5];
const squared = numbers.map(x => x * x);
console.log("Squared:", squared);
console.log("Sum of squares:", squared.reduce((a, b) => a + b, 0));
"""
            }
        }
    }
    
    response = await server.handle_mcp_request(js_request)
    print("JavaScript result:", response)
    print()
    
    # Test HTML serving
    print("Testing HTML serving...")
    html_request = {
        "method": "tools/call",
        "params": {
            "name": "serve_html",
            "arguments": {
                "html": """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .demo { background: #f0f0f0; padding: 20px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Hello from MCP HTML Server!</h1>
    <div class="demo">
        <p>This HTML was served by the MCP server.</p>
        <p>Current time: <span id="time"></span></p>
    </div>
    
    <script>
        document.getElementById('time').textContent = new Date().toLocaleString();
    </script>
</body>
</html>
""",
                "port": 8080
            }
        }
    }
    
    response = await server.handle_mcp_request(html_request)
    print("HTML server result:", response)

if __name__ == "__main__":
    asyncio.run(main())
