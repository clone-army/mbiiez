import time
import six
import re
import socket

class console:

    def __init__(self, rcon_password, server_port):
        self.ip = "127.0.0.1"
        self.port = int(server_port)
        self.password = rcon_password
        self.prefix_rcon = bytes([0xff, 0xff, 0xff, 0xff]) + b'rcon '
        self.prefix_console = bytes([0xff, 0xff, 0xff, 0xff])

    def rcon(self, command, quiet = False):
        cmd = f"{self.password} {command}".encode()
        query = self.prefix_rcon + cmd
        return self.send(query)

    def console(self, command, quiet = False):
        cmd = f"{command}".encode()
        query = self.prefix_console + cmd    
        return self.send(query)

    def send(self, query):
        # Create a fresh socket for every request so there is no state
        # bleed (non-blocking flag, stale buffer) from previous calls.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        try:
            sock.connect((self.ip, self.port))
            sock.send(query)

            total_data = []
            while True:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    total_data.append(data.decode("utf-8", "ignore"))
                except socket.timeout:
                    break
        finally:
            sock.close()

        return ''.join(total_data)


    # Send SAY as Server
    def say(self, message):
        self.rcon("svsay {}".format(message))
       
    # Send TELL as server (To Player)   
    def tell(self, player_id, message):
        self.rcon("svtell {} {}".format(player_id,message))
        
    def cvar(self, key, value = None, quiet = False):
    
        if(value == None): # GET a CVAR Value
            response = self.rcon(key, True)
            try:
                #OpenJK
                if("cvar" in response.lower()):
                    response = re.findall(r'"([^"]*)"', response)[0]               
                #JAMP    
                else:
                    response = response.split('"')[1::2][1]; # the [1::2] is a slicing which extracts odd values                
            except:
                if(not quiet):
                    print("Error, unknown or invalid cvar: {}".format(key))
                return None
                
            result = self.cvar_clean(response)   
            return result
        
        else: #SET a CVAR Value
            response = self.rcon("set " + key + "=" + str(value))             
            
    def cvar_clean(self, text):
        return re.sub(r"\^[1-9]","",text)
   
 