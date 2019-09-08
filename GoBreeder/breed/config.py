'''
Created on 14 Sep 2013

@author: GB108544
'''

#basepath
#basepath="/home/matth/breeders/GoBreeder_1/breed/"

basepath="c:\\cygwin64\\home\\matth\\breeders\\GoBreeder_1\\breed\\"

#all output goes here
runlog=basepath+'runlog.txt'

#vm parms
vm_running_genome_file=basepath+'vm_running_genome.py'


#breeder parms
#string to invoke the player program (note double quoting)
pythonpath='c:\\python27amd64\\python.exe'
gobreeder='"%s %smediator.py -genome_file %sbreeding_genome.py"' % (pythonpath,basepath,basepath)
gosumi='"java -jar %sgosumi_dks.jar"' % basepath
gosumi_2013='"java -jar %sgosumi_2013.jar -timeout 1"' % basepath
player_program=gobreeder
#and for the enemy program
enemy_program=gosumi_2013#player_program[0:-1]+' -silent"'#
referee_program_command=basepath+'ref_v0.1_exe'

two_gtp_command=basepath+'gogui-twogtp.exe'

#board size...
board_size=9  #oh yeah, about this. MUST BE 9 until the near future...

#file to hold 'previous' generation - just-tested pop is copied to here
previous_population_file=basepath+'current_population.py_save'

#this hold the current population being evaluated
current_population_file=basepath+'current_population.py'


#stats file name
previous_population_stats_file=previous_population_file+'_stats'

#entropy!?
rand_max=9  #why 4? why .. used of op_rnd 
#    def opcode_rnd(self):
#        self.reg_RES=int(random.random()*config.rand_max)-(config.rand_max/2)
#        self.set_SGN()

#historical runstats for genomes (watch for collisions)
history_stats_base=basepath+'histories/'
record_stats=False

#(not used yet)
#threads_or_processes  True/threads, False/processes, None/block file IO
threads_or_processes=False

#show cmd breeder executes to play two players against each other
show_cmd=True

graph_move_pc=True
