cd GoBreeder_${1}/breed
rm -f runlog.txt
python3 mediator.py -gtp_breed -genome_file current_population.py &
sleep 3
tail -f runlog.txt
