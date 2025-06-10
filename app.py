import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from routes.instances import instances_bp
from routes.logs import logs_bp
from routes.smod import smod_bp
from routes.config import config_bp

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.register_blueprint(instances_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(smod_bp)
app.register_blueprint(config_bp)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)