import os
import subprocess
import time
import socket
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from idle_time import IdleMonitor
from PyQt5 import QtWidgets, QtCore
import sys
from datetime import datetime
from tqdm import tqdm
from PyQt5.QtCore import QObject, QThread, pyqtSignal

class Client():
    def __init__(self,HOST = '127.0.0.1',PORT = 65432,normaldelimter='%',commanddelimeter='$',inputfilenamedelimiter='&',outputfilenamedelimiter='^',delaytime=.2):
        self.HOST=HOST
        self.PORT=PORT
        self.normaldelimter=normaldelimter
        self.commanddelimeter=commanddelimeter
        self.inputfilenamedelimiter=inputfilenamedelimiter
        self.outputfilenamedelimter=outputfilenamedelimiter
        self.delaytime=delaytime


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



    def CompleteJob(self,outputfilenamelist,inputfilenamelist):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.HOST, self.PORT))
            masterstring=self.ConcatenateStrings(['FINALIZE',self.jobid,self.ConcatenateStrings(outputfilenamelist,self.outputfilenamedelimter)],self.normaldelimter)
            s.sendall(masterstring.encode())
            time.sleep(self.delaytime)
            self.SendFile(s,outputfilename,self.delaytime)
            os.remove(outputfilename)
            for filename in inputfilenamelist:
                os.remove(filename)

    def Register(self,email,username,password):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.HOST, self.PORT))
            masterstring=self.ConcatenateStrings(['REGISTER',email,username,password],self.normaldelimter)
            s.sendall(masterstring.encode())
            object = s.recv(1024).decode()
            stringlist=self.ParseObject(object,self.normaldelimter)
            accepted=stringlist[0]
            if accepted=='False':
                accepted=False
            elif accepted=='True':
                accepted=True

            errormsg=stringlist[1]
        return accepted,errormsg

    def Login(self,username,password):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.HOST, self.PORT))
            masterstring=self.ConcatenateStrings(['LOGIN',username,password],self.normaldelimter)
            s.sendall(masterstring.encode())
            object = s.recv(1024).decode()
            stringlist=self.ParseObject(object,self.normaldelimter)
            accepted=stringlist[0]
            if accepted=='False':
                accepted=False
            elif accepted=='True':
                accepted=True
            errormsg=stringlist[1]

        return accepted,errormsg


    def CleanUpTinkerFiles(self):
        files=os.listdir()
        for f in files:
            file_name, file_extension = os.path.splitext(f)
            if file_extension=='.arc' or file_extension=='.dyn' or file_extension=='.key' or file_extension=='.xyz':
                os.remove(f)

    def WindowsSantizePath(self,path):
        return path.replace('\\','/')

