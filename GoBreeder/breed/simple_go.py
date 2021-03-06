#Simple Go playing program
#Goals are:
#1) Easy to understand:
#   If fully understanding GnuGo could be considered advanced,
#   then this should be beginner level Go playing program
#   Main focus is in understanding code, not in fancy stuff.
#   It should illustrate Go concepts using simple code.
#2) Plays enough well to get solid rating at KGS
#3) Small
#4) License should be GPL compatible: probably multiple licenses.

#Why at Senseis?
#Goal is to illustrate Go programming and not to code another "GnuGo".
#Senseis looks like good place to co-operatively write text and 
#create diagrams to illustrate algorithms.
#So main focus is in explaining code.
#Also possibility is to crosslink between concepts and documented code.


import re, string, time, random, sys
from types import *
from math import sqrt
from copy import deepcopy

EMPTY = "."
BLACK = "X"
WHITE = "O"

colors = [BLACK, WHITE]

other_side = {BLACK: WHITE, WHITE: BLACK}

PASS_MOVE = (-1, -1)

x_coords_string = "ABCDEFGHJKLMNOPQRSTUVXYZ"

def move_as_string(move, board_size):
    """convert move tuple to string
          example: (2, 3) -> B3
    """
    if move==PASS_MOVE: return "PASS"
    x, y = move
    return x_coords_string[x-1] + str(y)

def string_as_move(m, size):
    """convert string to move tuple
          example: B3 -> (2, 3)
    """
    if m=="PASS": return PASS_MOVE
    x = string.find(x_coords_string, m[0]) + 1
    y = int(m[1:])
    return x,y

class Board:
    def __init__(self, size):
        """Initialize board:
              argument: size
        """
        self.size = size
        self.side = BLACK #side to move
        self.captures = {} #number of stones captured
        self.captures[WHITE] = 0
        self.captures[BLACK] = 0
        self.goban = {} #actual board
        #Create and initialize board as empty size*size
        for pos in self.iterate_goban():
            self.goban[pos] = EMPTY

    def iterate_goban(self):
        """This goes trough all positions in goban
              Example usage: see above __init__ method
        """
        for x in range(1, self.size+1):
            for y in range(1, self.size+1):
                yield x, y

    def iterate_neighbour(self, pos):
        """This goes trough all neighbour positions:
              down, up, left, right
              Example usage: see legal_move method
        """
        x, y = pos
        for x2,y2 in ((x,y-1), (x,y+1), (x-1,y), (x+1,y)):
            if 1<=x2<=self.size and 1<=y2<=self.size:
                yield (x2, y2)

    def key(self):
        """This returns unique key for board.
              Returns board as string.
              Key can be used for example in super-ko detection
        """
        stones = []
        for pos in self.iterate_goban():
            stones.append(self.goban[pos])
        return string.join(stones, "")

    def change_side(self):
        self.side = other_side[self.side]

    def legal_move(self, move):
        """Test whether given move is legal.
              Returns truth value.
        """
        if move==PASS_MOVE:
            return True
        if move not in self.goban: return False
        if self.goban[move]!=EMPTY: return False
        for pos in self.iterate_neighbour(move):
            if self.goban[pos]==EMPTY: return True
            if self.goban[pos]==self.side and self.liberties(pos)>1: return True
            if self.goban[pos]==other_side[self.side] and self.liberties(pos)==1: return True
        return False

    def liberties(self, pos):
        """Count liberties for group at given position.
              Returns number of liberties.
              This is simple flood algorith tha keeps track of stones and empty intersections visited.
              pos_list keeps track of stones we need to visit.
              pos_list starts with argument pos.
              We go trough each stone in pos_list.
              First we check whether we have already seen this position and skip it if it so.
              Then we go trough each neighbour intersection skipping those we have already seen.
              If intersection is empty we add to liberty_count and mark this as visited.
              If intersection belongs to same group we add it to stones to go trough (pos_list).
              If it gets added more than once that is not problem because we as first step skip stones already seen.
              It would be more complex to check for duplicates now: we would need to check both seen_pos and pos_list.
              TODO: add senseis diagram illustrating algorithm.
        """
        seen_pos = {}
        liberty_count = 0
        group_color = self.goban[pos]
        pos_list = [pos]
        while pos_list:
            pos2 = pos_list.pop()
            if pos2 in seen_pos: continue
            seen_pos[pos2] = True
            for pos3 in self.iterate_neighbour(pos2):
                if pos3 in seen_pos: continue
                if self.goban[pos3]==EMPTY:
                    liberty_count = liberty_count + 1
                    seen_pos[pos3] = True
                    continue
                if self.goban[pos3]==group_color:
                    pos_list.append(pos3)
        return liberty_count

    def remove_group(self,  pos):
        """Recursively remove given group from board and updating capture counts.
              First we remove this stone and then recursively call ourself to remove neighbour stones.
        """
        remove_color = self.goban[pos]
        self.goban[pos] = EMPTY
        self.captures[remove_color] = self.captures[remove_color] + 1
        for pos2 in self.iterate_neighbour(pos):
            if self.goban[pos2] == remove_color:
                self.remove_group(pos2)

    def make_move(self, move):
        """Make move given in argument.
              Returns move or None if illegl.
              First we check given move for legality.
              Then we make move and remove captured opponent groups if there are any.
        """
        if move==PASS_MOVE:
            self.change_side()
            return move
        if self.legal_move(move):
            self.goban[move] = self.side
            remove_color = other_side[self.side] 
            for pos in self.iterate_neighbour(move):
                if self.goban[pos]==remove_color and self.liberties(pos)==0:
                    self.remove_group(pos)
            self.change_side()
            return move
        return None

    def __str__(self):
        """Convert position to string suitable for printing to screen.
              Returns board as string.
        """
        s = self.side + " to move:\n"
        s = s + "Captured stones: "
        s = s + "White: " + str(self.captures[WHITE])
        s = s + " Black: " + str(self.captures[BLACK]) + "\n"
        board_x_coords = "   " + x_coords_string[:self.size]
        s = s + board_x_coords + "\n"
        s = s + "  +" + "-"*self.size + "+\n"
        for y in range(self.size, 0, -1):
            if y < 10:
                board_y_coord = " " + str(y)
            else:
                board_y_coord = str(y)
            line = board_y_coord + "|"
            for x in range(1, self.size+1):
                line = line + self.goban[x,y]
            s = s + line + "|" + board_y_coord + "\n"
        s = s + "  +" + "-"*self.size + "+\n"
        s = s + board_x_coords + "\n"
        return s

