'''
Created on 17 Jul 2015

@author: matt
'''
'''implements background file ops'''



import threading
import config
import os


from multiprocessing import pool

from config import threads_or_processes



logging=False
def log(msg):
    if logging:
        if os.path.exists(config.runlog):
            mode='a'
        else:
            mode='w'
        logfile=open(config.runlog,mode)
        logfile.write('threaded_files: '+msg+'\n')
        logfile.close()


def threaded_writelines(data,filehandle):
    threading.Thread(target=_threaded_writelines(data,filehandle)).start()
    log('write thread create')
    
def _threaded_writelines(data,filehandle):
    if data[0]:
        if not data[0][-1]=='\n':#if the first element doesnt have '\n' assume they all dont
            data=[ d+'\n' for d in data ]
            #must be a better way
    with filehandle as filehandle:
        filehandle.writelines(data)
        log('write thread fin')
    
    
