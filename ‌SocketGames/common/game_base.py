from abc import ABC, abstractmethod

class GameBase(ABC):
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = {}  # {player_id: {'username': str, 'ws': websocket}}
        self.username_to_id = {}
        self.current_player = 0
        self.game_started = False
        self.game_over = False

    def reset_game(self):
        """重置游戏状态"""
        self.current_player = 0
        self.game_over = False
        self.game_started = True

    @abstractmethod
    def check_winner(self):
        """检查是否有获胜者"""
        pass

    @abstractmethod
    async def broadcast_game_state(self):
        """广播游戏状态"""
        pass

    @abstractmethod
    async def broadcast_winner(self, winner):
        """广播获胜者"""
        pass

    @abstractmethod
    def make_move(self, player_id, position):
        """执行移动"""
        pass 