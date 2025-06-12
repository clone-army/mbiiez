from mbiiez.models import process
from mbiiez.db import db
from mbiiez.bcolors import bcolors

import multiprocessing
import os
import time
import subprocess
import shlex

import asyncio
import inspect


class process_handler:

    instance = None
    services = []
    
    def __init__(self, instance):
        self.instance = instance
               
    def register_service(self, name, func, priority = 99, awaiter = None):
        """ 
            Register a function as a service. Runs as a fork with PIDs stored in database
        """
        self.services.append({"name": name, "func": func, "priority": priority, "awaiter": awaiter})

    def launch_services(self):
        """ 
            Launch all services 
        """       
        # Sort by Priority
        services = sorted(self.services, key=lambda k: k['priority'])
        
        for service in services:
        
            if(service['awaiter'] and callable(service['awaiter'])):
                service['awaiter']();
        
            self.instance.log_handler.log("Starting Service: " + service['name'])
            print("[" + bcolors.OK + "Yes" + bcolors.ENDC + "] Launching " + service['name'])   
            self.start(service['func'], service['name'], self.instance.name)
            time.sleep(1)
            
    def start(self, func, name, instance):
        """ 
            Start a given func (or shell command), with name for instance 
        """  

        # Is our service a Python Function?
        if(callable(func)):

            # Process is Forked
            pid = os.fork()
            
            # Child Process Continues
            if(pid == 0):
            
                # Capture the PID for this fork
                db().insert("processes", {"name": name, "pid": os.getpid(), "instance": instance})

                times_started = 0

                # Begin a Loop
                while(True):
                
                    if(times_started > 10):
                        self.instance.log_handler.log("{} Failed to start after 10 tries".format(name))
                        break;
                     
                    try:
                        
                        if inspect.iscoroutinefunction(func):
                            asyncio.run(func())
                        else:
                            func()
                                                
                         
                    except Exception as e:     
                        self.instance.exception_handler.log(e)
                         
                    # Reached is func ends, should not end    
                    times_started = times_started + 1
                    time.sleep(1)
                          
        # It is a shell command so run inside a python container so we have the pid
        else:
            # Output from this process is sent to this log file, but is cleared on every restart. 
            std_out_file = "/var/log/{}-{}-output.log".format(instance.lower(),name.lower())

            # Used to clear the file, these output looks are not for persistant logging
            open(std_out_file, 'w').close()

            pid = os.fork()
            if(pid == 0):
            
                func = "{} ".format(func)
                
                container_name = name + " Container"
            
                # When running a shell command, a fork is created which acts are the parent to the new process.
            
                db().insert("processes", {"name": container_name, "pid": os.getpid(), "instance": instance})
                
                process = None
                crashes = 0
                restart = False
                
                # Begin Loop
                while(True):
                
                    # Should stop this process if requested to stop
                    if(not self.process_status_name(container_name)):
                        break;
                        
                    if(crashes >= 10):
                        self.instance.log_handler.log("Service: {} was unable to start after {} retries...".format(name, crashes))
                        break;
                        
                    # Start the Process
                    if(process == None):  
                        if os.path.exists(std_out_file):
                            os.remove(std_out_file)
                        log = open(std_out_file, 'a')
                        process = subprocess.Popen(shlex.split(func), shell=False, stdin=log, stdout=log, stderr=log) 
                        db().insert("processes", {"name": name, "pid": process.pid, "instance": instance}) 
                        time.sleep(1)
                        if(crashes > 0):
                            time.sleep(5)
                        
                    # If either POLL returns some error or the PID is not running at all
                    if(not process == None):     
                        if(not process.poll() == None): # WHEN PROCESS CRASHES, POLL AND STATUS STILL SHOW ACTIVE
                            crashes = crashes + 1
                            db().execute("delete from processes where pid = {}".format(process.pid))
                            self.stop_process_name(name)
                            process = None
                            self.instance.log_handler.log("Restarting Service: {}, failed {} times".format(name, crashes))
                            
                    time.sleep(3)

    def process_pid_by_name(self, name):
        """ 
        Find a process pid by its name
        """           
        pr = db().select("processes",{"instance": self.instance.name, "name": name})
        for p in pr:
            return p['pid']
        return 0

    def process_status_name(self, name):
        """ 
        Is a process running by its name
        """  
        
        pr = db().select("processes",{"instance": self.instance.name, "name": name})
     
        if(len(pr) == 0):
            return False
        else:
            for p in pr:
                if(self.process_status_pid(p['pid'])):
                    return True
                else:
                    return False
       
    def process_status_pid(self, pid):
        """ 
        Is a process running by its pid
        """    
        try:
             os.kill(pid, 0)
             return True
             
        except OSError:           
            return False
       
    def stop_all(self):
        """ 
        Stops all processes for this instance
        """  
        pr = db().select("processes",{"instance": self.instance.name})

        for p in pr:          
            if(self.process_status_pid(p['pid'])):           
                if(self.stop_process_pid(p['pid'])):
                    # Extra DB not really needed but best to be safe
                    db().delete("processes", p['id'])
                    print("[" + bcolors.GREEN + "Yes" + bcolors.ENDC +  "] Stopped {}".format(str(p['name'])))
                else:
                    print("[" + bcolors.RED + "No" + bcolors.ENDC +  "] Stopped {}".format(str(p['name']))) 
            else:
                db().delete("processes", p['id'])

        # The above is quite good for keeping track of processes, ultimately it does not work....
        # This is the brute force... burn it all, command
        cmd = "ps aux | grep -ie " + self.instance.name + "- | awk '{print $2}' | xargs kill -15 >/dev/null 2>&1"
        os.system(cmd)                 


    def stop_process_name(self, name):
        """ 
        Stops all process by its name
        """         
        pr = db().select("processes",{"instance": self.instance.name, "name": name})
        db().execute("delete from processes where instance = \"{}\" and name = \"{}\"".format(self.instance.name, name))
        
        if(len(pr) == 0): # Without its pid we cant do anything here
            return False
        else:
            for p in pr:
                if(self.process_status_pid(p['pid'])):
                    return self.stop_process_pid(p['pid'])
                else:
                    return False
            
    def stop_process_pid(self, pid):
        """ 
        Stops process by its pid
        """         
        
        try:
            db().execute("delete from processes where pid = {}".format(pid))
        
            if(self.process_status_pid(pid)):
                os.kill(pid, 9)

            return True
             
        except OSError:           
            return False    