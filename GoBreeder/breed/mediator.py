'''
Created on 6 Sep 2013

@author: GB108544

No responsibilities are accepted for any decisions made during and pertaining to the implementation of this software.
'''

'''mediator module manages the breeder and the go game connection, with a breeder and go_engine respectivley'''
import argparse
import sys
import os
plotly=True
try:
    import plotly.express as px
    import plotly.io as pio
    pio.renderers.default='browser'
except:
    plotly=False
import pandas as pd
import breeder
import vm
import go_engine
import data_structures
import config
import datetime
import hashlib
from threaded_fileops import threaded_writelines

class Mediator(object):
    ## Gets board state/game over from go_engine, gives to breeder
    ## send moves from breeder to go engine
    def __init__(self,population_size=1000,govm=None,
                                            go_eng=None,genome=None,
                                            gtp_breed=False,
                                            silent=False,
                                            logprefix=''):
        self.logprefix=logprefix
        self.logging=not silent
        #DEBUG OVERRIDE
        self.logging=True
        if not gtp_breed:
            #if not a breed run, the genome has been turned into a GoGenome insance, otherwise is file of genome strings to breed
            self.genome=genome
            self.genome_hash=str(self.genome)
            
            self.log('genome  %s' % genome)
            
            self.govm=govm
            vm.logging=False

            self.go_eng=go_eng
            
            self.go_eng.logging=not silent
                
        else:
            self.log('Breeding...')
            self.gtp_breed=True
            self.breeder=breeder.Breeder(population_file=genome)
            self.go_engine=go_engine.GoEngine()
            
    def get_genome_lifetime_game(self):
        #search for hash as filename... ?512char filenames?
        dirn=config.history_stats_base
        hashlist=os.listdir(dirn)
        self.genome_dir=dirn+self.genome_hash+'/'
        if self.genome_hash not in hashlist:
            os.mkdir(self.genome_dir)
            self.game_dir=self.genome_dir+'game_1/'
            os.mkdir(self.game_dir)
            return 1 #what?
        
        #not the first game so;
        #find all dir entries that are numbers
        entries_found=os.listdir(self.genome_dir)
        
        #self.log(repr(entries_found))
        gamecount=max( [ int(e.replace('game_','')) for e in entries_found if e.replace('game_','').isdigit() ])
        self.game_dir=self.genome_dir+'game_%i/' % (gamecount+1)
        try:
            os.mkdir(self.game_dir)
        except OSError:
            pass #probably alread exists... :/ *cough*
        self.log('Genome lifetime game number : '+str(gamecount+1))
        return gamecount+1
        
        
    def record_game_start_info(self,game_number):
        #genome string, current game number, player color. VM version
        
        
        #i hope these opens close the file after themselves ;p
        
        #use threaded IO for the big bits
        lines=[repr(self.genome.dna)]#just one line..
        filehandle=open(self.genome_dir+'full_genome.py',"w")
        threaded_writelines(lines,filehandle)
        
        
        #make my mind up!
        handle=open(self.game_dir+'player_color',"w")
        handle.write(self.go_eng.player)
        handle.close()
        handle=open(self.game_dir+'VM_version',"w")
        handle.write(self.govm.version)
        handle.close()
        
    def record_move_info(self,pc_history):
        ###just take a dict of stuff and use the keys as filenames...
        ###
        
        self.move_dir=self.game_dir+'move_%i' % self.move_number
        try:
            os.mkdir(self.move_dir)
        except OSError:
            pass
        #oh i should really use os.pathsep + join etc..
        pc_history_filen=self.move_dir+'/rundata_pc_history'
        #thread the big writes..
        filehandle= open(pc_history_filen,'w')
        pc_history=[str(item) for item in pc_history]#not sure I really need that
        threaded_writelines(pc_history, filehandle)

        #go_eng board
        board_history_filen=self.move_dir+'/rundata_board'
        row_strings=self.go_eng.render_board(dont_render_board=True,return_as_list_of_strings=True)
        with open(board_history_filen,"w") as outf:
            outf.writelines(row_strings)
            
            
                
            
    def go_gtp(self):
        #Play single game with given genome
        
        if not self.go_eng.initialise():
            sys.stderr.write('ERR - Go Engine failed to INIT')
            sys.exit(9)
        play_games=True
        #find game for this play through for genome
        #game_number=self.get_genome_lifetime_game()

        game_number=0
        self.move_number=0
        start_recorded=False
        while play_games:
            self.log("Playing a game..")
            if game_number==1:
                self.log('Played one game, halting for now.')
                sys.exit(99)
                ##this hsould all really be sitting inside go_engine..?
            game_number+=1
            game_on=True
            while game_on:
                verb=self.receive()
                if 'PASS' in verb:
                    self.go_eng.play_pass_and_end()
                elif 'genmove' in verb:
                    verb,value=verb.split()
                    if value=='b':
                        self.go_eng.player='black'
                    else:
                        self.go_eng.player='white'
                        
                    #messy cos of how we set player up there ^^
                    if not start_recorded:
                        if config.record_stats:
                            self.record_game_start_info(game_number)
                        start_recorded=True
                    
                    
                    
                    #genome run data
                    #  genome_hash    /        game_{}/        move_{num}/
                    #                  full_genome               rundata_board
                    #                  player_color                rundata_{type}
                    #                  game_Stats
                    #                  vm_version
                    #                  
                    ##
                    
                    
                    move,pc_history=self.govm.get_move(board=self.go_eng.board,
                                            player=self.go_eng.player,
                                            program=self.genome)
                    self.move_number+=1
                    if config.record_stats:
                        self.record_move_info(pc_history)
                    if config.graph_move_pc:
                        pch_df=pd.DataFrame(zip(pc_history,range(0,len(pc_history))),columns=['pc','idx'],index=range(0,len(pc_history)))
                        fig = px.line(pch_df, x="idx", y="pc", title='PC history for move %s' % self.move_number)
                        fig.show()
                    if config.show_board_every_move:
                        #todo make config value
                        self.go_eng.render_board()
                    
                    
                    result=self.go_eng.play_move(move=move)
                    if result!='ok':
                        self.log('ERR - Got %s back from go_eng play move, expected ok' % result)
                        sys.exit(99)
                elif verb=='clear_board':
                    self.go_eng.clear_board()
                    self.send('=\n\n')
                elif 'play' in verb:
                    self.go_eng.receive_move(verb)
                elif 'boardsize' in verb:
                    sys.stdout.write('=\n\n')
                    sys.stdout.flush()
                elif 'final_score' in verb:
                    self.send('? unknown command: final_score\n\n')
                elif verb=='quit':
                    ##Need to capture i_win and fitness score?
                    #
                    #
                    # possiblky can correlate winners from logs and datestamps aftar?
                    self.go_eng.render_board()
                    self.log('%s Finished game' % datetime.datetime.now())
                    self.send('=\n\n')
                    sys.exit(0)
                else:
                    self.log('ERR - DONT KNOW WHAT TO DO got %s' % verb)
                    sys.exit(99)

    def check_for_obvious_wins(self):
        #check for obvious winning moves.
        #if found, return the move
        return None
    
    def evaluate_move_for_stupidity(self,move):
        #if move is stupid (throws the game)
        #find a safe 'space' to play into
        if self.move_is_stupid(move):
            move=self.find_a_safe_move()
        return move
    
    def move_is_stupid(self,move):
        #return True if the move is stupid
        return False
        
    def find_a_safe_move(self):
        #find a safe move... (empty space, or something...)
        return None


    def send(self,msg):
        sys.stdout.write(msg)
        sys.stdout.flush()

    def receive(self):
        data=sys.stdin.readline()
        data=data.strip()
        return data

    def log(self,msg):
        if self.logging:
            if os.path.exists(config.runlog):
                mode='a'
            else:
                mode='w'
            logfile=open(config.runlog,mode)
            logfile.write('MEDIATOR:'+self.logprefix+': '+msg+'\n')
            logfile.close()
    
    
    def go(self):
        play_games=True
        game_number=0
        while play_games:
            game_number+=1
            self.log('game_number %d' % game_number)
            #TODO: Plugin fitness / breeding criteria/methods
            game_stats=self.breeder.simulate_gtp_game()
            
            self.log('returned from simulate game. Mediator processing stats and breeding.')
            population_stats=self.breeder.end_of_game(game_stats=game_stats)
            
            



