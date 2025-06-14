import asyncio
import websockets
import json
import os
from flask import Flask, send_from_directory
from threading import Thread
from games.tictactoe.game import TicTacToeGame

# 用户数据文件
USERS_FILE = 'users.json'

# 加载用户数据
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# 保存用户数据
def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# 用户数据库
users_db = load_users()

# Flask全局定义
app = Flask(__name__, static_folder='../static')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

class GameServer:
    def __init__(self):
        self.rooms = {}  # {room_id: GameRoom}
        self.next_room_id = 1
        self.username_to_room = {}  # {username: room_id}
        self.connected_clients = set()
        self.online_users = {}  # {username: websocket}
        
    def get_or_create_room(self):
        # 创建新房间
        room_id = self.next_room_id
        self.next_room_id += 1
        self.rooms[room_id] = TicTacToeGame(room_id)
        return self.rooms[room_id]
        
    def get_rooms_info(self):
        rooms_info = []
        for room_id, room in self.rooms.items():
            rooms_info.append({
                'room_id': room_id,
                'player_count': len(room.players),
                'players': [room.players[i]['username'] if i in room.players else None for i in range(2)]
            })
        return rooms_info

    async def broadcast_rooms_info(self):
        """广播房间信息给所有在线玩家"""
        rooms_info = []
        for room_id, room in self.rooms.items():
            rooms_info.append({
                'room_id': room_id,
                'player_count': len(room.players)
            })
        
        # 广播给所有在线玩家
        for username, websocket in self.online_users.items():
            if websocket:
                try:
                    await websocket.send(json.dumps({
                        'type': 'rooms_info',
                        'rooms': rooms_info
                    }))
                except:
                    continue

    async def handle_client(self, websocket, path):
        """处理客户端连接"""
        username = None
        try:
            async for message in websocket:
                data = json.loads(message)
                print(f"收到消息: {data}")
                
                if data['type'] == 'register':
                    username = data['username']
                    password = data['password']
                    if username in users_db:
                        await websocket.send(json.dumps({
                            'type': 'register_result',
                            'success': False,
                            'msg': '用户名已存在'
                        }))
                        continue
                    users_db[username] = password
                    save_users(users_db)
                    await websocket.send(json.dumps({
                        'type': 'register_result',
                        'success': True,
                        'msg': '注册成功'
                    }))
                    continue

                elif data['type'] == 'login':
                    username = data['username']
                    password = data['password']
                    if username not in users_db or users_db[username] != password:
                        await websocket.send(json.dumps({
                            'type': 'login_result',
                            'success': False,
                            'msg': '用户名或密码错误'
                        }))
                        continue
                    if username in self.username_to_room:
                        await websocket.send(json.dumps({
                            'type': 'login_result',
                            'success': False,
                            'msg': '该用户已在其他房间中'
                        }))
                        continue
                    
                    # 保存用户连接信息
                    self.online_users[username] = websocket
                    
                    await websocket.send(json.dumps({
                        'type': 'login_result',
                        'success': True,
                        'msg': '登录成功'
                    }))
                    continue

                elif data['type'] == 'get_rooms':
                    if username is None:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '请先登录'}))
                        continue
                    
                    rooms_info = []
                    for room_id, room in self.rooms.items():
                        rooms_info.append({
                            'room_id': room_id,
                            'player_count': len(room.players)
                        })
                    await websocket.send(json.dumps({
                        'type': 'rooms_info',
                        'rooms': rooms_info
                    }))
                    continue

                elif data['type'] == 'join_room':
                    if username is None:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '请先登录'}))
                        continue
                    
                    if username in self.username_to_room:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '你已在其他房间中，请先退出'}))
                        continue
                    
                    room_id = data['room_id']
                    if room_id == 0:
                        # 创建新房间
                        room = self.get_or_create_room()
                    elif room_id not in self.rooms:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '房间不存在'}))
                        continue
                    else:
                        room = self.rooms[room_id]
                        
                    if len(room.players) >= 2:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '房间已满'}))
                        continue
                    
                    player_id = 0 if 0 not in room.players else 1
                    room.players[player_id] = {'username': username, 'ws': websocket}
                    room.username_to_id[username] = player_id
                    self.username_to_room[username] = room.room_id
                    
                    await websocket.send(json.dumps({
                        'type': 'join_result',
                        'success': True,
                        'player_id': player_id,
                        'room_id': room.room_id,
                        'msg': f'成功加入房间{room.room_id}，您是玩家{player_id+1}'
                    }))
                    
                    if len(room.players) == 2:
                        room.game_started = True
                        room.current_player = 0
                        room.reset_game()
                        await room.broadcast_game_state()
                    
                    # 广播房间信息给所有在线玩家
                    await self.broadcast_rooms_info()
                    continue

                elif data['type'] == 'leave_room':
                    if username is None or username not in self.username_to_room:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '你不在任何房间中'}))
                        continue
                    
                    room_id = self.username_to_room[username]
                    if room_id in self.rooms:
                        room = self.rooms[room_id]
                        if username in room.username_to_id:
                            player_id = room.username_to_id[username]
                            if player_id in room.players:
                                del room.players[player_id]
                                del room.username_to_id[username]
                                del self.username_to_room[username]
                                
                                if not room.players:
                                    del self.rooms[room_id]
                                else:
                                    room.game_started = False
                                    room.game_over = False
                                    room.reset_game()
                                    await room.broadcast_game_state()
                                
                                await websocket.send(json.dumps({
                                    'type': 'leave_result',
                                    'success': True,
                                    'msg': '成功退出房间'
                                }))
                                
                                # 广播房间信息给所有在线玩家
                                await self.broadcast_rooms_info()
                                continue
                    
                    await websocket.send(json.dumps({'type': 'error', 'msg': '退出房间失败'}))
                    continue

                elif data['type'] == 'move':
                    if username is None or username not in self.username_to_room:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '请先登录'}))
                        continue
                    
                    room_id = self.username_to_room[username]
                    if room_id not in self.rooms:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '房间不存在'}))
                        continue
                    
                    room = self.rooms[room_id]
                    if not room.game_started:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '游戏未开始'}))
                        continue
                    if room.game_over:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '游戏已结束，请重新开始'}))
                        continue
                    
                    player_id = room.username_to_id[username]
                    if room.current_player != player_id:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '还没到你的回合'}))
                        continue
                    
                    success, error_msg = room.make_move(player_id, data['position'])
                    if not success:
                        await websocket.send(json.dumps({'type': 'error', 'msg': error_msg}))
                        continue
                        
                    await room.broadcast_game_state()
                    winner = room.check_winner()
                    if winner:
                        await room.broadcast_winner(winner)
                    continue

                elif data['type'] == 'restart':
                    if not room or not room.game_started:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '游戏未开始'}))
                        continue
                    room.reset_game()
                    await room.broadcast_game_state()
                    continue

                elif data['type'] == 'chat':
                    if username is None:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '请先登录'}))
                        continue
                    
                    if username not in self.username_to_room:
                        await websocket.send(json.dumps({'type': 'error', 'msg': '你不在任何房间中'}))
                        continue
                    
                    room_id = self.username_to_room[username]
                    if room_id in self.rooms:
                        room = self.rooms[room_id]
                        # 广播聊天消息给房间内的所有玩家
                        for player_id, player in room.players.items():
                            if player['ws']:
                                await player['ws'].send(json.dumps({
                                    'type': 'chat',
                                    'message': f"{username}: {data['message']}"
                                }))
                    continue

                else:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'msg': '未知的消息类型'
                    }))
        except websockets.exceptions.ConnectionClosed:
            print("客户端连接关闭")
        finally:
            if username:
                # 清理用户连接信息
                if username in self.online_users:
                    del self.online_users[username]
                await self.handle_disconnect(username)

    async def handle_disconnect(self, username):
        """处理客户端断开连接"""
        if username in self.username_to_room:
            room_id = self.username_to_room[username]
            if room_id in self.rooms:
                room = self.rooms[room_id]
                if username in room.username_to_id:
                    player_id = room.username_to_id[username]
                    if player_id in room.players:
                        del room.players[player_id]
                        del room.username_to_id[username]
                        del self.username_to_room[username]
                        
                        if not room.players:
                            del self.rooms[room_id]
                        else:
                            room.game_started = False
                            room.game_over = False
                            room.reset_game()
                            await room.broadcast_game_state()
                        
                        # 广播房间信息给所有在线玩家
                        await self.broadcast_rooms_info()

async def start_server():
    server = GameServer()
    print("WebSocket服务器启动在 ws://0.0.0.0:8765")
    print("HTTP服务器启动在 http://0.0.0.0:8080")
    print("可以通过以下地址访问：")
    print("1. 本机访问：http://localhost:8080")
    print("2. 局域网访问：http://<本机IP>:8080")
    
    # 启动Flask服务器
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 启动WebSocket服务器
    async with websockets.serve(server.handle_client, "0.0.0.0", 8765):
        await asyncio.Future()  # 运行永久 