class Worker(QObject):
    status=pyqtSignal(str)
    eta=pyqtSignal(str)
    cpupercent=pyqtSignal(int)
    gpupercent=pyqtSignal(int)
    finished = pyqtSignal()
    def __init__(self,parent=None,screensleeptime=1,BASE_DIR=os.path.dirname(os.path.abspath(__file__)),outputlogname='dynamics.log',notebookname='screensaver.ipynb',parameterfilename='amoebabio18.txt',inputfilename='inputparameters.txt',dynamics_only_while_idle=False,animationframerefreshrate=1,terminatedjob=False,initialframecount=3,pausedynamics=False,status='INACTIVE',username=None,teamname=None,eta=None,cpupercent=0,gpupercent=0,assigned=None,expiration=None,cpudynamics=True,gpudynamics=False,numbercpus=1,numbergpus=1,commandlist=None,outputfilenamelist=None):
        super(Worker, self).__init__(parent)
        self.outputfilenamelist=outputfilenamelist
        self.commandlist=commandlist
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
        self.initialframecount=initialframecount
        if os.name == 'nt':
            self.parameterfile_path=self.tinkerpath_windows+'/'+self.parameterfilename
            self.tinker_binpath=self.tinkerpath_windows+'/'+'bin-windows'+'/'
            self.outputlog_path=self.WindowsSantizePath(self.outputlog_path)

        self.dynamic_binpath=self.tinker_binpath+'dynamic.exe'
        self.logfilehandle=open(self.outputlog_path,'w')
        self.pausedynamics=pausedynamics
        self.numbercpus=numbercpus
        self.numbergpus=numbergpus
        self.cpudynamics=cpudynamics
        self.gpudynamics=gpudynamics


    def ConvertSecondsToMinutes(self,currenttime):
        return currenttime/60

    def ConvertSecondsToHours(self,currenttime):
        return currenttime/(60*60)

    def ConvertTimeToBestUnits(self,currenttime):
        hours=self.ConvertSecondsToHours(currenttime)
        if hours<1:
            time=self.ConvertSecondsToMinutes(currenttime)
            units='minutes'
        else:
            time=hours
            units='hours'
        string=str(time)+' '+units
        return string

    def WindowsSantizePath(self,path):
        return path.replace('\\','/')


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
        self.driver = webdriver.Chrome(ChromeDriverManager().install(),chrome_options=options)
        self.driver.get(nburl)
        main_window = self.driver.current_window_handle


    def TerminateTinkerDynamics(self,xyzfile_path):
        if self.terminatedjob==False:
            endpath=xyzfile_path.replace('.xyz','.end')
            temp=open(endpath,'w')
            temp.close()
            self.terminatedjob=True
            string="Status: %s"%('INACTIVE')
            self.status.emit(string)


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
        self.terminatedjob=False
        string="Status: %s"%('ACTIVE')
        self.status.emit(string)
        return p





    def TerminateTinkerDynamicsAndScreenSaver(self):
        self.TerminateTinkerDynamics(self.xyzfile_path)
        self.TerminateScreenSaver()


    def TerminateScreenSaver(self):
        if self.launched==True:
            self.driver.quit()
            self.launched=False
            self.launchready=True

    def GetIdleTime(self,monitor):
        if os.name == 'nt':
            time=monitor.get_idle_time()
        return time

    def CheckIfReadyForLaunch(self,idletime):
        if self.firstlaunch==True:
            self.firstlaunch=False
            self.launchready=True
        else:
            if idletime>=self.screensleeptime:
                self.launchready=True

    def LaunchJupyterNoteBookInControlledChromeBrowser(self):
        nburl=self.LaunchJupyterNotebook(self.notebookname,self.logfilehandle)
        self.LaunchControlledChromeBrowser(nburl)
        self.launched=True
        self.framesatlaunch=self.newxyzfilecount
        string="Status: %s"%('ACTIVE')
        self.status.emit(string)

    def GetSystemMonitor(self):
        if os.name == 'nt':
            monitor = IdleMonitor.get_monitor()
        return monitor

    def CurrentTinkerDynamicFrame(self,outputfilename):
        return int(float(os.stat(outputfilename).st_size)/self.xyzfile_path_size)


    def ExecuteCommand(self):
        monitor = self.GetSystemMonitor()
        for i in range(len(self.commandlist)):
            self.command=self.commandlist[i]
            if 'dynamic' in self.command:
                commandsplit=self.command.split()
                self.xyzfile_path=commandsplit[1]
                self.xyzfile_path_size=float(os.stat(self.xyzfile_path).st_size)
                dynamic_steps=int(commandsplit[3])
                time_step=float(commandsplit[4]) #fs
                writeout_time=float(commandsplit[5]) # ps
                self.writeout_time=writeout_time*1000 #fs
                dynamic_time=dynamic_steps*time_step
                self.frames=round(dynamic_time/self.writeout_time)
                if os.name == 'nt':
                    self.command=self.command.replace('dynamic.exe',self.dynamic_binpath).replace(self.parameterfilename,self.parameterfile_path)
                outputfilename=self.outputfilenamelist[i]
                p = subprocess.Popen(self.command, shell=True,stdout=self.logfilehandle, stderr=self.logfilehandle)
                start=time.time()
                count=0
                while not os.path.exists(outputfilename):
                    time.sleep(1)
                    if count==0:
                        string="Status: %s"%('INITIALIZING')
                        self.status.emit(string)
                    count+=1

                xyzfilecount=0
                self.launched=False
                self.firstlaunch=True
                self.framesatlaunch=0
                self.launchready=False
                self.timearray=[]
                while xyzfilecount!=self.frames:
                    self.newxyzfilecount=self.CurrentTinkerDynamicFrame(outputfilename)
                    if self.newxyzfilecount!=xyzfilecount:
                        end=time.time()
                        iteration=end-start
                        self.timearray.append(iteration)
                        self.averagetime=sum(self.timearray)/len(self.timearray)
                        start=end
                        remainingframes=self.frames-self.newxyzfilecount
                        eta=self.averagetime*remainingframes
                        eta=self.ConvertTimeToBestUnits(eta)
                        string="ETA: %s"%(eta)
                        self.eta.emit(string)
                        progress=(self.newxyzfilecount/self.frames)*100
                        if self.cpudynamics==True:
                            self.cpupercent.emit(progress)
                        elif self.gpudynamics==True:
                            self.gpupercent.emit(progress)


                    idletime=self.ConvertSecondsToMinutes(self.GetIdleTime(monitor))
                    if idletime<self.screensleeptime and self.dynamics_only_while_idle==True:
                        self.TerminateTinkerDynamicsAndScreenSaver()

                    if self.newxyzfilecount>=self.initialframecount and self.launched==False and self.pausedynamics==False:
                        self.CheckIfReadyForLaunch(idletime)
                        if self.launchready==True:
                            self.LaunchJupyterNoteBookInControlledChromeBrowser()
                            if self.firstlaunch==False and self.terminatedjob==True: # then need to restart dynamics
                                p=self.RestartTinkerDynamics(self.command,self.frames,self.newxyzfilecount,self.logfilehandle,self.writeout_time)


                    if os.path.isfile('killbrowser.txt'):
                        os.remove('killbrowser.txt')
                        self.TerminateScreenSaver()

                    if (self.newxyzfilecount-self.framesatlaunch)>self.animationframerefreshrate and self.newxyzfilecount>self.initialframecount:
                        self.TerminateScreenSaver()


                    xyzfilecount=self.newxyzfilecount
                    time.sleep(.5)
        string="Status: %s"%('FINALIZE')
        self.status.emit(string)
        self.finished.emit()




