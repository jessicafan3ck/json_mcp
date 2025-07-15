import asyncio
import json
import subprocess
import tempfile
import os
import uuid
from typing import Dict, Any, Optional
import docker
import threading
import time
from pathlib import Path

class CodeExecutionMCPServer:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.running_containers = {}
        
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
        """List available execution tools"""
        return {
            "tools": [
                {
                    "name": "execute_python",
                    "description": "Execute Python code and return output",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "packages": {"type": "array", "items": {"type": "string"}, "optional": True}
                        },
                        "required": ["code"]
                    }
                },
                {
                    "name": "execute_javascript",
                    "description": "Execute JavaScript/Node.js code",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "packages": {"type": "array", "items": {"type": "string"}, "optional": True}
                        },
                        "required": ["code"]
                    }
                },
                {
                    "name": "serve_html",
                    "description": "Serve HTML content with live preview",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "html": {"type": "string"},
                            "port": {"type": "integer", "optional": True}
                        },
                        "required": ["html"]
                    }
                },
                {
                    "name": "serve_react",
                    "description": "Build and serve React component",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "component": {"type": "string"},
                            "port": {"type": "integer", "optional": True}
                        },
                        "required": ["component"]
                    }
                },
                {
                    "name": "execute_visualization",
                    "description": "Execute data visualization code (matplotlib, plotly, etc.)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "library": {"type": "string", "enum": ["matplotlib", "plotly", "seaborn", "bokeh"]},
                            "output_format": {"type": "string", "enum": ["png", "svg", "html", "json"], "optional": True}
                        },
                        "required": ["code", "library"]
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
            elif tool_name == "serve_react":
                return await self.serve_react(arguments)
            elif tool_name == "execute_visualization":
                return await self.execute_visualization(arguments)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": f"Execution failed: {str(e)}"}
    
    async def execute_python(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python code in Docker container"""
        code = args["code"]
        packages = args.get("packages", [])
        
        # Create Dockerfile content
        dockerfile_content = f"""
FROM python:3.9-slim
RUN pip install numpy pandas matplotlib plotly seaborn {' '.join(packages)}
WORKDIR /app
COPY script.py .
CMD ["python", "script.py"]
"""
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write code to file
            with open(f"{temp_dir}/script.py", "w") as f:
                f.write(code)
            
            # Write Dockerfile
            with open(f"{temp_dir}/Dockerfile", "w") as f:
                f.write(dockerfile_content)
            
            # Build and run container
            try:
                image = self.docker_client.images.build(
                    path=temp_dir,
                    tag=f"python-exec-{uuid.uuid4().hex[:8]}"
                )[0]
                
                container = self.docker_client.containers.run(
                    image.id,
                    remove=True,
                    stdout=True,
                    stderr=True,
                    timeout=30
                )
                
                output = container.decode('utf-8')
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Python execution completed:\n\n{output}"
                        }
                    ]
                }
                
            except Exception as e:
                return {"error": f"Docker execution failed: {str(e)}"}
    
    async def execute_javascript(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute JavaScript code in Node.js container"""
        code = args["code"]
        packages = args.get("packages", [])
        
        package_json = {
            "name": "js-execution",
            "version": "1.0.0",
            "dependencies": {pkg: "latest" for pkg in packages}
        }
        
        dockerfile_content = f"""
FROM node:16-slim
WORKDIR /app
COPY package.json .
RUN npm install
COPY script.js .
CMD ["node", "script.js"]
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(f"{temp_dir}/script.js", "w") as f:
                f.write(code)
            
            with open(f"{temp_dir}/package.json", "w") as f:
                json.dump(package_json, f)
            
            with open(f"{temp_dir}/Dockerfile", "w") as f:
                f.write(dockerfile_content)
            
            try:
                image = self.docker_client.images.build(
                    path=temp_dir,
                    tag=f"js-exec-{uuid.uuid4().hex[:8]}"
                )[0]
                
                container = self.docker_client.containers.run(
                    image.id,
                    remove=True,
                    stdout=True,
                    stderr=True,
                    timeout=30
                )
                
                output = container.decode('utf-8')
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"JavaScript execution completed:\n\n{output}"
                        }
                    ]
                }
                
            except Exception as e:
                return {"error": f"Docker execution failed: {str(e)}"}
    
    async def serve_html(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Serve HTML content on a web server"""
        html_content = args["html"]
        port = args.get("port", 8080)
        
        dockerfile_content = f"""
FROM nginx:alpine
COPY index.html /usr/share/nginx/html/
EXPOSE {port}
CMD ["nginx", "-g", "daemon off;"]
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(f"{temp_dir}/index.html", "w") as f:
                f.write(html_content)
            
            with open(f"{temp_dir}/Dockerfile", "w") as f:
                f.write(dockerfile_content)
            
            try:
                image = self.docker_client.images.build(
                    path=temp_dir,
                    tag=f"html-serve-{uuid.uuid4().hex[:8]}"
                )[0]
                
                container = self.docker_client.containers.run(
                    image.id,
                    ports={f'{port}/tcp': port},
                    detach=True,
                    remove=True
                )
                
                container_id = container.id[:12]
                self.running_containers[container_id] = container
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"HTML server started!\nAccess at: http://localhost:{port}\nContainer ID: {container_id}"
                        }
                    ]
                }
                
            except Exception as e:
                return {"error": f"Failed to serve HTML: {str(e)}"}
    
    async def serve_react(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Build and serve React component"""
        component_code = args["component"]
        port = args.get("port", 3000)
        
        # Create a basic React app structure
        package_json = {
            "name": "react-component",
            "version": "1.0.0",
            "dependencies": {
                "react": "^18.0.0",
                "react-dom": "^18.0.0",
                "react-scripts": "5.0.1"
            },
            "scripts": {
                "start": "react-scripts start",
                "build": "react-scripts build"
            }
        }
        
        app_js = f"""
import React from 'react';
import ReactDOM from 'react-dom/client';

{component_code}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
"""
        
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>React Component</title>
</head>
<body>
    <div id="root"></div>
</body>
</html>
"""
        
        dockerfile_content = f"""
FROM node:16-alpine
WORKDIR /app
COPY package.json .
RUN npm install
COPY public/ public/
COPY src/ src/
EXPOSE {port}
CMD ["npm", "start"]
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create directory structure
            os.makedirs(f"{temp_dir}/src")
            os.makedirs(f"{temp_dir}/public")
            
            with open(f"{temp_dir}/package.json", "w") as f:
                json.dump(package_json, f)
            
            with open(f"{temp_dir}/src/index.js", "w") as f:
                f.write(app_js)
            
            with open(f"{temp_dir}/public/index.html", "w") as f:
                f.write(html_template)
            
            with open(f"{temp_dir}/Dockerfile", "w") as f:
                f.write(dockerfile_content)
            
            try:
                image = self.docker_client.images.build(
                    path=temp_dir,
                    tag=f"react-serve-{uuid.uuid4().hex[:8]}"
                )[0]
                
                container = self.docker_client.containers.run(
                    image.id,
                    ports={f'{port}/tcp': port},
                    detach=True,
                    remove=True,
                    environment={"PORT": str(port)}
                )
                
                container_id = container.id[:12]
                self.running_containers[container_id] = container
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"React app building and starting...\nWill be available at: http://localhost:{port}\nContainer ID: {container_id}"
                        }
                    ]
                }
                
            except Exception as e:
                return {"error": f"Failed to serve React: {str(e)}"}
    
    async def execute_visualization(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute visualization code and return image/HTML"""
        code = args["code"]
        library = args["library"]
        output_format = args.get("output_format", "png")
        
        # Add code to save visualization
        if library == "matplotlib":
            code += f"\nimport matplotlib.pyplot as plt\nplt.savefig('/app/output.{output_format}')\nplt.close()"
        elif library == "plotly":
            if output_format == "html":
                code += f"\nimport plotly.offline as pyo\npyo.plot(fig, filename='/app/output.html', auto_open=False)"
            else:
                code += f"\nfig.write_image('/app/output.{output_format}')"
        
        dockerfile_content = f"""
FROM python:3.9-slim
RUN pip install {library} pandas numpy
WORKDIR /app
COPY script.py .
CMD ["python", "script.py"]
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(f"{temp_dir}/script.py", "w") as f:
                f.write(code)
            
            with open(f"{temp_dir}/Dockerfile", "w") as f:
                f.write(dockerfile_content)
            
            try:
                image = self.docker_client.images.build(
                    path=temp_dir,
                    tag=f"viz-exec-{uuid.uuid4().hex[:8]}"
                )[0]
                
                container = self.docker_client.containers.run(
                    image.id,
                    remove=True,
                    stdout=True,
                    stderr=True,
                    timeout=30
                )
                
                # Get the output file from container
                # In real implementation, you'd copy the file out
                output = container.decode('utf-8')
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Visualization created!\nOutput: {output}\nFile saved as output.{output_format}"
                        }
                    ]
                }
                
            except Exception as e:
                return {"error": f"Visualization failed: {str(e)}"}

# Usage example
async def main():
    server = CodeExecutionMCPServer()
    
    # Test Python execution
    python_request = {
        "method": "tools/call",
        "params": {
            "name": "execute_python",
            "arguments": {
                "code": """
import numpy as np
import matplotlib.pyplot as plt

x = np.linspace(0, 10, 100)
y = np.sin(x)

print("Generated sine wave data")
print(f"X range: {x.min():.2f} to {x.max():.2f}")
print(f"Y range: {y.min():.2f} to {y.max():.2f}")
"""
            }
        }
    }
    
    response = await server.handle_mcp_request(python_request)
    print("Python execution:", response)

if __name__ == "__main__":
    asyncio.run(main())
