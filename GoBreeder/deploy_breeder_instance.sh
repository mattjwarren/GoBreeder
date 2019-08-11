instance=${1}

#root dir for instances
deploy_base=/home/matth/breeders
#exec base in the context of the system used to run a breed
breed_exec_base="C:\\\\\\\\cygwin64\\\\\\\\home\\\\\\\\matth\\\\\\\\breeders\\\\\\\\GoBreeder_${1}\\\\\\\\breed\\\\\\\\"

target_dir=${deploy_base}/GoBreeder_${instance}

if [ -d ${target_dir} ]
then
	rm -rf ${target_dir}
fi

mkdir -p ${target_dir}

cp -R ${deploy_base}/GoBreeder/* ${target_dir}

#update basepath in config
cat ${target_dir}/breed/config.py | sed -e "s!basepath=.*!basepath=\"${breed_exec_base}\"!g" > ${target_dir}/breed/config.py_sed
mv ${target_dir}/breed/config.py_sed ${target_dir}/breed/config.py