class Monitor(QtWidgets.QDialog):
    def __init__(self, parent=None,username=None,teamname=None,status='',eta='',assigned='',expiration='',numbercpus='',numbergpus='',cpupercent=0,gpupercent=0,cpudynamics=True,gpudynamics=False):
        super(Monitor, self).__init__(parent)
        self.buttonpressed=False
        self.username=username
        if teamname==None:
            self.teamname=''
        else:
            self.teamname=teamname
        self.status=status
        self.eta=eta
        self.assigned=assigned
        self.expiration=expiration
        self.numbercpus=numbercpus
        self.numbergpus=numbergpus
        self.cpupercent=cpupercent
        self.gpupercent=gpupercent
        self.cpudynamics=cpudynamics
        self.gpudynamics=gpudynamics


    def StartMonitor(self):
        self.usernamelabel = QtWidgets.QLabel("Username:%s"%(self.username))
        self.usernamelabel.setAlignment(QtCore.Qt.AlignLeft)
        self.statuslabel = QtWidgets.QLabel("Status:%s"%(self.status))
        self.statuslabel.setAlignment(QtCore.Qt.AlignRight)
        self.teamlabel = QtWidgets.QLabel("Teamname:%s"%(self.teamname))
        self.teamlabel.setAlignment(QtCore.Qt.AlignLeft)
        self.etalabel = QtWidgets.QLabel("ETA:%s"%(self.eta))
        self.etalabel.setAlignment(QtCore.Qt.AlignRight)
        self.assignedlabel = QtWidgets.QLabel("Assigned:%s"%(self.assigned))
        self.assignedlabel.setAlignment(QtCore.Qt.AlignLeft)
        self.expirationlabel = QtWidgets.QLabel("Expiration:%s"%(self.expiration))
        self.expirationlabel.setAlignment(QtCore.Qt.AlignRight)
        verticalLayout = QtWidgets.QVBoxLayout()
        horizontalLayout1 = QtWidgets.QHBoxLayout()
        horizontalLayout2 = QtWidgets.QHBoxLayout()
        horizontalLayout3 = QtWidgets.QHBoxLayout()
        horizontalLayout4 = QtWidgets.QHBoxLayout()
        horizontalLayout5 = QtWidgets.QHBoxLayout()
        self.r1=QtWidgets.QRadioButton("While working")
        self.r1.setChecked(True)
        self.r1.toggled.connect(lambda:self.btnstate(self.r1))
        self.r2=QtWidgets.QRadioButton("While idle")
        self.r2.toggled.connect(lambda:self.btnstate(self.r2))
        radiolabel = QtWidgets.QLabel("Only run simulations")
        self.pbar = QtWidgets.QProgressBar(self)
        cpulabel = QtWidgets.QLabel("Active CPUs: %s"%(self.numbercpus))
        gpulabel = QtWidgets.QLabel("Active GPUs: %s"%(self.numbergpus))
        self.buttonStop = QtWidgets.QPushButton('Stop drug discovery', self)
        self.buttonStop.clicked.connect(self.handleStop)
        horizontalLayout1.addWidget(self.usernamelabel)
        horizontalLayout1.addStretch()
        horizontalLayout1.addWidget(self.statuslabel)
        horizontalLayout2.addWidget(self.teamlabel)
        horizontalLayout2.addStretch()
        horizontalLayout2.addWidget(self.etalabel)
        horizontalLayout3.addWidget(self.assignedlabel)
        horizontalLayout3.addStretch()
        horizontalLayout3.addWidget(self.expirationlabel)
        horizontalLayout4.addWidget(radiolabel)
        horizontalLayout4.addStretch()
        horizontalLayout4.addWidget(self.r1)
        horizontalLayout4.addStretch()
        horizontalLayout4.addWidget(self.r2)
        if self.cpudynamics==True:
            horizontalLayout5.addWidget(cpulabel)
            self.pbar.setValue(self.cpupercent)
        elif self.gpudynamics==True:
            horizontalLayout5.addWidget(gpulabel)
            self.pbar.setValue(self.gpupercent)
        horizontalLayout5.addStretch()
        horizontalLayout5.addWidget(self.pbar)
        verticalLayout.addLayout(horizontalLayout1)
        verticalLayout.addStretch()
        verticalLayout.addLayout(horizontalLayout2)
        verticalLayout.addStretch()
        verticalLayout.addLayout(horizontalLayout3)
        verticalLayout.addStretch()
        verticalLayout.addLayout(horizontalLayout4)
        verticalLayout.addStretch()
        verticalLayout.addLayout(horizontalLayout5)
        verticalLayout.addStretch()
        verticalLayout.addWidget(self.buttonStop)
        self.setLayout(verticalLayout)
        frameGm = self.frameGeometry()
        centerPoint = QtWidgets.QDesktopWidget().availableGeometry().center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())
        self.setFixedHeight(1000)
        self.setFixedWidth(1000)
        self.setWindowTitle("Monitor")

    def btnstate(self,b):
        if b.text() == "While working":
            pass
        elif b.text() == "While idle":
            pass

    def handleStop(self):
        if self.buttonpressed==False:
            self.buttonpressed==True
            self.buttonStop.setText('Resume drug discovery')
            #self.TerminateTinkerDynamicsAndScreenSaver()
            #self.pausedynamics=True
        elif self.buttonpressed==True:
            self.buttonpressed=False
            self.buttonStop.setText('Stop drug discovery')
            #self.pausedynamics=False