class Game:
    def __init__(self, size):
        """Initialize game:
           argument: size
        """
        self.size = size
        self.current_board = Board(size)
        #past boards and moves
        self.board_history = []
        self.move_history = []
        #for super-ko detection
        self.position_seen = {}
        self.position_seen[self.current_board.key()] = True

    def make_move_in_new_board(self, move):
        """This is utility method.
              This does not check legality.
              It returns move in copied board and also key of new board
        """
        new_board = deepcopy(self.current_board)
        new_board.make_move(move)
        board_key = new_board.key()
        return new_board, board_key

    def legal_move(self, move):
        """check whether move is legal
              return truth value
              first check move legality on current board
              then check for repetition (situational super-ko)
        """
        if move==PASS_MOVE:
            return True
        if not self.current_board.legal_move(move): return False
        new_board, board_key = self.make_move_in_new_board(move)
        if board_key in self.position_seen: return False
        return True

    def make_move(self, move):
        """make given move and return new board
              or return None if move is illegal
              First check move legality.
              Then make move and update history.
        """
        if not self.legal_move(move): return None
        new_board, board_key = self.make_move_in_new_board(move)
        self.move_history.append(move)
        self.board_history.append(self.current_board)
        if move!=PASS_MOVE:
            self.position_seen[board_key] = True
        self.current_board = new_board
        return new_board

    def undo_move(self):
        """undo latest move and return current board
              or return None if at beginning.
              Update repetition history and make previous position current.
        """
        if not self.move_history: return None
        last_move = self.move_history.pop()
        if last_move!=PASS_MOVE:
            del self.position_seen[self.current_board.key()]
        self.current_board = self.board_history.pop()
        return self.current_board

    def list_moves(self):
        """return all legal moves including pass move
        """
        all_moves = [PASS_MOVE]
        for move in self.current_board.iterate_goban():
            if self.legal_move(move):
                all_moves.append(move)
        return all_moves

    def select_random_move(self):
        """return randomly selected move from all legal moves
        """
        return random.choice(self.list_moves())

    def generate_move(self):
        """generate move using random move generator
        """
        return self.select_random_move()


def main():
    size = 5
    g = Game(size)
    while True:
        move = g.generate_move()
        g.make_move(move)
        print move_as_string(move, g.size)
        print g.current_board
        #if last 2 moves are pass moves: exit loop 
        if len(g.move_history)>=2 and \
           g.move_history[-1]==PASS_MOVE and \
           g.move_history[-2]==PASS_MOVE:
            break

if __name__=="__main__":
    main()
