import sqlite3
import os
import time
import threading
import subprocess
from flask import Flask, request, render_template, redirect, jsonify
from flask_httpauth import HTTPBasicAuth
from mbiiez import settings

# Web Tools
from mbiiez.web.tools import tools

# Controllers
from mbiiez.web.controllers.dashboard import controller as dashboard_c
from mbiiez.web.controllers.logs import controller as logs_c
from mbiiez.web.controllers.stats import controller as stats_c
from mbiiez.web.controllers.players import controller as players_c
from mbiiez.web.controllers.instance import controller as instance_c
from mbiiez.web.controllers.logs_api import logs_api
from mbiiez.web.controllers.chat import controller as chat_c
from mbiiez.web.controllers.chat_api import chat_api
from mbiiez.web.controllers.mod import controller as mod_c
from mbiiez.web.controllers.rcon import controller as rcon_c
from mbiiez.web.controllers.config import controller as config_c

# Views
from mbiiez.web.views.dashboard import view as dashboard_v
from mbiiez.web.views.logs import view as logs_v
from mbiiez.web.views.stats import view as stats_v
from mbiiez.web.views.players import view as players_v
from mbiiez.web.views.instance import view as instance_v
from mbiiez.web.views.chat import view as chat_v
from mbiiez.web.views.mod import view as mod_v
from mbiiez.web.views.rcon import view as rcon_v
from mbiiez.web.views.config import view as config_v

app = Flask(
    __name__,
    static_url_path="/assets",
    static_folder="mbiiez/web/static",
    template_folder="mbiiez/web/templates"
)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Authentication
auth = HTTPBasicAuth()
@auth.verify_password
def verify_password(username, password):
    if(username == settings.web_service.username and password == settings.web_service.password):
        return username
                
@app.route('/', methods=['GET', 'POST'])
@auth.login_required
def home():
    return redirect("/dashboard", code=302)

@app.route('/dashboard', methods=['GET', 'POST'])
@auth.login_required
def dashboard():
    return render_template('pages/dashboard.html', view_bag={})


@app.route('/logs', methods=['GET', 'POST'])
@auth.login_required
def log():
    instance = request.args.get('instance')
    page = request.args.get('page') or 1
    per_page = request.args.get('per_page') or 100  # Default to 100 if not provided
    c = logs_c(instance, page, per_page)
    return logs_v(c).render()
    
@app.route('/players', methods=['GET', 'POST'])
@auth.login_required
def players():
    c = players_c(request.args.get('filter'), request.args.get('page'), request.args.get('per_page'))
    return players_v(c).render()    
    
@app.route('/stats', methods=['GET', 'POST'])
@auth.login_required
def stats():
    c = stats_c(request.args.get('instance'))
    return stats_v(c).render()    

@app.route('/instance', methods=['GET', 'POST'])
@auth.login_required
def instance():
    c = instance_c(request.args.get('instance'))
    return instance_v(c).render()     

instance_locks = {}

@app.route('/instance/<instance_name>/command', methods=['POST'])
@auth.login_required
def instance_command(instance_name):
    data = request.get_json()
    cmd = data.get('command')
    if cmd not in ['start', 'stop', 'restart']:
        return {"error": "Unknown command."}, 400
    
    # Change "start" to actually run "restart" for cleaner startup
    if cmd == 'start':
        actual_cmd = 'restart'
    else:
        actual_cmd = cmd
    
    # For stop and restart commands, always use --force to avoid confirmation prompts
    if actual_cmd in ['stop', 'restart']:
        cli_cmd = ["mbii", "-i", instance_name, actual_cmd, "--force"]
    else:
        cli_cmd = ["mbii", "-i", instance_name, actual_cmd]
    
    try:
        result = subprocess.run(cli_cmd, capture_output=True, text=True, timeout=30)
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        output = output.strip()
        if result.returncode == 0:
            return {"output": output or f"Instance {instance_name} {cmd}ed."}
        else:
            return {"error": output or f"Failed to {cmd} instance {instance_name}."}, 500
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/instance/<instance_name>/command_async', methods=['POST'])
@auth.login_required
def instance_command_async(instance_name):
    """Non-blocking command execution for start/restart operations"""
    data = request.get_json()
    cmd = data.get('command')
    if cmd not in ['start', 'stop', 'restart']:
        return {"error": "Unknown command."}, 400
    
    # Change "start" to actually run "restart" for cleaner startup
    if cmd == 'start':
        actual_cmd = 'restart'
    else:
        actual_cmd = cmd
    
    # For stop and restart commands, always use --force to avoid confirmation prompts
    if actual_cmd in ['stop', 'restart']:
        cli_cmd = ["mbii", "-i", instance_name, actual_cmd, "--force"]
    else:
        cli_cmd = ["mbii", "-i", instance_name, actual_cmd]
    
    try:
        # Start the process in the background without waiting
        # Use proper detachment to prevent server from stopping when web UI stops
        # Create a completely independent process using double fork technique
        def detached_process():
            # First fork
            pid = os.fork()
            if pid > 0:
                # Parent process exits immediately
                return
            
            # Child process - become session leader
            os.setsid()
            
            # Second fork to prevent zombie processes
            pid = os.fork()
            if pid > 0:
                # First child exits
                os._exit(0)
            
            # Grandchild process - completely detached
            # Redirect file descriptors
            with open(os.devnull, 'r') as devnull_in:
                with open(os.devnull, 'w') as devnull_out:
                    os.dup2(devnull_in.fileno(), 0)  # stdin
                    os.dup2(devnull_out.fileno(), 1)  # stdout
                    os.dup2(devnull_out.fileno(), 2)  # stderr
            
            # Execute the command
            os.execvp(cli_cmd[0], cli_cmd)
        
        # Start the detached process
        detached_process()
        
        return {"output": f"Instance {instance_name} {cmd} initiated.", "async": True}
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/chat', methods=['GET', 'POST'])
@auth.login_required
def chat():
    instance = request.args.get('instance')
    c = chat_c(instance)
    return chat_v(c).render()