class Login(QtWidgets.QDialog,Client):
    def __init__(self,parent=None):
        super(Login, self).__init__(parent)

    def StartLogin(self):
        self.textName = QtWidgets.QLineEdit(self)
        usernamelabel = QtWidgets.QLabel("Username or email:")
        usernamelabel.setAlignment(QtCore.Qt.AlignCenter)
        passwordlabel = QtWidgets.QLabel("Password:")
        passwordlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.registerlabel = QtWidgets.QLabel("<a href='#'>Register</a>")
        self.registerlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.textPass = QtWidgets.QLineEdit(self)
        verticalLayout = QtWidgets.QVBoxLayout()
        horizontalLayout1 = QtWidgets.QHBoxLayout()
        horizontalLayout2 = QtWidgets.QHBoxLayout()
        self.buttonLogin = QtWidgets.QPushButton('Login',self)
        self.buttonLogin.clicked.connect(self.handleLogin)
        horizontalLayout1.addWidget(usernamelabel)
        horizontalLayout1.addStretch()
        horizontalLayout1.addWidget(self.textName)
        horizontalLayout2.addWidget(passwordlabel)
        horizontalLayout2.addStretch()
        horizontalLayout2.addWidget(self.textPass)
        verticalLayout.addLayout(horizontalLayout1)
        verticalLayout.addStretch()
        verticalLayout.addLayout(horizontalLayout2)
        verticalLayout.addStretch()
        verticalLayout.addWidget(self.registerlabel)
        verticalLayout.addStretch()
        verticalLayout.addWidget(self.buttonLogin)
        self.setLayout(verticalLayout)
        frameGm = self.frameGeometry()
        centerPoint = QtWidgets.QDesktopWidget().availableGeometry().center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())
        self.setFixedHeight(600)
        self.setFixedWidth(600)
        self.setWindowTitle("Login")

    def handleLogin(self):
        self.username=self.textName.text()
        password=self.textPass.text()
        accepted,errormsg=self.Login(self.username,password)
        if accepted==True:
            self.accept()
        else:
            self.ErrorMessage(errormsg)

    def ErrorMessage(self,errormsg):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setText(errormsg)
        msg.setWindowTitle("Error!")
        msg.exec_()


