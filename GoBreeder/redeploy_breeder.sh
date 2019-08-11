instance=${1}

echo clearing save cache
rm -rf saved_histories
mkdir saved_histories
rm -rf saved_config
mkdir saved_config
rm -rf saved_current
mkdir saved_current

echo saving current instance state
mv GoBreeder_${instance}/breed/histories/* saved__histories/
mv GoBreeder_${instance}/breed/config.py saved_config/
mv GoBreeder_${instance}/breed/current_* saved_current/

echo redeploying
./deploy_breeder_instance.sh ${instance}

echo restoring saved instance state
mv saved_histories/* GoBreeder_Instance_${instance}/breed/histories/
mv saved_config/config.py GoBreeder_Instance_${instance}/breed/config.py
mv saved_current/current_* GoBreeder_Instance_${instance}/breed/
echo Done.