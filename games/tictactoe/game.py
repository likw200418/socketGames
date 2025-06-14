import json
from common.game_base import GameBase

class TicTacToeGame(GameBase):
    def __init__(self, room_id):
        super().__init__(room_id)
        self.board = [[' ' for _ in range(3)] for _ in range(3)]

    def reset_game(self):
        super().reset_game()
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        print(f"房间{self.room_id}游戏重置，棋盘清空")

    def check_winner(self):
        # 检查行
        for row in self.board:
            if row[0] == row[1] == row[2] != ' ':
                return row[0]
                
        # 检查列
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != ' ':
                return self.board[0][col]
                
        # 检查对角线
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != ' ':
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != ' ':
            return self.board[0][2]
            
        # 检查平局
        if all(cell != ' ' for row in self.board for cell in row):
            return 'D'
            
        return None

    async def broadcast_game_state(self):
        game_state = {
            'type': 'game_state',
            'board': self.board,
            'current_player': self.current_player,
            'players': [self.players[i]['username'] if i in self.players else None for i in range(2)],
            'game_started': self.game_started,
            'room_id': self.room_id
        }
        print(f"房间{self.room_id}广播游戏状态: {game_state}")
        for p in self.players.values():
            try:
                await p['ws'].send(json.dumps(game_state))
            except:
                pass

    async def broadcast_winner(self, winner):
        self.game_over = True
        message = {
            'type': 'game_over',
            'winner': winner,
            'room_id': self.room_id
        }
        for p in self.players.values():
            try:
                await p['ws'].send(json.dumps(message))
            except:
                pass

    def make_move(self, player_id, position):
        row, col = position
        if row < 0 or row > 2 or col < 0 or col > 2:
            return False, "无效的位置"
        if self.board[row][col] != ' ':
            return False, "该位置已有棋子"
        self.board[row][col] = 'X' if player_id == 0 else 'O'
        self.current_player = 1 - self.current_player
        return True, None 