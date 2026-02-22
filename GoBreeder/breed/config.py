"""
Created on 14 Sep 2013

@author: GB108544
"""

import os
import shutil


def _choose_sep(path):
    if "/" in path and "\\" not in path:
        return "/"
    if "\\" in path and "/" not in path:
        return "\\"
    return os.sep


def _ensure_trailing_sep(path):
    sep = _choose_sep(path)
    if not path.endswith(sep):
        return path + sep
    return path


def _join_path(base, *parts):
    """Join using the separator style already present in base."""
    sep = _choose_sep(base)
    out = base.rstrip("/\\")
    for part in parts:
        out = out + sep + str(part).strip("/\\")
    return out


# basepath: absolute path to this breed/ directory on the WSL2 Linux filesystem.
# Auto-detected from __file__ so the default is always correct after a plain
# 'git clone' without needing deploy-script sed rewrites.
basepath = _ensure_trailing_sep(os.path.dirname(os.path.abspath(__file__)))

# Java artefacts (gosumi JARs) – invoked via Linux 'java' by gogui-twogtp (Linux).
java_basepath = _ensure_trailing_sep(_join_path(basepath, "java"))

# Absolute path to java binary. Must be absolute so gogui-twogtp.jar (which
# spawns subprocesses via Java ProcessBuilder and resolves relative paths from
# its cwd=breed/) does not accidentally try to execute the breed/java/ directory.
_java_bin = shutil.which("java") or "java"
if _java_bin == "java":
    import warnings
    warnings.warn("'java' not found on PATH; gosumi commands may fail", RuntimeWarning)


def set_basepath(new_basepath):
    """Update basepath and recompute derived paths.

    NOTE: Some callers mutate config.basepath at runtime (e.g. mediator.py).
    Derived values (paths/command strings) must be recomputed to stay consistent.
    """
    global basepath
    global java_basepath
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

    basepath = _ensure_trailing_sep(new_basepath)
    java_basepath = _ensure_trailing_sep(_join_path(basepath, "java"))

    # all output goes here
    runlog = _join_path(basepath, "runlog.txt")

    # vm parms
    vm_running_genome_file = _join_path(basepath, "vm_running_genome.py")

    # breeder parms
    # string to invoke the player program (note double quoting)
    gobreeder = '"' + pythonpath + " " + basepath + "mediator.py -genome_file " + basepath + 'breeding_genome.py"'
    # gosumi JARs are invoked by Linux gogui-twogtp as a Linux subprocess,
    # so plain Linux paths and Linux java are correct here.
    # Use absolute java path so gogui-twogtp.jar's ProcessBuilder doesn't
    # resolve 'java' relative to cwd and hit the breed/java/ directory.
    _java_bin = shutil.which("java") or "java"
    gosumi = '"' + _java_bin + ' -jar ' + java_basepath + 'gosumi_dks.jar"'
    gosumi_2013 = '"' + _java_bin + ' -jar ' + java_basepath + 'gosumi_2013.jar -timeout 1"'
    player_program = gobreeder
    # and for the enemy program
    enemy_program = gosumi_2013

    # ref_v0.1_exe is a Linux binary in breed/ (runs natively under WSL2)
    referee_program_command = _join_path(basepath, "ref_v0.1_exe")
    # Bundled Linux gogui-twogtp script from gogui-v1.6.0-bin (sibling of breed/).
    # Uses Linux java to run the JAR – no Windows interop needed.
    two_gtp_command = os.path.normpath(
        os.path.join(basepath, "..", "gogui-v1.6.0-bin", "gogui", "bin", "gogui-twogtp")
    )

    # file to hold 'previous' generation - just-tested pop is copied to here
    previous_population_file = _join_path(basepath, "current_population.py_save")

    # this hold the current population being evaluated
    current_population_file = _join_path(basepath, "current_population.py")

    # stats file name
    previous_population_stats_file = previous_population_file + "_stats"

    # historical runstats for genomes (watch for collisions)
    history_stats_base = _ensure_trailing_sep(_join_path(basepath, "histories"))


# all output goes here
runlog = _join_path(basepath, "runlog.txt")

# vm parms
vm_running_genome_file = _join_path(basepath, "vm_running_genome.py")


# breeder parms
# string to invoke the player program (note double quoting)
# Use uv to run python so the project venv is always active.
pythonpath = "uv run python3"
gobreeder = '"' + pythonpath + " " + basepath + "mediator.py -genome_file " + basepath + 'breeding_genome.py"'
# gosumi JARs are invoked by Linux gogui-twogtp as a Linux subprocess,
# so plain Linux paths and Linux java are correct here.
# Use absolute java path so gogui-twogtp.jar's ProcessBuilder doesn't
# resolve 'java' relative to cwd and hit the breed/java/ directory.
gosumi = '"' + _java_bin + ' -jar ' + java_basepath + 'gosumi_dks.jar"'
gosumi_2013 = '"' + _java_bin + ' -jar ' + java_basepath + 'gosumi_2013.jar -timeout 1"'
player_program = gobreeder
# and for the enemy program
enemy_program = gosumi_2013
# ref_v0.1_exe is a Linux binary in breed/ (runs natively under WSL2)
referee_program_command = _join_path(basepath, "ref_v0.1_exe")
# Bundled Linux gogui-twogtp script from gogui-v1.6.0-bin (sibling of breed/).
# Uses Linux java to run the JAR – no Windows interop needed.
two_gtp_command = os.path.normpath(
    os.path.join(basepath, "..", "gogui-v1.6.0-bin", "gogui", "bin", "gogui-twogtp")
)

# board size...
board_size = 9  # oh yeah, about this. MUST BE 9 until the near future...

# file to hold 'previous' generation - just-tested pop is copied to here
previous_population_file = _join_path(basepath, "current_population.py_save")

# this hold the current population being evaluated
current_population_file = _join_path(basepath, "current_population.py")


# stats file name
previous_population_stats_file = previous_population_file + "_stats"

# entropy!?
rand_max = 9  # why 4? why .. used of op_rnd
#    def opcode_rnd(self):
#        self.reg_RES=int(random.random()*config.rand_max)-(config.rand_max/2)
#        self.set_SGN()

# historical runstats for genomes (watch for collisions)
history_stats_base = _ensure_trailing_sep(_join_path(basepath, "histories"))
record_stats = False

# (not used yet)
# threads_or_processes  True/threads, False/processes, None/block file IO
threads_or_processes = False

# show cmd breeder executes to play two players against each other
show_cmd = True

graph_move_pc = True
show_board_every_move = True