@app.route('/mod', methods=['GET'])
@auth.login_required
def mod():
    instance = request.args.get('instance')
    c = mod_c(instance)
    return mod_v(c).render()

@app.route('/mod/map', methods=['POST'])
@auth.login_required
def mod_map():
    data = request.get_json()
    success, msg = mod_c.change_map(data['instance'], data['mapname'])
    return {'success': success, 'error': None if success else msg}

@app.route('/mod/mode', methods=['POST'])
@auth.login_required
def mod_mode():
    data = request.get_json()
    success, msg = mod_c.change_mode(data['instance'], data['mode'])
    return {'success': success, 'error': None if success else msg}

@app.route('/mod/kick', methods=['POST'])
@auth.login_required
def mod_kick():
    data = request.get_json()
    success, msg = mod_c.kick_player(data['instance'], data['player_id'])
    return {'success': success, 'error': None if success else msg}

@app.route('/mod/ban', methods=['POST'])
@auth.login_required
def mod_ban():
    data = request.get_json()
    success, msg = mod_c.ban_player(data['instance'], data['ip'])
    return {'success': success, 'error': None if success else msg}

@app.route('/mod/unban', methods=['POST'])
@auth.login_required
def mod_unban():
    data = request.get_json()
    success, msg = mod_c.unban_ip(data['instance'], data['ip'])
    return {'success': success, 'error': None if success else msg}

@app.route('/mod/tell', methods=['POST'])
@auth.login_required
def mod_tell():
    data = request.get_json()
    success, msg = mod_c.tell_player(data['instance'], data['player_id'], data['message'])
    return {'success': success, 'error': None if success else msg}

@app.route('/rcon', methods=['GET'])
@auth.login_required
def rcon():
    instance = request.args.get('instance')
    c = rcon_c(instance)
    return rcon_v(c).render()

@app.route('/rcon/send', methods=['POST'])
@auth.login_required
def rcon_send():
    data = request.get_json()
    success, response = rcon_c.send_rcon(data['instance'], data['command'])
    return {'success': success, 'response': response if success else None, 'error': None if success else response}

@app.route('/config', methods=['GET'])
@auth.login_required
def config():
    instance = request.args.get('instance')
    c = config_c(instance)
    return config_v(c).render()

@app.route('/config/save', methods=['POST'])
@auth.login_required
def config_save():
    data = request.get_json()
    success, msg = config_c.save_config(data['instance'], data['content'])
    return {'success': success, 'error': None if success else msg}

@app.context_processor
def include_instances():
    return dict(instances=tools().list_of_instances())

app.register_blueprint(logs_api)
app.register_blueprint(chat_api)

def status_api(instance_name):
        from mbiiez.instance import instance as MBInstance
        try:
            inst = MBInstance(instance_name)
            status = inst.status()
            return jsonify({
                'server_name': status.get('server_name', ''),
                'players_count': status.get('players_count', 0),
                'map': status.get('map', ''),
                'mode': status.get('mode', ''),
                'uptime': status.get('uptime', ''),
                'running': status.get('server_running', False),
                'error': None
            })
        except Exception as e:
            return jsonify({'error': str(e)})

@app.route('/api/check_server/<instance_name>', methods=['GET'])
@auth.login_required
def check_server_status(instance_name):
    """Check if server is running by attempting UDP connection"""
    import socket
    from mbiiez.instance import instance as MBInstance
    
    try:
        inst = MBInstance(instance_name)
        config = inst.config
        
        # Get server IP and port from config
        server_ip = config.get('server', {}).get('ip', '127.0.0.1')
        server_port = int(config.get('server', {}).get('port', 29070))
        
        # Try to connect to UDP port
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)  # 1 second timeout
        
        try:
            # Send a simple UDP packet to test if port is open
            sock.sendto(b'', (server_ip, server_port))
            sock.close()
            return jsonify({'running': True, 'error': None})
        except:
            sock.close()
            return jsonify({'running': False, 'error': None})
            
    except Exception as e:
        return jsonify({'running': False, 'error': str(e)})

app.add_url_rule('/api/instance_status/<instance_name>', 'status_api', status_api, methods=['GET'])

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=settings.web_service.port, use_reloader=False)