class Register(QtWidgets.QDialog,Client):
    def __init__(self, parent=None):
        super(Register, self).__init__(parent)

    def StartRegister(self):
        self.textName = QtWidgets.QLineEdit(self)
        usernamelabel = QtWidgets.QLabel("Username:")
        usernamelabel.setAlignment(QtCore.Qt.AlignCenter)
        self.textEmail = QtWidgets.QLineEdit(self)
        emaillabel = QtWidgets.QLabel("Email:")
        emaillabel.setAlignment(QtCore.Qt.AlignCenter)
        passwordlabel = QtWidgets.QLabel("Password:")
        passwordlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.textPass = QtWidgets.QLineEdit(self)
        verticalLayout = QtWidgets.QVBoxLayout()
        horizontalLayout1 = QtWidgets.QHBoxLayout()
        horizontalLayout2 = QtWidgets.QHBoxLayout()
        horizontalLayout3 = QtWidgets.QHBoxLayout()
        self.buttonRegister = QtWidgets.QPushButton('Register', self)
        self.buttonRegister.clicked.connect(self.handleRegister)
        horizontalLayout1.addWidget(usernamelabel)
        horizontalLayout1.addStretch()
        horizontalLayout1.addWidget(self.textName)
        horizontalLayout2.addWidget(emaillabel)
        horizontalLayout2.addStretch()
        horizontalLayout2.addWidget(self.textEmail)
        horizontalLayout3.addWidget(passwordlabel)
        horizontalLayout3.addStretch()
        horizontalLayout3.addWidget(self.textPass)
        verticalLayout.addLayout(horizontalLayout1)
        verticalLayout.addStretch()
        verticalLayout.addLayout(horizontalLayout2)
        verticalLayout.addStretch()
        verticalLayout.addLayout(horizontalLayout3)
        verticalLayout.addStretch()
        verticalLayout.addWidget(self.buttonRegister)
        self.setLayout(verticalLayout)
        frameGm = self.frameGeometry()
        centerPoint = QtWidgets.QDesktopWidget().availableGeometry().center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())
        self.setFixedHeight(600)
        self.setFixedWidth(600)
        self.setWindowTitle("Register")

    def ErrorMessage(self,errormsg):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setText(errormsg)
        msg.setWindowTitle("Error!")
        msg.exec_()

    def handleRegister(self): # contact server
        email=self.textEmail.text()
        username=self.textName.text()
        password=self.textPass.text()
        accepted,errormsg=self.Register(email,username,password)
        if accepted==True:
            self.accept()
        else:
            self.ErrorMessage(errormsg)


class MainWindow(QtWidgets.QMainWindow,Client):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.client=Client()
        self.login = Login()
        self.register = Register()
        self.StartLoginWindow()

    def StartRegisterWindow(self):
        self.register.StartRegister()
        self.register.show()

    def StartMonitorWindow(self):
        self.monitor.StartMonitor()
        self.monitor.show()

    def reportStatus(self,n):
        self.monitor.statuslabel.setText(n)

    def reportETA(self,n):
        self.monitor.etalabel.setText(n)

    def reportCPUPercent(self,n):
        if self.monitor.cpudynamics==True:
            self.monitor.pbar.setValue(n)

    def reportGPUpercent(self,n):
        if self.monitor.gpudynamics==True:
            self.monitor.pbar.setValue(n)

    def UpdateAssignedExpirationLabels(self):
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        string="Assigned: %s"%(dt_string)
        self.monitor.assignedlabel.setText(string)
        timestamp=time.time()
        timeallowed=3600*self.client.timeallowed
        futuretimestamp=timestamp+timeallowed
        dt_object = datetime.fromtimestamp(futuretimestamp)
        dt_string = dt_object.strftime("%d/%m/%Y %H:%M:%S")
        string="Expiration: %s"%(dt_string)
        self.monitor.expirationlabel.setText(string)

    def CompleteJob(self):
        self.client.CompleteJob(self.client.outputfilenamelist,self.client.inputfilenamelist)

    def StartLoginWindow(self):
        self.login.StartLogin()
        self.login.registerlabel.linkActivated.connect(self.StartRegisterWindow)
        self.login.show()
        if self.login.exec_() == QtWidgets.QDialog.Accepted:
            self.monitor = Monitor(username=self.login.username)
            self.StartMonitorWindow()
            self.client.ReceiveJob()
            self.UpdateAssignedExpirationLabels()
            self.worker=Worker(commandlist=self.client.commandlist,outputfilenamelist=self.client.outputfilenamelist)
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.ExecuteCommand)
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.finished.connect(self.CompleteJob)
            self.worker.status.connect(self.reportStatus)
            self.worker.eta.connect(self.reportETA)
            self.worker.cpupercent.connect(self.reportCPUPercent)
            self.worker.gpupercent.connect(self.reportGPUpercent)
            self.thread.start()
            sys.exit(app.exec_())


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
