import os
import socket
from tqdm import tqdm
import time

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432        # Port to listen on (non-privileged ports are > 1023)

delaytime=.2
secretfile='secret.txt'
normaldelimter='%'
commanddelimeter='$'
inputfilenamedelimiter='&'
outputfilenamedelimter='^'

xyzfilename='initialpdb.xyz'
dynamic_steps='1000'
time_step='1' # fs
writeout_time='.1' # ps
ensemble='2'
temperature='298'


parameterfilename='amoebabio18.txt'
outputname=xyzfilename.replace('.xyz','.arc')


def WindowsSantizePath(path):
    return path.replace('\\','/')

def ReadPassword(filename):
    temp=open(filename,'r')
    lines=temp.readlines()
    password=lines[0].replace('\n','').lstrip().rstrip()
    return password

def ConcatenateStrings(stringlist,delimiter):
    masterstring=''
    for string in stringlist:
        masterstring+=string+delimiter
    if len(stringlist)!=1:
        masterstring=masterstring[:-1]
    return masterstring

def SendFile(s,filename,delaytime):
    # get the file size
    filesize = os.path.getsize(filename)
    SEPARATOR = "<SEPARATOR>"
    BUFFER_SIZE = 4096 # send 4096 bytes each time step
    # start sending the file
    # send the filename and filesize
    s.send(f"{filename}{SEPARATOR}{filesize}".encode())
    time.sleep(delaytime)
    progress = tqdm(range(filesize), f"Sending {filename}", unit="B", unit_scale=True, unit_divisor=1024)
    with open(filename, "rb") as f:
        for _ in progress:
            # read the bytes from the file
            bytes_read = f.read(BUFFER_SIZE)
            if not bytes_read:
                # file transmitting is done
                break
            # we use sendall to assure transimission in
            # busy networks
            s.sendall(bytes_read)
            # update the progress bar
            progress.update(len(bytes_read))

dynamic_binpath='dynamic.exe'
xyzfile_path=xyzfilename
parameterfile_path=parameterfilename

def DynamicCommand(dynamic_binpath,xyzfile_path,parameterfile_path,dynamic_steps,time_step,writeout_time,ensemble,temperature):
    return dynamic_binpath+' '+xyzfile_path+' '+parameterfile_path+' '+dynamic_steps+' '+time_step+' '+writeout_time+' '+ensemble+' '+temperature

dynamic_command=DynamicCommand(dynamic_binpath,xyzfile_path,parameterfile_path,dynamic_steps,time_step,writeout_time,ensemble,temperature)
jobid='random-test'
password=ReadPassword(secretfile)
timeallowed=.5 # hours


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    masterstring=ConcatenateStrings(['SUBMIT',password,jobid,str(timeallowed),ConcatenateStrings([dynamic_command],commanddelimeter),ConcatenateStrings([xyzfilename],inputfilenamedelimiter),ConcatenateStrings([outputname],outputfilenamedelimter)],normaldelimter)
    print('masterstring',masterstring,flush=True)
    s.sendall(masterstring.encode())
    time.sleep(delaytime)
    SendFile(s,xyzfilename,delaytime)