def setup_and_parse_args():
    #Args processing - 
    #            -genome_file - file containing the genome to run a game with,
    #            -or the population of genomes to breed (-gtp_breed yes
    
    #TODO:       -fresh_meat # - generate new pop with size #
    #            -system_max_clocks
    #            -system_max_genome_size
    #            -system_max_memoryons
    #            -system_max_population
    
    argparser=argparse.ArgumentParser(description="Breed or run 1st Capture Go GA's")
    
    argparser.add_argument('-genome_file',type=str,nargs=1,
                            help='Without -gtp-breed, run a single game with -genome_file')
    
    argparser.add_argument('-gtp_breed',
                           action='store_true',
                           help='Do a breeding run, using genome_file as starting population')

    argparser.add_argument('-silent',
                           action='store_true',
                           help='Do not generate any STDOUT, useful when playing a single genome against itself.')

    argparser.add_argument('-basepath',type=str,nargs=1,
                           #TODO: may be broken?
                            help='Base path to run from, defaults to CWD. (may be broken)')


    args=argparser.parse_args()
    return args 


if __name__=='__main__':
    
    args=setup_and_parse_args()
    
    if args.genome_file!=None:
        if len(args.genome_file[0])>0:
            genome_filename=args.genome_file[0]
            
            if args.basepath:
                basepath=args.basepath[0]
            else:
                basepath=os.getcwd()+'/'

            config.basepath=basepath

            breed=args.gtp_breed
            silent=args.silent
            
            if not breed:
                genome_file=open(genome_filename,'r')
                dna=eval(genome_file.readline())
                genome_file.close()
                genome=data_structures.GoGenome(dna=dna)    
            else:
                genome=genome_filename #population file of 1 or more genomes

            if not breed:
                #single game
                VM=vm.GoVM()
                GE=go_engine.GoEngine()
                M=Mediator(govm=VM,go_eng=GE,genome=genome,silent=silent,logprefix='Game')
                M.go_gtp()
                
            else:
                #breeding run
                M=Mediator(genome=genome_filename,gtp_breed=True,silent=silent,logprefix='Breeder')
                M.go()
