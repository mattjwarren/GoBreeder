'''
Created on 27 Jul 2013
 
@author: matt
'''

'''...It got better.  '''

import os
import data_structures
import random
random.seed()
import subprocess
import sys
import shutil
import time
import datetime
import vm
import config


class Breeder(object):
    '''
    classdocs
    '''
##instead of firing up a vm, run via single-genome game process and read output

    def __init__(self,population_size=1000,population_file=None):
        '''
        Constructor
        '''
        self.population=list()
        self.genome_stats=dict()
        self.current_simulation_member=0
        self.population_max=population_size
        self.population_file=population_file
        self.switch_players=False
        self.generation=0
        self.logging=True
        self.initialise_population(population_size=population_size)
        self.vm=vm.GoVM()
        
    
    def initialise_population(self,population_size=1000):
        #Initial seeding of entirely random population
        self.log('breeder Initialising population\n')
        if self.population_file:
            self.log('breeder using population file %s\n' % self.population_file)
            infile=open(self.population_file,'r')
            ctr=1
            for genome_repr in ( line for line in infile if line!='' ):
                if '<<<>>>' in genome_repr:
                    #entry is from a stats_save file so plit the stats off the end
                    genome_repr=genome_repr.split('<<<>>>')[0]
                    #may have been grep/culled so filter out front bit
                    if 'save_stats' in genome_repr:
                        genome_repr=genome_repr.split(':')[1]
                        
                        
                try:
                    dna=eval(genome_repr)#the slow
                    genome=data_structures.GoGenome(dna=dna)
                    self.population.append(genome)
                    self.genome_stats[self.population[-1]]=''
                    print "Done ressurrect of genome #",ctr
                    ctr+=1
                except SyntaxError:
                    print "Genome FAILED to resurrect #",ctr
                    pass
        else:
            self.log('breeder using genome genesis\n')
            for _n in range(0,population_size):
                new_genome=data_structures.GoGenome()
                self.population.append(new_genome)
                self.genome_stats[self.population[-1]]=''
        self.current_simulation_member=0
        self.population_max=len(self.population)
        self.log('pop size is %d\n' % len(self.population))
        #write 
        self.log('\t.. Fin ..\n')


    def simulate_gtp_game(self,player='black',
                            player_program=config.player_program,
                            enemy_program=config.enemy_program):
        enemy_player='black' if player=='white' else 'white'
        #Put genome to test into genome_test file
        #get command for program to test against
        self.log('Simulating GTP game for breeding\n')
        #create batch fie, run that?
        if self.switch_players:
            n=enemy_player
            enemy_player=player
            player=n
            self.switch_players=False
        else:
            self.switch_players=True
        self.log('\tI AM PLAYER %s\n' % player)
        genome_to_run=self.population[self.current_simulation_member]
        breeding_file=open("breeding_genome.py",'w')
        breeding_file.write(repr(genome_to_run.dna)+'\n')
        breeding_file.close()
        
        cmdstr='%s -%s %s -%s %s -size %d -referee %s -auto -verbose' % (config.two_gtp_command,
                                                                         player,
                                                                         player_program,
                                                                         enemy_player,
                                                                         enemy_program,
                                                                         config.board_size,
												                         config.referee_program_command)
        if config.show_cmd: self.log("CMDSTRING:"+cmdstr)
        game_process=subprocess.Popen(cmdstr,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        sout,serr=game_process.communicate()
        
        move_made='genmove' #integer /2 is good enough
        win_line='has won'
        moves=0
        won=False
        for line in sout.split('\n')+serr.split('\n'): #if works great, if not switch for sout
            if move_made in line:
                moves+=1
            elif win_line in line:
                tokens=line.split()
                if tokens[-3].lower()==player.lower():
                    won=True
        moves=moves/2
        self.log('\tevaluation: moves made=%d i_win %s\n' % (moves,str(won)))
        
        return {'moves_made':moves,
                'i_win':won}    
        
    def log(self,msg):
        if self.logging:
            logfile=open(config.runlog,'a')
            logfile.write("BREEDER:\t"+msg+"\n")
            logfile.close()
 
    
#'gogui-twogtp.exe -white "python ./mediator.py -genome_file ./champion_genome.py" -black "java -jar gosumi_dks.jar" -size 9 -referee ref_v0.1_exe'
    
    
    def simulate_move(self,board=None,player='black'):#,finished_game_fitness_data=None):

        move=self.vm.get_move(board=board,
                              player=player,
                              program=self.population[self.current_simulation_member])
        
        return move
        
    
        
    
    def end_of_game(self,game_stats=dict()):
        current_genome=self.population[self.current_simulation_member]
        self.log('game ended for genome:')
        self.log('%s' % current_genome)
        self.log('\tpop max=%d' % self.population_max)
        self.log('\tcurrent genome=%d' % self.current_simulation_member)
        self.genome_stats[current_genome]=game_stats
        
        #greater number of of moves is important; unless, you win, then the less moves the better
        

        self.current_simulation_member+=1
        max_pieces=0
        if self.current_simulation_member>len(self.population)-1:#?-1
            self.log('\tGeneration Assessed, breed new generation.')
            self.population=self.breed()
            self.current_simulation_member=0
            self.vm=vm.GoVM()
            
        current_genome=self.population[self.current_simulation_member]
        
        
        return {'max_pieces':max_pieces}
        
    
    def breed(self):
        #go through pop, assigning fitness. pick top ?% to breed
        self.generation+=1
        self.log('\tbreeding generation %d...' % self.generation)
        max_moves_made=max([ self.genome_stats[genome]['moves_made'] for genome in self.population ])
        min_moves_made=min([ self.genome_stats[genome]['moves_made'] for genome in self.population ])
        self.log('\tmin_moves_made %d' % min_moves_made)
        self.log('\tmax_moves_made %d' % max_moves_made)
        self.log('\tcalculating fitness')
        pop_fitness={}
        min_pop_fit=99999999
        max_pop_fit=0
        for genome in self.population:
            genome_moves=self.genome_stats[genome]['moves_made']
            genome_won=self.genome_stats[genome]['i_win']
            if not genome_won:
                fitness=genome_moves
                self.log('\tWe have a LOOSER! - fitness = %i\n' % fitness)
                
            else:
                fitness=(45-genome_moves) +46#  make any winner better than any loser.. // *1.9 #magic here shoul be 1/threshold_magic
                self.log('\t *** We have a WINNER! *** - fitness = %i\n\t\t%s' % (fitness,genome))
            pop_fitness[genome]=fitness
            if fitness<min_pop_fit:
                min_pop_fit=fitness
            if fitness>max_pop_fit:
                max_pop_fit=fitness
        
        date_time=datetime.datetime.now()
        self.log('%s // min_pop_fit,max_pop_fit=%f,%f' % (date_time,min_pop_fit,max_pop_fit))
        
        threshold_fitness=(min_pop_fit+((max_pop_fit-min_pop_fit)*.5)) #threshold_magic
        
        self.log('\tthreshold fitness=%f' % threshold_fitness)
        seed_pop=[ genome for genome in self.population if pop_fitness[genome]>=threshold_fitness ]
        self.log('\tLEN seed pop is %d of %d' % (len(seed_pop),len(self.population)))
        self.population_max=len(seed_pop)*2
                
                #2016 is this rught? max pop and max seed should be msit mutation? ...????
        mutation_rate=( 7.0/float(self.population_max) )*float(len(seed_pop)) #1% = total change in 100 generaion. we want that more like .. 1000
        self.log('\tMutation rate = %f %%' % mutation_rate)
        new_pop=seed_pop
        
        
        
        mutations=0        
        while len(new_pop)<self.population_max:
            for lucky_genome in seed_pop:
                #crossover
                #beautiful !! + Ugly!   people
                #we breed a succesful member with anyone frm the pop. Hmm....
                other_genome=random.choice(self.population)
                
                min_len=min([ len(other_genome),len(lucky_genome) ])
                crossover_point=random.randint(0,min_len-1)
                
                new_dna=lucky_genome[0:crossover_point]+other_genome[crossover_point:]
                
                new_genome=data_structures.GoGenome(dna=new_dna)
                for idx in range(0,len(new_genome)):
                    if random.random()*100.0<=mutation_rate: 
                        new_genome.mutate(idx)
                        mutations+=1
                new_pop.append(new_genome)
                
                #because length divs can be variable?
                if not len(new_pop)<self.population_max:
                    break
        self.log('Total breeding mutations='+str(mutations))
        #Save the old, write the new
        self.log('\n\nWriting population info...') 
        sfn=config.previous_population_file
        fn=config.current_population_file
        try:
            shutil.copyfile(fn,sfn)
        except:
            self.log('ERROR: Could not copy current_population_file.py')
            
            
        #write the stats file for the previous population,
        #and pare out any not in population
        stats_filename=config.previous_population_stats_file
        stats_file=open(stats_filename,'w')
        for genome in self.genome_stats.keys():
            if genome in self.population: #if genome was in population tested, then do stats
                stats_file.write(repr(genome.dna)+'<<<>>>'+repr(self.genome_stats[genome])+'<<<>>>'+str(fitness)+'\n')
            if genome not in new_pop: #if genome is not in new pop then kill its info
                del(self.genome_stats[genome]) 
        stats_file.close()


        gfile=open(fn,'w')
        for genome in new_pop:
            gfile.write(repr(genome.dna)+'\n')
        gfile.close()
        
        self.log('\tDone writing.')
                    
        return new_pop
                    
                
                
                
                
                
                
                
                
                
                
                
                
                
                
            
            
      
