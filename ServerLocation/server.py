import socket
from tqdm import tqdm
import os
from datetime import datetime
import time


HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432        # Port to listen on (non-privileged ports are > 1023)

delaytime=.2
logname='event.log'
logh=open(logname,'w')
secretfile='secret.txt'
normaldelimter='%'
commanddelimeter='$'
inputfilenamedelimiter='&'
outputfilenamedelimter='^'

def ParseObject(object,delimter):
    stringlist=object.split(delimter)
    return stringlist

def WriteToLog(logh,msg):
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    print(dt_string+' '+msg)
    logh.write(dt_string+' '+msg+'\n')

def ReadPassword(filename):
    temp=open(filename,'r')
    lines=temp.readlines()
    password=lines[0].replace('\n','').lstrip().rstrip()
    return password

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

def ReceiveFile(s,delaytime):
    # receive the file infos
    # receive using client socket, not server socket
    BUFFER_SIZE = 4096
    SEPARATOR = "<SEPARATOR>"
    received = s.recv(BUFFER_SIZE).decode()
    filename, filesize = received.split(SEPARATOR)
    time.sleep(delaytime)

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


def ConcatenateStrings(stringlist,delimiter):
    masterstring=''
    for string in stringlist:
        masterstring+=string+delimiter
    if len(stringlist)!=1:
        masterstring=masterstring[:-1]
    return masterstring


addresstonumberoftimesconnecting={}
addresstonumberoffailedpasswords={}
blacklistaddresses=[]
passwordattempts=3
queue={} # {jobid:[time allowed (hours),[commandstring1,commandstring2,...],[inputfilename1,inputfilename2..],[outputfilename1,outpufilename2,..]]}
jobsinprogress=[]
jobidtostarttime={}

while True:
    currenttime=time.time()
    for jobid,starttime in jobidtostarttime.items():
        timepassed=(currenttime-starttime)*0.000277778
        sublist=queue[jobid]
        allowedtime=sublist[0]
        if timepassed>=allowedtime:
            jobsinprogress.remove(jobid)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        conn, addr = s.accept()
        if addr in blacklistaddresses:
            continue
        with conn:
            WriteToLog(logh,'Connected by '+str(addr))
            if addr not in addresstonumberoftimesconnecting.keys():
                addresstonumberoftimesconnecting[addr]=1
            else:
                addresstonumberoftimesconnecting[addr]+=1
            string=conn.recv(1024).decode()
            stringlist=ParseObject(string,normaldelimter)
            signal=stringlist[0]
            if signal=='INITIALIZE':
                for jobid,sublist in queue.items():
                    if jobid not in jobsinprogress:
                        pass
                    else:
                        continue
                    os.chdir(jobid)
                    timeallowed=sublist[0]
                    commandlist=sublist[1]
                    inputfilenamelist=sublist[2]
                    outputfilenamelist=sublist[3]
                    masterstring=ConcatenateStrings([jobid,str(timeallowed),ConcatenateStrings(commandlist,commanddelimeter),ConcatenateStrings(inputfilenamelist,inputfilenamedelimiter),ConcatenateStrings(outputfilenamelist,outputfilenamedelimter)],normaldelimter)
                    conn.sendall(masterstring.encode())
                    time.sleep(delaytime)
                    for filename in inputfilenamelist:
                        time.sleep(delaytime)
                        SendFile(conn,filename,delaytime)
                    os.chdir('..')
                    jobidtostarttime[jobid]=time.time()
                    WriteToLog(logh,'Initializing job on client, jobid= '+str(jobid)+' '+str(addr))
                    break
            elif signal=='FINALIZE':
                jobid=stringlist[1]
                if jobid not in jobsinprogress: # then they didnt finish in time
                    WriteToLog(logh,'Job didnt finish in time cannot accept files, jobid= '+str(jobid)+' '+str(addr))
                    continue
                if not os.path.isdir(jobid):
                    os.mkdir(jobid)
                os.chdir(jobid)
                residual=' '.join(stringlist[2:])
                outputfilenamelist=ParseObject(residual,outputfilenamedelimter)
                outputfilenamelist=outputfilenamelist[:-1]
                outputfilenamelist=[item.lstrip().rstrip() for item in outputfilenamelist]
                time.sleep(delaytime)
                for filename in outputfilenamelist:
                    time.sleep(delaytime)
                    ReceiveFile(conn,delaytime)
                os.chdir('..')
                del queue[jobid]
                del jobidtostarttime[jobid]
                jobsinprogress.remove(jobid)
                WriteToLog(logh,'Completed job, jobid= '+str(jobid)+' '+str(addr))
            elif signal=='SUBMIT':
                password=ReadPassword(secretfile)
                passphrase=stringlist[1]
                if password==passphrase:
                    jobid=stringlist[2]
                    timeallowed=float(stringlist[3])
                    string=' '.join(stringlist[4:])
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
                    ls=[timeallowed,commandlist,inputfilenamelist,outputfilenamelist]
                    if not os.path.isdir(jobid):
                        os.mkdir(jobid)
                    os.chdir(jobid)
                    time.sleep(delaytime)
                    for filename in inputfilenamelist:
                        time.sleep(delaytime)
                        ReceiveFile(conn,delaytime)
                    os.chdir('..')
                    queue[jobid]=ls
                    WriteToLog(logh,'Recived job submission jobid= '+str(jobid)+' '+str(addr))
                else:
                    WriteToLog(logh,'Failed password attempt '+str(addr))
                    if addr not in addresstonumberoffailedpasswords.keys():
                        addresstonumberoffailedpasswords[addr]=0
                    addresstonumberoffailedpasswords[addr]+=1
                    if addresstonumberoffailedpasswords[addr]>=passwordattempts:
                        WriteToLog(logh,'Blacklisting '+str(addr))
                        blacklistaddresses.append(addr)
            else:
                if addr not in blacklistaddresses:
                    WriteToLog(logh,'Wrong initial signal blacklisting address'+str(addr)+' signal was '+signal)
                    blacklistaddresses.append(addr)
