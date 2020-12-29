import os
import subprocess
import time
import socket
from tqdm import tqdm
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from idle_time import IdleMonitor

class Client():
    def __init__(self,HOST = '127.0.0.1',PORT = 65432,normaldelimter='%',commanddelimeter='$',inputfilenamedelimiter='&',outputfilenamedelimiter='^',delaytime=.2,screensleeptime=1,BASE_DIR = os.path.dirname(os.path.abspath(__file__)),outputlogname='dynamics.log',notebookname='screensaver.ipynb',parameterfilename='amoebabio18.txt',inputfilename='inputparameters.txt',dynamics_only_while_idle=False,animationframerefreshrate=1,terminatedjob=False):
        self.HOST=HOST
        self.PORT=PORT
        self.normaldelimter=normaldelimter
        self.commanddelimeter=commanddelimeter
        self.inputfilenamedelimiter=inputfilenamedelimiter
        self.outputfilenamedelimter=outputfilenamedelimiter
        self.delaytime=delaytime
        self.screensleeptime=screensleeptime
        self.BASE_DIR=BASE_DIR
        self.outputlogname=outputlogname
        self.notebookname=notebookname
        self.parameterfilename=parameterfilename
        self.inputfilename=inputfilename
        self.dynamics_only_while_idle=dynamics_only_while_idle
        self.animationframerefreshrate=animationframerefreshrate
        self.terminatedjob=terminatedjob
        self.outputlog_path=self.BASE_DIR+'/'+self.outputlogname
        self.notebookpath=self.BASE_DIR+'/'+self.notebookname
        self.tinkerpath_windows=os.path.join(self.BASE_DIR, 'bin-windows')
        if os.name == 'nt':
            self.parameterfile_path=self.tinkerpath_windows+'/'+self.parameterfilename
            self.tinker_binpath=self.tinkerpath_windows+'/'+'bin-windows'+'/'
            self.outputlog_path=self.WindowsSantizePath(self.outputlog_path)


        self.dynamic_binpath=self.tinker_binpath+'dynamic.exe'
        self.logfilehandle=open(self.outputlog_path,'w')



    def WindowsSantizePath(self,path):
        return path.replace('\\','/')




    def ParseTrajectoryOutput(self,trajectory_path,xyzfilecount):
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
                        element=self.SanitizeElement(element)
                        x=linesplit[2]
                        y=linesplit[3]
                        z=linesplit[4]
                        newline=element+' '+x+' '+y+' '+z+'\n'
                        xyzfile.append(newline)
                        if atomnum==totalatomnum:
                            xyzfiles.append(xyzfile)

        return newxyzfilecount

    def SanitizeElement(self,element):
        allupper=True
        for e in element:
            if e.islower():
                allupper=False
        if allupper==True:
            element=element[0]
        return element

    def ReceiveFile(self,s,delaytime):
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

    def ParseObject(self,object,delimiter):
        stringlist=object.split(delimiter)
        return stringlist


    def ConcatenateStrings(self,stringlist,delimiter):
        masterstring=''
        for string in stringlist:
            masterstring+=string+delimiter
        if len(stringlist)!=1:
            masterstring=masterstring[:-1]
        return masterstring


    def LaunchJupyterNotebook(self,notebookname,logfilehandle):
        cmd = "jupyter notebook --no-browser --NotebookApp.token='' --NotebookApp.password=''"
        p=subprocess.Popen(cmd,shell=True,stdout=logfilehandle,stderr=logfilehandle)
        time.sleep(5)
        nburl='http://localhost:8888/notebooks/'+notebookname
        return nburl


    def LaunchControlledChromeBrowser(self,nburl):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument('start-maximized')
        chrome_options.add_argument('disable-infobars')
        options = Options()
        options.add_argument("start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        driver = webdriver.Chrome(ChromeDriverManager().install(),chrome_options=options)
        driver.get(nburl)
        main_window = driver.current_window_handle
        return driver,main_window

    def ConvertSecondsToMinutes(self,currenttime):
        return currenttime/60

    def TerminateTinkerDynamics(self,xyzfile_path):
        endpath=xyzfile_path.replace('.xyz','.end')
        temp=open(endpath,'w')
        temp.close()


    def RestartTinkerDynamics(self,command,frames,newxyzfilecount,logfilehandle,writeout_time):
        files=os.listdir()
        for f in files:
            file_name, file_extension = os.path.splitext(f)
            if file_extension=='.end':
                os.remove(endpath)
        newframes=frames-newxyzfilecount
        dynamic_time=newframes*writeout_time # in fs
        dynamic_steps=str(dynamic_time/1) # just remove fs unit
        commandsplit=command.split()
        commandsplit[3]=dynamic_steps
        command=' '.join(commandsplit)
        p = subprocess.Popen(command, shell=True,stdout=logfilehandle, stderr=logfilehandle)
        return p


    def CleanUpTinkerFiles(self):
        files=os.listdir()
        for f in files:
            file_name, file_extension = os.path.splitext(f)
            if file_extension=='.arc' or file_extension=='.dyn' or file_extension=='.key' or file_extension=='.xyz':
                os.remove(f)

    def ReadInputParameters(self):
        if os.path.isfile(os.getcwd()+r'/'+self.inputfilename):
            temp=open(os.getcwd()+r'/'+self.inputfilename,'r')
            results=temp.readlines()
            temp.close()
            for line in results:
                if '#' not in line and line!='\n':
                    if '=' in line:
                        linesplit=line.split('=',1)
                        a=linesplit[1].replace('\n','').rstrip().lstrip()
                        newline=linesplit[0]
                        if a=='None':
                            continue
                    else:
                        newline=line

                    if "dynamics_only_while_idle" in newline:
                        if '=' not in line:
                            self.dynamics_only_while_idle = True
                        else:
                            self.dynamics_only_while_idle=self.GrabBoolValue(a)
                    elif "animationframerefreshrate" in newline:
                        self.animationframerefreshrate=int(a)
                    elif "teamname" in newline:
                        self.teamname=a
                    elif "username" in newline:
                        self.username=a
                    elif "email" in newline:
                        self.email=a
                    elif "userpassword" in newline:
                        self.userpassword=a
                    elif "teampassword" in newline:
                        self.teampassword=a


    def ReceiveJob(self):
        self.CleanUpTinkerFiles()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.HOST, self.PORT))
            masterstring=self.ConcatenateStrings(['INITIALIZE'],self.normaldelimter)
            s.sendall(masterstring.encode())
            object = s.recv(1024).decode()
            stringlist=self.ParseObject(object,self.normaldelimter)
            self.jobid=stringlist[0]
            self.timeallowed=float(stringlist[1])
            string=' '.join(stringlist[2:])
            residual=self.ParseObject(string,self.commanddelimeter)
            self.commandlist=residual[:-1]
            residual=residual[-1]
            residual=self.ParseObject(residual,self.inputfilenamedelimiter)
            self.inputfilenamelist=residual[:-1]
            self.inputfilenamelist=[item.lstrip().rstrip() for item in self.inputfilenamelist]
            residual=residual[-1]
            self.outputfilenamelist=self.ParseObject(residual,self.outputfilenamedelimter)
            self.outputfilenamelist=self.outputfilenamelist[:-1]
            self.outputfilenamelist=[item.lstrip().rstrip() for item in self.outputfilenamelist]
            time.sleep(self.delaytime)
            for filename in self.inputfilenamelist:
                time.sleep(self.delaytime)
                self.ReceiveFile(s,self.delaytime)
            if os.name == 'nt':
                self.commandlist=[self.WindowsSantizePath(string) for string in self.commandlist]



    def ExecuteCommand(self):
        for i in range(len(self.commandlist)):
            command=self.commandlist[i]
            if 'dynamic' in command:
                monitor = IdleMonitor.get_monitor()
                commandsplit=command.split()
                xyzfile_path=commandsplit[1]
                dynamic_steps=int(commandsplit[3])
                time_step=float(commandsplit[4]) #fs
                writeout_time=float(commandsplit[5]) # ps
                writeout_time=writeout_time*1000 #fs
                dynamic_time=dynamic_steps*time_step
                frames=round(dynamic_time/writeout_time)
                if os.name == 'nt':
                    command=command.replace('dynamic.exe',self.dynamic_binpath).replace(self.parameterfilename,self.parameterfile_path)
                outputfilename=self.outputfilenamelist[i]
                p = subprocess.Popen(command, shell=True,stdout=self.logfilehandle, stderr=self.logfilehandle)
                count=0
                while not os.path.exists(outputfilename):
                    time.sleep(1)
                    if count==0:
                        print('Waiting for simulation to begin')
                    count+=1


                xyzfilecount=0
                launched=False
                firstlaunch=True
                framesatlaunch=0
                while xyzfilecount!=frames:
                    newxyzfilecount=self.ParseTrajectoryOutput(outputfilename,xyzfilecount)
                    idletime=self.ConvertSecondsToMinutes(monitor.get_idle_time())
                    if idletime<self.screensleeptime and self.dynamics_only_while_idle==True:
                        self.TerminateTinkerDynamics(xyzfile_path)
                        self.terminatedjob=True
                        if launched==True:
                            driver.quit()
                            launched=False

                    launchready=False
                    if newxyzfilecount>=3 and launched==False:
                        if firstlaunch==True:
                            firstlaunch=False
                            launchready=True
                        else:
                            if idletime>=self.screensleeptime:
                                launchready=True
                        if launchready==True:
                            nburl=self.LaunchJupyterNotebook(self.notebookname,self.logfilehandle)
                            driver,main_window=self.LaunchControlledChromeBrowser(nburl)
                            launched=True
                            framesatlaunch=newxyzfilecount
                            if firstlaunch==False and self.terminatedjob==True: # then need to restart dynamics
                                p=self.RestartTinkerDynamics(command,frames,newxyzfilecount,self.logfilehandle,writeout_time)
                                self.terminatedjob=False

                    if os.path.isfile('killbrowser.txt'):
                        os.remove('killbrowser.txt')
                        driver.quit()
                        launched=False
                    if (newxyzfilecount-framesatlaunch)>self.animationframerefreshrate:
                        if launched==True:
                            driver.quit()
                            launched=False
                        launchready=True



                    xyzfilecount=newxyzfilecount
                    time.sleep(.5)
                self.CompleteJob(outputfilename,self.inputfilenamelist)

    def CompleteJob(self,outputfilename,inputfilenamelist):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.HOST, self.PORT))
            masterstring=self.ConcatenateStrings(['FINALIZE',self.jobid,self.ConcatenateStrings([outputfilename],self.outputfilenamedelimter)],self.normaldelimter)
            s.sendall(masterstring.encode())
            time.sleep(self.delaytime)
            self.SendFile(s,outputfilename,self.delaytime)
            os.remove(outputfilename)
            for filename in inputfilenamelist:
                os.remove(filename)

    def GrabBoolValue(self, value):
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        raise ValueError('Could not convert "{}" into a boolean!'.format(value))

if __name__ == '__main__':
    cliobject=Client()
    cliobject.ReadInputParameters()
    cliobject.ReceiveJob()
    cliobject.ExecuteCommand()
