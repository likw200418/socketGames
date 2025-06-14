import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.server import start_server

if __name__ == "__main__":
    asyncio.run(start_server()) 