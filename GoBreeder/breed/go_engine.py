'''
Created on 6 Sep 2013

@author: GB108544
'''


'''Communicates with the external go programs using GTP2,
passes moves made back and forth from mediator to go program / stdferr'''

import sys
import config

class GoEngine(object):
    '''manages talking to the go and receiving moves / making moves / maintaining board state'''
    
    def __init__(self):
        self.board=dict()
        self.current_game_stats=dict()
        self.nzm=0
        self.player='black'
        self.gtpin=sys.stdin
        self.gtpout=sys.stdout
        self.game_in_progress=False
        self.player=None
        self.logging=True
        pass
    
    def clear_board(self):
        self.board=dict()
        for x in range(0,9):
            for y in range(0,9):
                self.board[(x,y)]=0 #-1 is black, 0 none, 1 white
        
    
    def start_new_game(self):
        #start new game
        self.nzm=0
        self.current_game_stats=dict()
        self.current_game_stats['moves_made']=0
        self.game_in_progress=True
    
    def initialise(self):#Do inital handshake
        #may have to sleep here?? Naa, wait for STD
        handshake_conversation=['B>> protocol_version',
                                'B<< = 2',
                                'B<<',
                                'B>> name',
                                'B<< = GoBreeder',
                                'B<<',
                                'B>> version',
                                'B<< = 1.0',
                                'B<<',
                                'B>> list_commands',
                                'B<< = boardsize',
                                'B<< clear_board',
                                'B<< echo',
                                'B<< echo_err',
                                'B<< genmove',
                                'B<< gogui-analyze_commands',
                                'B<< gogui-dummy-bwboard',
                                'B<< gogui-dummy-crash',
                                'B<< gogui-dummy-delay',
                                'B<< gogui-dummy-eplist',
                                'B<< gogui-dummy-file_open',
                                'B<< gogui-dummy-file_save',
                                'B<< gogui-dummy-gfx',
                                'B<< gogui-dummy-invalid',
                                'B<< gogui-dummy-live_gfx',
                                'B<< gogui-dummy-long_response',
                                'B<< gogui-dummy-next_failure',
                                'B<< gogui-dummy-next_success',
                                'B<< gogui-dummy-sboard',
                                'B<< gogui-dummy-sleep',
                                'B<< gogui-interrupt',
                                'B<< known_command',
                                'B<< list_commands',
                                'B<< name',
                                'B<< play',
                                'B<< protocol_version',
                                'B<< quit',
                                'B<< version',
                                'B<<',
                                'B>> gogui-interrupt',
                                'B<< =',
                                'B<<']
        board_setup_conversation=['B>> boardsize 9',
                                    'B<< =',
                                    'B<<',
                                    'B>> clear_board',
                                    'B<< =',
                                    'B<<',
                                    ]

        self.log('Go-Engine INIT\n')
        for line in handshake_conversation+board_setup_conversation:
            tokens=line.split()
            inout=tokens[0][1:]
            reading=(inout=='>>')
            if reading:
                target_verb=' '.join(tokens[1:])
                verb=sys.stdin.readline().strip()
                if target_verb!=verb:
                    self.log('ERR: Got :%s: Expected :%s:\n' % (verb,target_verb))
                    return False
            else:
                reply=' '.join(tokens[1:])
                sys.stdout.write(reply+'\n')
                sys.stdout.flush()
        self.start_new_game()
        return True
                
                    
            
                
            
    def log(self,msg):
        if self.logging:
            logfile=open(config.runlog,'a')
            logfile.write('ENGINE:\t\t'+msg)
            logfile.close()
        

        
    
    
    visual_pieces={-1:'B',
                   0:'-',
                   1:'W'}
    def render_board(self,dont_render_board=False,return_as_list_of_strings=False):
        pieces=0
        toggle=-1
        if not dont_render_board: self.log('\nRendering board\n') #no honestly just using randomly scattered siwtched for flow control is awesome
        board_rows=list()
        for y in range(0,9):
            row=''
            for x in range(0,9):
                toggle=-toggle
                row=row+GoEngine.visual_pieces[self.board[(x,y)]]
                #self.log("row="+row)
                if self.board[(x,y)]==toggle:
                    pieces+=1
                    
                    
            if not dont_render_board: self.log('\t'+row+'\n')
            board_rows.append(row+'\n')
        if not dont_render_board: self.log('\n')
        if return_as_list_of_strings:
            return board_rows
        
    def get_game_stats(self):
        return self.current_game_stats
    
    def translate_move_to_text(self,move):
        #gogui uses bot left as 
        rows=[9,8,7,6,5,4,3,2,1]
        cols=['A','B','C','D','E','F','G','H','J']
        x,y=move
        text_move=str(cols[x])+str(rows[y])
        return text_move
    
    def translate_move_from_text(self,move):
        rows=[99,8,7,6,5,4,3,2,1,0]
        cols={'A':0,'B':1,'C':2,'D':3,'E':4,'F':5,'G':6,'H':7,'J':8}
        x,y=(move[0],move[1])
        move=(cols[x],rows[int(y)])
        return move
        
    def send(self,msg):
        sys.stdout.write(msg)
        sys.stdout.flush()

    def receive(self):
        data=sys.stdin.readline()
        data=data.strip()
        return data    
    
    def play_pass_and_end(self):
        self.log('go_engine playing pass and end\n')
        self.send('=\n\n')
        self.log('go_engine waiting for final genmove verb\n')
        verb=self.receive()
        self.log('go_engine got verb %s\n' % verb)
        if 'genmove' not in verb:
            self.log('go_engine playing pass and end - expected genmove verb got %s\n' % verb)
        self.send('= PASS\n\n')
        
    def receive_move(self,verb=None):
        if not verb:
            verb=sys.stdin.readline().strip()
        if self.player=='black':
            play_token=1 #we're making the other players move
        else:
            play_token=-1
        if 'play' in verb:
            tokens=verb.split()
            move=tokens[2]
            move=self.translate_move_from_text(move)
            self.board[move]=play_token
            sys.stdout.write('=\n\n')
            sys.stdout.flush()
            return 'ok'
        else:
            return verb
    
    def play_move(self,move=None,move_limit=0):
        '''Play the move, report current state.'''

        if self.player=='black':
            play_token=-1
        else:
            play_token=1
        self.board[(move)]=play_token
        
        text_move=self.translate_move_to_text(move)
        sys.stdout.write('= '+text_move+'\n\n')
        sys.stdout.flush()
        

        self.current_game_stats['moves_made']+=1
        return 'ok'
        #now wait for returning move.
        #result=self.receive_move()    
        #return result        

        #if self.current_game_stats['moves_made']>move_limit:
        #    return 'game finished %d nzm' % self.nzm
        #else:
        #    return 'game in progress'
