'''
Created on 14 Sep 2013

@author: GB108544
'''

import os

def _choose_sep(path):
	if '/' in path and '\\' not in path:
		return '/'
	if '\\' in path and '/' not in path:
		return '\\'
	return os.sep


def _ensure_trailing_sep(path):
	sep = _choose_sep(path)
	if not path.endswith(sep):
		return path + sep
	return path


def _join_path(base, *parts):
	"""Join using the separator style already present in base."""
	sep = _choose_sep(base)
	out = base.rstrip('/\\')
	for part in parts:
		out = out + sep + str(part).strip('/\\')
	return out


# basepath
# basepath="/home/matth/breeders/GoBreeder_1/breed/"
basepath="c:\\cygwin64\\home\\matth\\breeders\\GoBreeder_1\\breed\\"
basepath=_ensure_trailing_sep(basepath)

# external Go tools live here (moved from breed/ into breed/external_go/)
external_go_basepath=_ensure_trailing_sep(_join_path(basepath, 'external_go'))

def set_basepath(new_basepath):
	"""Update basepath and recompute derived paths.

	NOTE: Some callers mutate config.basepath at runtime (e.g. mediator.py).
	Derived values (paths/command strings) must be recomputed to stay consistent.
	"""
	global basepath
	global external_go_basepath
	global runlog
	global vm_running_genome_file
	global gobreeder
	global gosumi
	global gosumi_2013
	global player_program
	global enemy_program
	global referee_program_command
	global two_gtp_command
	global previous_population_file
	global current_population_file
	global previous_population_stats_file
	global history_stats_base

	basepath=_ensure_trailing_sep(new_basepath)
	external_go_basepath=_ensure_trailing_sep(_join_path(basepath, 'external_go'))

	# all output goes here
	runlog=_join_path(basepath, 'runlog.txt')

	# vm parms
	vm_running_genome_file=_join_path(basepath, 'vm_running_genome.py')

	# breeder parms
	# string to invoke the player program (note double quoting)
	gobreeder='"%s %smediator.py -genome_file %sbreeding_genome.py"' % (pythonpath,basepath,basepath)
	gosumi='"java -jar %sgosumi_dks.jar"' % external_go_basepath
	gosumi_2013='"java -jar %sgosumi_2013.jar -timeout 1"' % external_go_basepath
	player_program=gobreeder
	# and for the enemy program
	enemy_program=gosumi_2013

	referee_program_command=_join_path(external_go_basepath, 'ref_v0.1_exe')
	two_gtp_command=_join_path(external_go_basepath, 'gogui-twogtp.exe')

	# file to hold 'previous' generation - just-tested pop is copied to here
	previous_population_file=_join_path(basepath, 'current_population.py_save')

	# this hold the current population being evaluated
	current_population_file=_join_path(basepath, 'current_population.py')

	# stats file name
	previous_population_stats_file=previous_population_file+'_stats'

	# historical runstats for genomes (watch for collisions)
	history_stats_base=_ensure_trailing_sep(_join_path(basepath, 'histories'))


#all output goes here
runlog=_join_path(basepath, 'runlog.txt')

#vm parms
vm_running_genome_file=_join_path(basepath, 'vm_running_genome.py')


#breeder parms
#string to invoke the player program (note double quoting)
pythonpath='c:\\python27amd64\\python.exe'
gobreeder='"%s %smediator.py -genome_file %sbreeding_genome.py"' % (pythonpath,basepath,basepath)
gosumi='"java -jar %sgosumi_dks.jar"' % external_go_basepath
gosumi_2013='"java -jar %sgosumi_2013.jar -timeout 1"' % external_go_basepath
player_program=gobreeder
#and for the enemy program
enemy_program=gosumi_2013#player_program[0:-1]+' -silent"'#
referee_program_command=_join_path(external_go_basepath, 'ref_v0.1_exe')

two_gtp_command=_join_path(external_go_basepath, 'gogui-twogtp.exe')

#board size...
board_size=9  #oh yeah, about this. MUST BE 9 until the near future...

#file to hold 'previous' generation - just-tested pop is copied to here
previous_population_file=_join_path(basepath, 'current_population.py_save')

#this hold the current population being evaluated
current_population_file=_join_path(basepath, 'current_population.py')


#stats file name
previous_population_stats_file=previous_population_file+'_stats'

#entropy!?
rand_max=9  #why 4? why .. used of op_rnd 
#    def opcode_rnd(self):
#        self.reg_RES=int(random.random()*config.rand_max)-(config.rand_max/2)
#        self.set_SGN()

#historical runstats for genomes (watch for collisions)
history_stats_base=_ensure_trailing_sep(_join_path(basepath, 'histories'))
record_stats=False

#(not used yet)
#threads_or_processes  True/threads, False/processes, None/block file IO
threads_or_processes=False

#show cmd breeder executes to play two players against each other
show_cmd=True

graph_move_pc=True
show_board_every_move=True
