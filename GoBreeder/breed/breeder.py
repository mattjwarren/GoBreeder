"""Breeder: population management, genome evaluation, and evolutionary breeding."""
import ast
import datetime
import logging
import random
import shlex
import shutil
import subprocess

import config
import data_structures
import vm

random.seed()


class Breeder:
    """Genetic-programming breeder: manages population evaluation and evolution."""

    _logger = logging.getLogger(__name__)

    def __init__(self, population_size=1000, population_file=None):
        """
        Constructor
        """
        self.population = list()
        self.genome_stats = dict()
        self.current_simulation_member = 0
        self.population_max = population_size
        self.population_file = population_file
        self.switch_players = False
        self.generation = 0
        self.logging = True
        self.initialise_population(population_size=population_size)
        self.vm = vm.GoVM()

    def initialise_population(self, population_size=1000):
        # Initial seeding of entirely random population
        self.log("breeder Initialising population\n")
        if self.population_file:
            self.log(f"breeder using population file {self.population_file}\n")
            infile = open(self.population_file)
            ctr = 1
            for genome_repr in (line for line in infile if line != ""):
                if "<<<>>>" in genome_repr:
                    # entry is from a stats_save file so plit the stats off the end
                    genome_repr = genome_repr.split("<<<>>>")[0]
                    # may have been grep/culled so filter out front bit
                    if "save_stats" in genome_repr:
                        genome_repr = genome_repr.split(":")[1]

                try:
                    dna = ast.literal_eval(genome_repr)  # safe alternative to eval()
                    genome = data_structures.GoGenome(dna=dna)
                    self.population.append(genome)
                    self.genome_stats[self.population[-1]] = ""
                    print("Done ressurrect of genome #", ctr)
                    ctr += 1
                except (SyntaxError, ValueError):
                    print("Genome FAILED to resurrect #", ctr)
        else:
            self.log("breeder using genome genesis\n")
            for _n in range(0, population_size):
                new_genome = data_structures.GoGenome()
                self.population.append(new_genome)
                self.genome_stats[self.population[-1]] = ""
        self.current_simulation_member = 0
        self.population_max = len(self.population)
        self.log("pop size is %d\n" % len(self.population))
        # write
        self.log("\t.. Fin ..\n")

    def simulate_gtp_game(
        self, player="black", player_program=config.player_program, enemy_program=config.enemy_program
    ):
        enemy_player = "black" if player == "white" else "white"
        # Put genome to test into genome_test file
        # get command for program to test against
        self.log("Simulating GTP game for breeding\n")
        # create batch fie, run that?
        if self.switch_players:
            n = enemy_player
            enemy_player = player
            player = n
            self.switch_players = False
        else:
            self.switch_players = True
        self.log(f"\tI AM PLAYER {player}\n")
        genome_to_run = self.population[self.current_simulation_member]
        breeding_file = open("breeding_genome.py", "w")
        breeding_file.write(repr(genome_to_run.dna) + "\n")
        breeding_file.close()

        cmdstr = "%s -%s %s -%s %s -size %d -referee %s -auto -verbose" % (
            config.two_gtp_command,
            player,
            player_program,
            enemy_player,
            enemy_program,
            config.board_size,
            config.referee_program_command,
        )
        if config.show_cmd:
            self.log("CMDSTRING:" + cmdstr)
        # Use shlex.split to avoid shell=True with unvalidated config paths.
        args = shlex.split(cmdstr)
        self._logger.debug("BREEDER: subprocess args: %s", args)
        game_process = subprocess.Popen(
            args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        sout, serr = game_process.communicate()
        returncode = game_process.returncode

        self._logger.debug("BREEDER: subprocess returncode: %d", returncode)

        # Count genmove calls (each pair = one full move from each side).
        all_lines = sout.split("\n") + serr.split("\n")
        moves = sum(1 for ln in all_lines if "genmove" in ln) // 2

        # Extract the referee's final_score response.
        # In -verbose mode gogui-twogtp writes lines like "R<< = B+R" to stderr.
        result_str = "?"  # unknown
        after_final_score = False
        for ln in serr.split("\n"):
            if "final_score" in ln and ">>" in ln:
                after_final_score = True
                continue
            if after_final_score and "R<< =" in ln:
                parts = ln.split("R<< =", 1)
                candidate = parts[1].strip() if len(parts) > 1 else ""
                if candidate:
                    result_str = candidate
                after_final_score = False

        # Determine win from result string (e.g. "B+R", "W+3.5").
        # The result_str starts with 'B' for Black win, 'W' for White win.
        won = False
        if result_str != "?":
            won = result_str.upper().startswith(player[0].upper())
        else:
            # Fallback: scan for old-style "has won" line.
            for ln in all_lines:
                if "has won" in ln:
                    tokens = ln.split()
                    if len(tokens) >= 3 and tokens[-3].lower() == player.lower():
                        won = True

        # Extract the final board state rendered by the child process in its quit handler.
        # Child calls go_eng.render_board() unconditionally on receiving 'quit'; each row
        # is logged as "ENGINE: \t<row>" and goes to child's stderr (captured in serr here).
        board_rows = []
        for ln in serr.split("\n"):
            if "ENGINE:" not in ln:
                continue
            idx = ln.find("ENGINE:")
            msg = ln[idx + 7:]  # slice past "ENGINE:"
            if msg.startswith(" "):
                msg = msg[1:]  # strip the single space from "ENGINE: <msg>"
            if msg.startswith("\t"):
                board_rows.append(msg.strip())

        # Log a clear per-game summary.
        genome_hash = str(genome_to_run)
        if board_rows:
            board_display = "\n".join(f"  {row}" for row in board_rows)
            self._logger.debug(
                "BREEDER: --- FINAL BOARD (player=%s) ---\n%s\n---",
                player, board_display,
            )
        else:
            self._logger.debug("BREEDER: (no board state found in child output)")
        self._logger.debug(
            "BREEDER: --- GAME RESULT --- player=%s result=%s moves=%d i_win=%s genome=%s",
            player, result_str, moves, won, genome_hash,
        )
        self.log(f"\tevaluation: moves made={moves} result={result_str} i_win {won}\n")

        return {"moves_made": moves, "i_win": won, "result": result_str}

    def log(self, msg: str) -> None:
        """Forward to Python logger at DEBUG level."""
        if self.logging:
            Breeder._logger.debug("BREEDER: %s", msg.rstrip())

    #'gogui-twogtp.exe -white "python ./mediator.py -genome_file ./champion_genome.py" -black "java -jar gosumi_dks.jar" -size 9 -referee ref_v0.1_exe'

    def simulate_move(self, board=None, player="black"):  # ,finished_game_fitness_data=None):

        move = self.vm.get_move(board=board, player=player, program=self.population[self.current_simulation_member])

        return move

    def end_of_game(self, game_stats=dict()):
        current_genome = self.population[self.current_simulation_member]
        self.log("game ended for genome:")
        self.log(f"{current_genome}")
        self.log("\tpop max=%d" % self.population_max)
        self.log("\tcurrent genome=%d" % self.current_simulation_member)
        self.genome_stats[current_genome] = game_stats

        # greater number of of moves is important; unless, you win, then the less moves the better

        self.current_simulation_member += 1
        max_pieces = 0
        if self.current_simulation_member > len(self.population) - 1:  # ?-1
            self.log("\tGeneration Assessed, breed new generation.")
            self.population = self.breed()
            self.current_simulation_member = 0
            self.vm = vm.GoVM()

        current_genome = self.population[self.current_simulation_member]

        return {"max_pieces": max_pieces}

    def breed(self):
        # go through pop, assigning fitness. pick top ?% to breed
        self.generation += 1
        self.log("\tbreeding generation %d..." % self.generation)
        max_moves_made = max([self.genome_stats[genome]["moves_made"] for genome in self.population])
        min_moves_made = min([self.genome_stats[genome]["moves_made"] for genome in self.population])
        self.log("\tmin_moves_made %d" % min_moves_made)
        self.log("\tmax_moves_made %d" % max_moves_made)
        self.log("\tcalculating fitness")
        pop_fitness = {}
        min_pop_fit = 99999999
        max_pop_fit = 0
        for genome in self.population:
            genome_moves = self.genome_stats[genome]["moves_made"]
            genome_won = self.genome_stats[genome]["i_win"]
            if not genome_won:
                fitness = genome_moves
                self.log("\tWe have a LOOSER! - fitness = %i\n" % fitness)

            else:
                # Winner fitness: fewer moves = better, but any winner beats any loser.
                # max_moves_on_9x9 ≈ 45; offset = max_moves_on_9x9 + 1 = 46 so
                # worst winner (fitness ~= 46+1 = 47) > best loser (fitness = 45).
                max_moves = config.board_size * config.board_size // 2
                winner_offset = max_moves + 1
                fitness = (max_moves - genome_moves) + winner_offset
                self.log("\t *** We have a WINNER! *** - fitness = %i\n\t\t%s" % (fitness, genome))
            pop_fitness[genome] = fitness
            if fitness < min_pop_fit:
                min_pop_fit = fitness
            if fitness > max_pop_fit:
                max_pop_fit = fitness

        date_time = datetime.datetime.now()
        self.log(f"{date_time} // min_pop_fit,max_pop_fit={min_pop_fit:f},{max_pop_fit:f}")

        threshold_fitness = min_pop_fit + ((max_pop_fit - min_pop_fit) * 0.5)  # threshold_magic

        self.log(f"\tthreshold fitness={threshold_fitness:f}")
        seed_pop = [genome for genome in self.population if pop_fitness[genome] >= threshold_fitness]
        self.log("\tLEN seed pop is %d of %d" % (len(seed_pop), len(self.population)))
        self.population_max = len(seed_pop) * 2

        # 2016 is this rught? max pop and max seed should be msit mutation? ...????
        mutation_rate = (7.0 / float(self.population_max)) * float(
            len(seed_pop)
        )  # 1% = total change in 100 generaion. we want that more like .. 1000
        self.log(f"\tMutation rate = {mutation_rate:f} %")
        new_pop = seed_pop

        mutations = 0
        while len(new_pop) < self.population_max:
            for lucky_genome in seed_pop:
                # crossover
                # beautiful !! + Ugly!   people
                # we breed a succesful member with anyone frm the pop. Hmm....
                other_genome = random.choice(self.population)

                min_len = min([len(other_genome), len(lucky_genome)])
                crossover_point = random.randint(0, min_len - 1)

                new_dna = lucky_genome[0:crossover_point] + other_genome[crossover_point:]

                new_genome = data_structures.GoGenome(dna=new_dna)
                for idx in range(0, len(new_genome)):
                    if random.random() * 100.0 <= mutation_rate:
                        new_genome.mutate(idx)
                        mutations += 1
                new_pop.append(new_genome)

                # because length divs can be variable?
                if not len(new_pop) < self.population_max:
                    break
        self.log("Total breeding mutations=" + str(mutations))
        # Save the old, write the new
        self.log("\n\nWriting population info...")
        sfn = config.previous_population_file
        fn = config.current_population_file
        try:
            shutil.copyfile(fn, sfn)
        except Exception as exc:
            self.log(f"ERROR: Could not copy current_population_file.py: {exc}")

        # write the stats file for the previous population,
        # and pare out any not in population
        stats_filename = config.previous_population_stats_file
        stats_file = open(stats_filename, "w")
        for genome in list(self.genome_stats.keys()):
            if genome in self.population:  # if genome was in population tested, then do stats
                stats_file.write(
                    repr(genome.dna)
                    + "<<<>>>"
                    + repr(self.genome_stats[genome])
                    + "<<<>>>"
                    + str(pop_fitness[genome])
                    + "\n"
                )
            if genome not in new_pop:  # if genome is not in new pop then kill its info
                del self.genome_stats[genome]
        stats_file.close()

        gfile = open(fn, "w")
        for genome in new_pop:
            gfile.write(repr(genome.dna) + "\n")
        gfile.close()

        self.log("\tDone writing.")

        return new_pop
