import sqlite3
import os
from flask import Flask, request, render_template, redirect
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

# Views
from mbiiez.web.views.dashboard import view as dashboard_v
from mbiiez.web.views.logs import view as logs_v
from mbiiez.web.views.stats import view as stats_v
from mbiiez.web.views.players import view as players_v
from mbiiez.web.views.instance import view as instance_v
from mbiiez.web.views.chat import view as chat_v

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
    c = dashboard_c()
    return render_template('pages/dashboard.html', view_bag=c.controller_bag)


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


@app.route('/instance/<instance_name>/command', methods=['POST'])
@auth.login_required
def instance_command(instance_name):
    from mbiiez.instance import instance as MBInstance
    data = request.get_json()
    cmd = data.get('command')
    inst = MBInstance(instance_name)
    try:
        if cmd == 'start':
            inst.start()
            return {"output": f"Instance {instance_name} started."}
        elif cmd == 'stop':
            inst.stop()
            return {"output": f"Instance {instance_name} stopped."}
        elif cmd == 'restart':
            inst.restart()
            return {"output": f"Instance {instance_name} restarted."}
        else:
            return {"error": "Unknown command."}, 400
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/chat', methods=['GET', 'POST'])
@auth.login_required
def chat():
    instance = request.args.get('instance')
    c = chat_c(instance)
    return chat_v(c).render()

@app.context_processor
def include_instances():
    return dict(instances=tools().list_of_instances())

app.register_blueprint(logs_api)
app.register_blueprint(chat_api)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=settings.web_service.port, use_reloader=True)

