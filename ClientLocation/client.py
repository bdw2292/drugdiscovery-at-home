import os
import subprocess
import time
import socket
from tqdm import tqdm

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 65432        # The port used by the server
normaldelimter='%'
commanddelimeter='$'
inputfilenamedelimiter='&'
outputfilenamedelimter='^'
delaytime=.2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
outputlogname='dynamics.log'
outputlog_path=BASE_DIR+'/'+outputlogname
notebookname='screensaver.ipynb'
notebookpath=BASE_DIR+'/'+notebookname
tinkerpath_windows=os.path.join(BASE_DIR, 'bin-windows')
parameterfilename='amoebabio18.txt'



def WindowsSantizePath(path):
    return path.replace('\\','/')


if os.name == 'nt':
    parameterfile_path=tinkerpath_windows+'/'+parameterfilename
    tinker_binpath=tinkerpath_windows+'/'+'bin-windows'+'/'
    outputlog_path=WindowsSantizePath(outputlog_path)


dynamic_binpath=tinker_binpath+'dynamic.exe'
logfilehandle=open(outputlog_path,'w')

def ParseTrajectoryOutput(trajectory_path,xyzfilecount):
    newxyzfilecount=0
    xyzfiles=[]
    xyzfile=[]
    filecounts=[]
    with open(trajectory_path) as infile:
        for line in infile:
            linesplit=line.split()
            if len(linesplit)==1: # then new xyzfile (need to handle case for box conditions on top)
                newxyzfilecount+=1

                if newxyzfilecount>xyzfilecount or xyzfilecount==0:
                    xyzfile=[]
                    totalatomnum=int(linesplit[0])
                    newline=str(totalatomnum)+'\n'
                    xyzfile.append(newline)
                    xyzfile.append('\n')
                    filecounts.append(newxyzfilecount)
            else:
                if newxyzfilecount>xyzfilecount:
                    element=linesplit[1]
                    atomnum=int(linesplit[0])
                    element=SanitizeElement(element)
                    x=linesplit[2]
                    y=linesplit[3]
                    z=linesplit[4]
                    newline=element+' '+x+' '+y+' '+z+'\n'
                    xyzfile.append(newline)
                    if atomnum==totalatomnum:
                        xyzfiles.append(xyzfile)

    return newxyzfilecount

def SanitizeElement(element):
    allupper=True
    for e in element:
        if e.islower():
            allupper=False
    if allupper==True:
        element=element[0]
    return element




def LaunchJupyterNotebook(notebookpath):
    subprocess.Popen('jupyter notebook '+notebookpath)
    return


def SendNGLSignal():
    temp=open('readytoappend.txt','w')
    temp.close()

def ReceiveFile(s,delaytime):
    # receive the file infos
    # receive using client socket, not server socket
    BUFFER_SIZE = 4096
    SEPARATOR = "<SEPARATOR>"
    received = s.recv(BUFFER_SIZE).decode()
    time.sleep(delaytime)
    filename, filesize = received.split(SEPARATOR)

    # remove absolute path if there is
    filename = os.path.basename(filename)
    # convert to integer
    filesize = int(filesize)
    # start receiving the file from the socket
    # and writing to the file stream
    progress = tqdm(range(filesize), f"Receiving {filename}", unit="B", unit_scale=True, unit_divisor=1024)
    with open(filename, "wb") as f:
       for _ in progress:
            # read 1024 bytes from the socket (receive)
            bytes_read = s.recv(BUFFER_SIZE)
            if not bytes_read:
               # nothing is received
               # file transmitting is done
               break
            # write to the file the bytes we just received
            f.write(bytes_read)
            # update the progress bar
            progress.update(len(bytes_read))


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

def ParseObject(object,delimiter):
    stringlist=object.split(delimiter)
    return stringlist


def ConcatenateStrings(stringlist,delimiter):
    masterstring=''
    for string in stringlist:
        masterstring+=string+delimiter
    if len(stringlist)!=1:
        masterstring=masterstring[:-1]
    return masterstring

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    masterstring=ConcatenateStrings(['INITIALIZE'],normaldelimter)
    print('masterstring',masterstring)
    s.sendall(masterstring.encode())
    object = s.recv(1024).decode()
    stringlist=ParseObject(object,normaldelimter)
    jobid=stringlist[0]
    timeallowed=float(stringlist[1])
    string=' '.join(stringlist[2:])
    residual=ParseObject(string,commanddelimeter)
    commandlist=residual[:-1]
    residual=residual[-1]
    residual=ParseObject(residual,inputfilenamedelimiter)
    inputfilenamelist=residual[:-1]
    inputfilenamelist=[item.lstrip().rstrip() for item in inputfilenamelist]
    residual=residual[-1]
    outputfilenamelist=ParseObject(residual,outputfilenamedelimter)
    outputfilenamelist=outputfilenamelist[:-1]
    outputfilenamelist=[item.lstrip().rstrip() for item in outputfilenamelist]
    time.sleep(delaytime)
    for filename in inputfilenamelist:
        time.sleep(delaytime)
        ReceiveFile(s,delaytime)
    if os.name == 'nt':
        commandlist=[WindowsSantizePath(string) for string in commandlist]



for i in range(len(commandlist)):
    command=commandlist[i]
    print('command',command)
    if 'dynamic' in command:
        if os.name == 'nt':
            command=command.replace('dynamic.exe',dynamic_binpath).replace(parameterfilename,parameterfile_path)
            print('command after',command)
        outputfilename=outputfilenamelist[i]
        p = subprocess.Popen(command, shell=True,stdout=logfilehandle, stderr=logfilehandle)
        count=0
        while not os.path.exists(outputfilename):
            time.sleep(1)
            if count==0:
                print('Waiting for simulation to begin')
            count+=1

        LaunchJupyterNotebook(notebookpath)
        xyzfilecount=0
        while p.poll()==None:
            newxyzfilecount=ParseTrajectoryOutput(outputfilename,xyzfilecount)
            if newxyzfilecount>xyzfilecount and newxyzfilecount!=1:
                SendNGLSignal()
            xyzfilecount=newxyzfilecount
            time.sleep(5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            masterstring=ConcatenateStrings(['FINALIZE',jobid,ConcatenateStrings([outputfilename],outputfilenamedelimter)],normaldelimter)
            s.sendall(masterstring.encode())
            time.sleep(delaytime)
            SendFile(s,outputfilename,delaytime)
            os.remove(outputfilename)
            for filename in inputfilenamelist:
                os.remove(filename)
