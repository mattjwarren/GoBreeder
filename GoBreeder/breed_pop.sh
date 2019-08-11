cd GoBreeder_${1}/breed
rm runlog.txt
python.exe mediator.py -gtp_breed -genome_file current_population.py &
sleep 3
tail -f runlog.txt
