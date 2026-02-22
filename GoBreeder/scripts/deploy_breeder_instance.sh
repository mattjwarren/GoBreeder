instance=${1}

#root dir for instances
deploy_base=/home/matth/breeders
# WSL2: basepath is a plain Linux path inside the WSL2 filesystem
breed_exec_base="${deploy_base}/GoBreeder_${instance}/breed/"

target_dir=${deploy_base}/GoBreeder_${instance}

if [ -d ${target_dir} ]
then
	rm -rf ${target_dir}
fi

mkdir -p ${target_dir}

cp -R ${deploy_base}/GoBreeder/* ${target_dir}

#update basepath in config
cat ${target_dir}/breed/config.py | sed -E -e "s!^basepath=.*!basepath=\"${breed_exec_base}\"!g" > ${target_dir}/breed/config.py_sed
mv ${target_dir}/breed/config.py_sed ${target_dir}/breed/config.py

