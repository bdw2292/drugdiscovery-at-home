import socket
from tqdm import tqdm
import os
from datetime import datetime
import time
import json

class Server():
    def __init__(self,HOST='127.0.0.1',PORT=65432,delaytime=.2,logname='event.log',secretfile='secret.txt',normaldelimter='%',commanddelimiter='$',inputfilenamedelimiter='&',outputfilenamedelimter='^',addresstonumberoftimesconnectingfilename='addresstonumberoftimesconnecting.txt',addresstonumberoffailedpasswordsfilename='addresstonumberoffailedpasswords.txt',blacklistaddressesfilename='blacklistaddresses.txt',passwordattempts=3,queuefilename='queue.txt',jobsinprogressfilename='jobsinprogress.txt',jobidtostarttimefilename='jobidtostarttime.txt',emailtopasswordfilename='emailtopassword.txt',usernametopasswordfilename='usernametopassword.txt'):
        self.HOST=HOST
        self.PORT=PORT
        self.delaytime=delaytime
        self.logname=logname
        self.secretfile=secretfile
        self.normaldelimiter=normaldelimter
        self.commanddelimiter=commanddelimiter
        self.inputfilenamedelimiter=inputfilenamedelimiter
        self.outputfilenamedelimiter=outputfilenamedelimter
        self.logh=open(self.logname,'w')
        self.addresstonumberoftimesconnectingfilename=addresstonumberoftimesconnectingfilename
        self.addresstonumberoftimesconnecting=self.ReadDictionaryFromFileName(self.addresstonumberoftimesconnectingfilename) # only for serverpassword
        self.addresstonumberoffailedpasswordsfilename=addresstonumberoffailedpasswordsfilename
        self.addresstonumberoffailedpasswords=self.ReadDictionaryFromFileName(self.addresstonumberoffailedpasswordsfilename) # only for serverpassword
        self.blacklistaddressesfilename=blacklistaddressesfilename
        self.blacklistaddresses=self.ReadListFromFileName(self.blacklistaddressesfilename)
        self.passwordattempts=passwordattempts # only for serverpassword
        self.queuefilename=queuefilename
        self.queue=self.ReadDictionaryFromFileName(self.queuefilename) # {jobid:[time allowed (hours),[commandstring1,commandstring2,...],[inputfilename1,inputfilename2..],[outputfilename1,outpufilename2,..]]}
        self.jobsinprogressfilename=jobsinprogressfilename
        self.jobsinprogress=self.ReadListFromFileName(self.jobsinprogressfilename)
        self.jobidtostarttimefilename=jobidtostarttimefilename
        self.jobidtostarttime=self.ReadDictionaryFromFileName(self.jobidtostarttimefilename)
        self.emailtopasswordfilename=emailtopasswordfilename
        self.emailtopassword=self.ReadDictionaryFromFileName(self.emailtopasswordfilename)
        self.usernametopasswordfilename=usernametopasswordfilename
        self.usernametopassword=self.ReadDictionaryFromFileName(self.usernametopasswordfilename)


    def ParseObject(self,object,delimter):
        stringlist=object.split(delimter)
        return stringlist

    def WriteToLog(self,logh,msg):
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        print(dt_string+' '+msg)
        logh.write(dt_string+' '+msg+'\n')

    def ReadPassword(self,filename):
        temp=open(filename,'r')
        lines=temp.readlines()
        password=lines[0].replace('\n','').lstrip().rstrip()
        return password

    def SendFile(self,s,filename,delaytime):
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

    def ReceiveFile(self,s,delaytime):
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


    def ConcatenateStrings(self,stringlist,delimiter):
        masterstring=''
        for string in stringlist:
            masterstring+=string+delimiter
        if len(stringlist)!=1:
            masterstring=masterstring[:-1]
        return masterstring

    def ReadListFromFileName(self,filename):
        list=[]
        if os.path.isfile(filename):
            with open(filename, 'r') as filehandle:
                for line in filehandle:
                    current = line[:-1]
                    list.append(current)
        return list

    def WriteListToFileName(self,ls,filename):
        with open(filename, 'w') as filehandle:
            for listitem in ls:
                filehandle.write('%s\n' % listitem)

    def ReadDictionaryFromFileName(self,filename):
        dic={}
        if os.path.isfile(filename):
            dic=json.load(open(filename))
        return dic

    def WriteDictionaryToFileName(self,dic,filename):
        json.dump(dic, open(filename,'w'))

    def Initialize(self,conn,addr):
        for jobid,sublist in self.queue.items():
            if jobid not in self.jobsinprogress:
                pass
            else:
                continue
            os.chdir(jobid)
            timeallowed=sublist[0]
            commandlist=sublist[1]
            inputfilenamelist=sublist[2]
            outputfilenamelist=sublist[3]
            masterstring=self.ConcatenateStrings([jobid,str(timeallowed),self.ConcatenateStrings(commandlist,self.commanddelimiter),self.ConcatenateStrings(inputfilenamelist,self.inputfilenamedelimiter),self.ConcatenateStrings(outputfilenamelist,self.outputfilenamedelimiter)],self.normaldelimiter)
            conn.sendall(masterstring.encode())
            time.sleep(self.delaytime)
            for filename in inputfilenamelist:
                time.sleep(self.delaytime)
                self.SendFile(conn,filename,self.delaytime)
            os.chdir('..')
            self.jobidtostarttime[jobid]=time.time()
            self.WriteToLog(self.logh,'Initializing job on client, jobid= '+str(jobid)+' '+str(addr))
            break

    def Register(self,conn,stringlist):
        accepted=True
        errormsg=''
        email=stringlist[1]
        username=stringlist[2]
        password=stringlist[3]
        validemail=self.CheckValidEmail(email)
        if validemail==True:
            if username in self.usernametopassword.keys() or email in self.emailtopassword.keys():
                accepted=False
                errormsg='Username and email already registered'
            else:
                tempemailtopassword={email:password}
                self.emailtopassword.update(tempemailtopassword)
                tempusernametopassword={username:password}
                self.usernametopassword.update(tempusernametopassword)
        else:
            accepted=False
            errormsg='Invalid email address'

        accepted=str(accepted)
        masterstring=self.ConcatenateStrings([accepted,errormsg],self.normaldelimiter)
        conn.sendall(masterstring.encode())

    def Login(self,conn,stringlist):
        accepted=True
        errormsg=''
        username=stringlist[1]
        password=stringlist[2]
        if username not in self.usernametopassword.keys() and username not in self.emailtopassword.keys():
            accepted=False
            errormsg='Username or email account does not exist'

        accepted=str(accepted)
        masterstring=self.ConcatenateStrings([accepted,errormsg],self.normaldelimiter)
        conn.sendall(masterstring.encode())


    def CheckValidEmail(self,email):
        valid=True
        if '@' not in email:
            valid=False
        else:
            split=email.split('@')
            secondpart=split[1]
            if '.' not in secondpart:
                valid=False
        return valid

    def Finalize(self,conn,stringlist):
        jobid=stringlist[1]
        if jobid not in self.jobsinprogress: # then they didnt finish in time
            self.WriteToLog(self.logh,'Job didnt finish in time cannot accept files, jobid= '+str(jobid)+' '+str(addr))

        if not os.path.isdir(jobid):
            os.mkdir(jobid)
        os.chdir(jobid)
        residual=' '.join(stringlist[2:])
        outputfilenamelist=self.ParseObject(residual,self.outputfilenamedelimter)
        outputfilenamelist=outputfilenamelist[:-1]
        outputfilenamelist=[item.lstrip().rstrip() for item in outputfilenamelist]
        time.sleep(self.delaytime)
        for filename in outputfilenamelist:
            time.sleep(self.delaytime)
            self.ReceiveFile(conn,self.delaytime)
        os.chdir('..')
        del self.queue[jobid]
        del self.jobidtostarttime[jobid]
        self.jobsinprogress.remove(jobid)
        self.WriteToLog(self.logh,'Completed job, jobid= '+str(jobid)+' '+str(addr))

    def Submit(self,conn,stringlist,addr):
        password=self.ReadPassword(self.secretfile)
        passphrase=stringlist[1]
        if password==passphrase:
            jobid=stringlist[2]
            timeallowed=float(stringlist[3])
            string=' '.join(stringlist[4:])
            residual=self.ParseObject(string,self.commanddelimiter)
            commandlist=residual[:-1]
            residual=residual[-1]
            residual=self.ParseObject(residual,self.inputfilenamedelimiter)
            inputfilenamelist=residual[:-1]
            inputfilenamelist=[item.lstrip().rstrip() for item in inputfilenamelist]
            residual=residual[-1]
            outputfilenamelist=self.ParseObject(residual,self.outputfilenamedelimiter)
            outputfilenamelist=outputfilenamelist[:-1]
            outputfilenamelist=[item.lstrip().rstrip() for item in outputfilenamelist]
            ls=[timeallowed,commandlist,inputfilenamelist,outputfilenamelist]
            if not os.path.isdir(jobid):
                os.mkdir(jobid)
            os.chdir(jobid)
            time.sleep(self.delaytime)
            for filename in inputfilenamelist:
                time.sleep(self.delaytime)
                self.ReceiveFile(conn,self.delaytime)
            os.chdir('..')
            self.queue[jobid]=ls
            self.WriteToLog(self.logh,'Recived job submission jobid= '+str(jobid)+' '+str(addr))
        else:
            self.WriteToLog(self.logh,'Failed password attempt '+str(addr))
            if addr not in self.addresstonumberoffailedpasswords.keys():
                self.addresstonumberoffailedpasswords[addr]=0
            self.addresstonumberoffailedpasswords[addr]+=1
            if self.addresstonumberoffailedpasswords[addr]>=self.passwordattempts:
                self.WriteToLog(self.logh,'Blacklisting '+str(addr))
                self.blacklistaddresses.append(addr)

    def StartServer(self):
        while True:
            currenttime=time.time()
            for jobid,starttime in self.jobidtostarttime.items():
                timepassed=(currenttime-starttime)*0.000277778
                sublist=self.queue[jobid]
                allowedtime=sublist[0]
                if timepassed>=allowedtime:
                    if jobid in self.jobsinprogress.keys():
                        self.jobsinprogress.remove(jobid)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.HOST, self.PORT))
                s.listen()
                conn, addr = s.accept()
                if addr in self.blacklistaddresses:
                    continue
                with conn:
                    self.WriteToLog(self.logh,'Connected by '+str(addr))
                    if addr not in self.addresstonumberoftimesconnecting.keys():
                        self.addresstonumberoftimesconnecting[addr]=1
                    else:
                        self.addresstonumberoftimesconnecting[addr]+=1
                    string=conn.recv(1024).decode()
                    stringlist=self.ParseObject(string,self.normaldelimiter)
                    signal=stringlist[0]
                    if signal=='INITIALIZE':
                        self.Initialize(conn,addr)
                    elif signal=='REGISTER':
                        self.Register(conn,stringlist)
                    elif signal=='LOGIN':
                        self.Login(conn,stringlist)
                    elif signal=='FINALIZE':
                        self.Finalize(conn,stringlist)
                    elif signal=='SUBMIT':
                        self.Submit(conn,stringlist,addr)
                    else:
                        if addr not in self.blacklistaddresses:
                            self.WriteToLog(self.logh,'Wrong initial signal blacklisting address'+str(addr)+' signal was '+signal)
                            self.blacklistaddresses.append(addr)

if __name__ == '__main__':
    serverobject=Server()
    serverobject.StartServer()
