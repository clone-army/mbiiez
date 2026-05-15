import json
import os
import socket
import subprocess
import time
from functools import wraps

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from mbiiez import settings
from mbiiez.db import db

# Web Tools
from mbiiez.web.tools import tools
from mbiiez.web.tools import trace_dashboard_load

# Controllers
from mbiiez.web.controllers.chat import controller as chat_c
from mbiiez.web.controllers.config import controller as config_c
from mbiiez.web.controllers.dashboard import controller as dashboard_c
from mbiiez.web.controllers.instance import controller as instance_c
from mbiiez.web.controllers.logs import controller as logs_c
from mbiiez.web.controllers.logs_api import logs_api
from mbiiez.web.controllers.chat_api import chat_api
from mbiiez.web.controllers.mod import controller as mod_c
from mbiiez.web.controllers.players import controller as players_c
from mbiiez.web.controllers.rcon import controller as rcon_c
from mbiiez.web.controllers.stats import controller as stats_c

# Views
from mbiiez.web.views.chat import view as chat_v
from mbiiez.web.views.config import view as config_v
from mbiiez.web.views.dashboard import view as dashboard_v
from mbiiez.web.views.instance import view as instance_v
from mbiiez.web.views.logs import view as logs_v
from mbiiez.web.views.mod import view as mod_v
from mbiiez.web.views.players import view as players_v
from mbiiez.web.views.rcon import view as rcon_v
from mbiiez.web.views.stats import view as stats_v


app = Flask(
    __name__,
    static_url_path="/assets",
    static_folder="mbiiez/web/static",
    template_folder="mbiiez/web/templates",
)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = os.environ.get("MBIIEZ_WEB_SECRET_KEY", "mbiiez-change-this-secret")


# Authentication
ROLE_RANK = {"viewer": 10, "mod": 20, "admin": 30}
INSTANCE_LIST_CACHE_SECONDS = 3
_instance_list_cache = {"expires": 0.0, "items": []}


def _normalize_role(role):
    role = str(role or "viewer").strip().lower()
    if role not in ROLE_RANK:
        return "viewer"
    return role


def _is_password_hashed(value):
    if not value:
        return False
    return str(value).startswith("pbkdf2:") or str(value).startswith("scrypt:")


def _password_matches(stored, provided):
    stored = str(stored or "")
    provided = str(provided or "")

    if _is_password_hashed(stored):
        try:
            return check_password_hash(stored, provided)
        except Exception:
            return False

    return stored == provided


def _load_users_data():
    data = {"users": []}
    users_file = settings.web_service.users_file

    if users_file and os.path.exists(users_file):
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and isinstance(loaded.get("users"), list):
                    data = loaded
        except Exception:
            pass

    return data


def _save_users_data(data):
    users_file = settings.web_service.users_file
    users_dir = os.path.dirname(users_file)

    if users_dir and not os.path.exists(users_dir):
        os.makedirs(users_dir, exist_ok=True)

    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    try:
        os.chmod(users_file, 0o600)
    except Exception:
        pass


def _load_users():
    users = {}

    data = _load_users_data()
    for item in data.get("users", []):
        username = str(item.get("username", "")).strip()
        password = str(item.get("password", ""))
        role = _normalize_role(item.get("role", "viewer"))

        if username:
            users[username] = {"password": password, "role": role}

    return users


def _setup_required():
    users_file = settings.web_service.users_file
    if not users_file:
        return True

    if not os.path.exists(users_file):
        return True

    users = _load_users()
    return len(users) == 0


def _create_first_user(username, password):
    data = {
        "users": [
            {
                "username": username,
                "password": generate_password_hash(password),
                "role": "admin",
            }
        ]
    }

    _save_users_data(data)


def _migrate_plaintext_user(username, plaintext_password):
    if not settings.web_service.users_file or not os.path.exists(settings.web_service.users_file):
        return

    data = _load_users_data()
    changed = False

    for item in data.get("users", []):
        item_user = str(item.get("username", "")).strip()
        item_pass = str(item.get("password", ""))
        if item_user == username and not _is_password_hashed(item_pass) and item_pass == plaintext_password:
            item["password"] = generate_password_hash(plaintext_password)
            changed = True
            break

    if changed:
        _save_users_data(data)


def _is_api_request(path):
    return path.startswith("/api/") or path.endswith("_api")


def _session_user():
    return str(session.get("mbiiez_user", "")).strip()


def _session_role():
    return _normalize_role(session.get("mbiiez_role", "viewer"))


def _set_session_auth(username, role):
    session["mbiiez_user"] = username
    session["mbiiez_role"] = _normalize_role(role)


def _clear_session_auth():
    session.pop("mbiiez_user", None)
    session.pop("mbiiez_role", None)


def _is_logged_in():
    return bool(_session_user())


def _auth_failed_response(path):
    if _is_api_request(path) or request.method != "GET":
        return jsonify({"error": "Authentication required"}), 401

    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("login", next=_safe_next_path(next_url)), code=302)


def _safe_next_path(path):
    path = str(path or "").strip()
    if not path.startswith("/") or path.startswith("//"):
        return "/dashboard"
    return path


def _role_allows(current_role, required_role):
    return ROLE_RANK.get(current_role, 0) >= ROLE_RANK.get(required_role, 0)


def _required_role_for_path(path, method):
    if path.startswith("/assets/"):
        return None

    if path.startswith("/health"):
        return None

    if path.startswith("/login") or path.startswith("/logout") or path.startswith("/setup"):
        return None

    admin_prefixes = [
        "/config",
        "/instance/",
        "/api/audit",
        "/admin",
    ]

    mod_prefixes = [
        "/mod",
        "/rcon",
    ]

    if path.startswith("/instance/") and path.endswith("/command"):
        return "admin"

    if path.startswith("/instance/") and path.endswith("/command_async"):
        return "admin"

    if path == "/config/save":
        return "admin"

    if path in ["/rcon/send", "/chat/send"]:
        return "mod"

    if path.startswith("/admin"):
        return "admin"

    if any(path.startswith(prefix) for prefix in admin_prefixes):
        if path in ["/config", "/config/save"]:
            return "admin"

    if any(path.startswith(prefix) for prefix in mod_prefixes):
        return "mod"

    # Default viewer permission for all other app pages/APIs.
    return "viewer"


def _current_user():
    user = getattr(g, "current_user", "")
    return user if user else "anonymous"


def _current_role():
    return getattr(g, "current_role", "viewer")


def _authenticate_credentials(username, password):
    users = _load_users()
    user = users.get(username)
    if not user:
        return False, ""

    if not _password_matches(user.get("password"), password):
        return False, ""

    if not _is_password_hashed(user.get("password")):
        _migrate_plaintext_user(username, password)

    return True, user.get("role", "viewer")


def _list_instances_cached():
    now = time.time()
    if now < _instance_list_cache["expires"]:
        return _instance_list_cache["items"]

    try:
        items = tools().list_of_instances()
    except Exception:
        items = []

    _instance_list_cache["items"] = items
    _instance_list_cache["expires"] = now + INSTANCE_LIST_CACHE_SECONDS
    return items


def _audit(action, instance_name=None, details=""):
    try:
        db().insert(
            "web_audit",
            {
                "actor": _current_user(),
                "role": _current_role(),
                "action": action,
                "instance": instance_name or "",
                "details": str(details),
                "ip": request.remote_addr or "",
            },
        )
    except Exception:
        pass


def require_role(required_role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not _role_allows(_current_role(), required_role):
                return jsonify({"error": "Insufficient permissions"}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.before_request
def enforce_auth_and_role():
    path = request.path or "/"

    # Default to anonymous each request, then elevate when authenticated.
    g.current_user = ""
    g.current_role = "viewer"

    if _setup_required():
        setup_allowed = (
            path.startswith("/assets/")
            or path.startswith("/health")
            or path.startswith("/setup")
            or path.startswith("/login")
            or path.startswith("/logout")
        )
        if not setup_allowed:
            return redirect("/setup", code=302)
        return None

    if path.startswith("/setup"):
        return redirect("/dashboard", code=302)

    if not settings.web_service.auth_enabled:
        g.current_user = "local"
        g.current_role = "admin"
    elif _is_logged_in():
        g.current_user = _session_user()
        g.current_role = _session_role()

    required_role = _required_role_for_path(path, request.method)

    if required_role is None:
        return None

    if settings.web_service.auth_enabled and not _is_logged_in():
        return _auth_failed_response(path)

    if not _role_allows(_current_role(), required_role):
        return jsonify({"error": "Insufficient permissions"}), 403

    return None


@app.context_processor
def include_instances_and_auth():
    dashboard_requested = request.path == "/dashboard"
    context_start = time.perf_counter() if dashboard_requested else None
    if dashboard_requested:
        trace_dashboard_load("context processor start")

    users = _load_users() if settings.web_service.auth_enabled else {}
    if dashboard_requested:
        trace_dashboard_load(
            "context processor users loaded",
            "count={}".format(len(users)),
            (time.perf_counter() - context_start) * 1000,
        )

    instances = _list_instances_cached()
    if dashboard_requested:
        trace_dashboard_load(
            "context processor instances loaded",
            "count={}".format(len(instances)),
            (time.perf_counter() - context_start) * 1000,
        )

    return dict(
        instances=instances,
        current_user=_current_user(),
        current_role=_current_role(),
        can_mod=_role_allows(_current_role(), "mod"),
        can_admin=_role_allows(_current_role(), "admin"),
        setup_required=_setup_required(),
        users_count=len(users),
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "auth_enabled": settings.web_service.auth_enabled,
            "setup_required": _setup_required(),
            "users_file": settings.web_service.users_file,
            "users_file_exists": bool(settings.web_service.users_file and os.path.exists(settings.web_service.users_file)),
        }
    )


@app.route("/setup", methods=["GET"])
def setup_page():
    if not _setup_required():
        return redirect("/dashboard", code=302)

    return render_template(
        "pages/setup.html",
        users_file=settings.web_service.users_file,
    )


@app.route("/setup/create", methods=["POST"])
def setup_create():
    if not _setup_required():
        return jsonify({"error": "Setup is already complete."}), 400

    data = request.get_json(silent=True) or request.form or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    try:
        _create_first_user(username, password)
        return jsonify(
            {
                "success": True,
                "message": "Initial admin user created. Reload and log in.",
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/login", methods=["GET", "POST"])
def login():
    if not settings.web_service.auth_enabled:
        return redirect("/dashboard", code=302)

    if _setup_required():
        return redirect("/setup", code=302)

    if _is_logged_in():
        return redirect(_safe_next_path(request.args.get("next")), code=302)

    error = ""
    next_path = _safe_next_path(request.args.get("next") or "/dashboard")

    if request.method == "POST":
        username = str(request.form.get("username", "")).strip()
        password = str(request.form.get("password", "")).strip()

        ok, role = _authenticate_credentials(username, password)
        if ok:
            _set_session_auth(username, role)
            return redirect(_safe_next_path(request.form.get("next")), code=302)

        error = "Invalid username or password."

    return render_template("pages/login.html", error=error, next_path=next_path)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    _clear_session_auth()
    return redirect("/login", code=302)


@app.route("/admin/users", methods=["GET"])
@require_role("admin")
def admin_users_page():
    users = _load_users_data().get("users", [])
    sanitized = []
    for u in users:
        sanitized.append(
            {
                "username": str(u.get("username", "")),
                "role": _normalize_role(u.get("role", "viewer")),
            }
        )

    return render_template("pages/admin-users.html", view_bag={"users": sanitized})


@app.route("/admin/users/add", methods=["POST"])
@require_role("admin")
def admin_users_add():
    data = request.get_json(silent=True) or request.form or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    role = _normalize_role(data.get("role", "viewer"))

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    users_data = _load_users_data()
    users = users_data.get("users", [])
    for u in users:
        if str(u.get("username", "")).strip().lower() == username.lower():
            return jsonify({"error": "User already exists."}), 400

    users.append(
        {
            "username": username,
            "password": generate_password_hash(password),
            "role": role,
        }
    )
    users_data["users"] = users
    _save_users_data(users_data)

    _audit("admin_user_add", details="user={};role={}".format(username, role))
    return jsonify({"success": True})


@app.route("/admin/users/password", methods=["POST"])
@require_role("admin")
def admin_users_password():
    data = request.get_json(silent=True) or request.form or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    users_data = _load_users_data()
    users = users_data.get("users", [])

    found = False
    for u in users:
        if str(u.get("username", "")).strip() == username:
            u["password"] = generate_password_hash(password)
            found = True
            break

    if not found:
        return jsonify({"error": "User not found."}), 404

    users_data["users"] = users
    _save_users_data(users_data)

    _audit("admin_user_password", details="user={}".format(username))
    return jsonify({"success": True})


@app.route("/admin/users/role", methods=["POST"])
@require_role("admin")
def admin_users_role():
    data = request.get_json(silent=True) or request.form or {}
    username = str(data.get("username", "")).strip()
    role = _normalize_role(data.get("role", "viewer"))

    users_data = _load_users_data()
    users = users_data.get("users", [])

    target_user = None
    for u in users:
        if str(u.get("username", "")).strip() == username:
            target_user = u
            break

    if not target_user:
        return jsonify({"error": "User not found."}), 404

    current_role = _normalize_role(target_user.get("role", "viewer"))
    target_user["role"] = role

    admin_count = 0
    for u in users:
        if _normalize_role(u.get("role", "viewer")) == "admin":
            admin_count += 1

    if admin_count == 0:
        # Revert and reject if change removes last admin.
        target_user["role"] = current_role
        return jsonify({"error": "At least one admin account must remain."}), 400

    users_data["users"] = users
    _save_users_data(users_data)

    _audit("admin_user_role", details="user={};role={}".format(username, role))
    return jsonify({"success": True})


@app.route("/admin/users/delete", methods=["POST"])
@require_role("admin")
def admin_users_delete():
    data = request.get_json(silent=True) or request.form or {}
    username = str(data.get("username", "")).strip()

    users_data = _load_users_data()
    users = users_data.get("users", [])

    if username == _current_user():
        return jsonify({"error": "You cannot delete your own account."}), 400

    remaining = [u for u in users if str(u.get("username", "")).strip() != username]
    if len(remaining) == len(users):
        return jsonify({"error": "User not found."}), 404

    admin_count = 0
    for u in remaining:
        if _normalize_role(u.get("role", "viewer")) == "admin":
            admin_count += 1

    if admin_count == 0:
        return jsonify({"error": "At least one admin account must remain."}), 400

    users_data["users"] = remaining
    _save_users_data(users_data)

    _audit("admin_user_delete", details="user={}".format(username))
    return jsonify({"success": True})


@app.route("/", methods=["GET", "POST"])
def home():
    return redirect("/dashboard", code=302)


@app.route("/dashboard", methods=["GET", "POST"])
@require_role("viewer")
def dashboard():
    route_start = time.perf_counter()
    trace_dashboard_load("dashboard route start")
    c = dashboard_c()
    trace_dashboard_load(
        "dashboard route controller complete",
        elapsed_ms=(time.perf_counter() - route_start) * 1000,
    )
    rendered = dashboard_v(c).render()
    trace_dashboard_load(
        "dashboard route render complete",
        elapsed_ms=(time.perf_counter() - route_start) * 1000,
    )
    return rendered


@app.route("/logs", methods=["GET", "POST"])
@require_role("viewer")
def log():
    instance = request.args.get("instance")
    page = request.args.get("page") or 1
    per_page = request.args.get("per_page") or 100
    c = logs_c(instance, page, per_page)
    return logs_v(c).render()


@app.route("/players", methods=["GET", "POST"])
@require_role("viewer")
def players():
    c = players_c(request.args.get("filter"), request.args.get("page"), request.args.get("per_page"))
    return players_v(c).render()


@app.route("/stats", methods=["GET", "POST"])
@require_role("viewer")
def stats():
    c = stats_c(request.args.get("instance"))
    return stats_v(c).render()


@app.route("/instance", methods=["GET", "POST"])
@require_role("viewer")
def instance():
    c = instance_c(request.args.get("instance"))
    return instance_v(c).render()


@app.route("/instance/<instance_name>/command", methods=["POST"])
@require_role("admin")
def instance_command(instance_name):
    data = request.get_json() or {}
    cmd = data.get("command")
    if cmd not in ["start", "stop", "restart"]:
        return {"error": "Unknown command."}, 400

    actual_cmd = cmd
    if actual_cmd in ["stop", "restart"]:
        cli_cmd = ["mbii", "-i", instance_name, actual_cmd, "--force"]
    else:
        cli_cmd = ["mbii", "-i", instance_name, actual_cmd]

    try:
        result = subprocess.run(cli_cmd, capture_output=True, text=True, timeout=30)
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        output = output.strip()

        _audit("instance_command", instance_name, f"cmd={actual_cmd}; rc={result.returncode}")

        if result.returncode == 0:
            return {"output": output or f"Instance {instance_name} {cmd}ed."}

        return {"error": output or f"Failed to {cmd} instance {instance_name}."}, 500
    except Exception as e:
        _audit("instance_command_error", instance_name, str(e))
        return {"error": str(e)}, 500


@app.route("/instance/<instance_name>/command_async", methods=["POST"])
@require_role("admin")
def instance_command_async(instance_name):
    data = request.get_json() or {}
    cmd = data.get("command")
    if cmd not in ["start", "stop", "restart"]:
        return {"error": "Unknown command."}, 400

    actual_cmd = cmd

    if actual_cmd in ["stop", "restart"]:
        cli_cmd = ["mbii", "-i", instance_name, actual_cmd, "--force"]
    else:
        cli_cmd = ["mbii", "-i", instance_name, actual_cmd]

    try:
        def detached_process():
            pid = os.fork()
            if pid > 0:
                return

            os.setsid()

            pid = os.fork()
            if pid > 0:
                os._exit(0)

            with open(os.devnull, "r") as devnull_in:
                with open(os.devnull, "w") as devnull_out:
                    os.dup2(devnull_in.fileno(), 0)
                    os.dup2(devnull_out.fileno(), 1)
                    os.dup2(devnull_out.fileno(), 2)

            os.execvp(cli_cmd[0], cli_cmd)

        detached_process()
        _audit("instance_command_async", instance_name, f"cmd={actual_cmd}")
        return {"output": f"Instance {instance_name} {cmd} initiated.", "async": True}

    except Exception as e:
        _audit("instance_command_async_error", instance_name, str(e))
        return {"error": str(e)}, 500


@app.route("/chat", methods=["GET", "POST"])
@require_role("viewer")
def chat():
    instance = request.args.get("instance")
    c = chat_c(instance)
    return chat_v(c).render()


@app.route("/mod", methods=["GET"])
@require_role("mod")
def mod():
    instance = request.args.get("instance")
    c = mod_c(instance)
    return mod_v(c).render()


@app.route("/mod/map", methods=["POST"])
@require_role("mod")
def mod_map():
    data = request.get_json() or {}
    success, msg = mod_c.change_map(data["instance"], data["mapname"])
    if success:
        _audit("mod_map", data.get("instance"), data.get("mapname", ""))
    return {"success": success, "error": None if success else msg}


@app.route("/mod/mode", methods=["POST"])
@require_role("mod")
def mod_mode():
    data = request.get_json() or {}
    success, msg = mod_c.change_mode(data["instance"], data["mode"])
    if success:
        _audit("mod_mode", data.get("instance"), data.get("mode", ""))
    return {"success": success, "error": None if success else msg}


@app.route("/mod/kick", methods=["POST"])
@require_role("mod")
def mod_kick():
    data = request.get_json() or {}
    success, msg = mod_c.kick_player(data["instance"], data["player_id"])
    if success:
        _audit("mod_kick", data.get("instance"), data.get("player_id", ""))
    return {"success": success, "error": None if success else msg}


@app.route("/mod/ban", methods=["POST"])
@require_role("mod")
def mod_ban():
    data = request.get_json() or {}
    success, msg = mod_c.ban_player(data["instance"], data["ip"])
    if success:
        _audit("mod_ban", data.get("instance"), data.get("ip", ""))
    return {"success": success, "error": None if success else msg}


@app.route("/mod/unban", methods=["POST"])
@require_role("mod")
def mod_unban():
    data = request.get_json() or {}
    success, msg = mod_c.unban_ip(data["instance"], data["ip"])
    if success:
        _audit("mod_unban", data.get("instance"), data.get("ip", ""))
    return {"success": success, "error": None if success else msg}


@app.route("/mod/tell", methods=["POST"])
@require_role("mod")
def mod_tell():
    data = request.get_json() or {}
    success, msg = mod_c.tell_player(data["instance"], data["player_id"], data["message"])
    if success:
        _audit("mod_tell", data.get("instance"), f"to={data.get('player_id', '')}")
    return {"success": success, "error": None if success else msg}


@app.route("/rcon", methods=["GET"])
@require_role("mod")
def rcon():
    instance = request.args.get("instance")
    c = rcon_c(instance)
    return rcon_v(c).render()


@app.route("/rcon/send", methods=["POST"])
@require_role("mod")
def rcon_send():
    data = request.get_json() or {}
    success, response = rcon_c.send_rcon(data["instance"], data["command"])
    if success:
        _audit("rcon_send", data.get("instance"), data.get("command", "")[:120])
    return {
        "success": success,
        "response": response if success else None,
        "error": None if success else response,
    }


@app.route("/config", methods=["GET"])
@require_role("admin")
def config():
    instance = request.args.get("instance")
    c = config_c(instance)
    return config_v(c).render()


@app.route("/config/save", methods=["POST"])
@require_role("admin")
def config_save():
    data = request.get_json() or {}
    success, msg = config_c.save_config(data["instance"], data["content"])
    if success:
        _audit("config_save", data.get("instance"), "saved")
    return {"success": success, "error": None if success else msg}


@app.route("/api/instances/summary", methods=["GET"])
@require_role("viewer")
def api_instances_summary():
    c = dashboard_c()
    return jsonify(c.controller_bag)


@app.route("/api/audit", methods=["GET"])
@require_role("admin")
def api_audit():
    conn = db().connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM web_audit ORDER BY added DESC LIMIT 200")
    rows = cur.fetchall()
    return jsonify(rows)


@app.route("/api/check_server/<instance_name>", methods=["GET"])
@require_role("viewer")
def check_server_status(instance_name):
    """Check if server is running by attempting UDP connection."""
    from mbiiez.instance import instance as MBInstance

    try:
        inst = MBInstance(instance_name)
        config = inst.config

        server_ip = config.get("server", {}).get("ip", "127.0.0.1")
        server_port = int(config.get("server", {}).get("port", 29070))

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)

        try:
            sock.sendto(b"", (server_ip, server_port))
            sock.close()
            return jsonify({"running": True, "error": None})
        except Exception:
            sock.close()
            return jsonify({"running": False, "error": None})

    except Exception as e:
        return jsonify({"running": False, "error": str(e)})


@app.route("/api/instance_status/<instance_name>", methods=["GET"])
@require_role("viewer")
def status_api(instance_name):
    from mbiiez.instance import instance as MBInstance

    try:
        inst = MBInstance(instance_name)
        status = inst.status()
        return jsonify(
            {
                "server_name": status.get("server_name", ""),
                "players_count": status.get("players_count", 0),
                "map": status.get("map", ""),
                "mode": status.get("mode", ""),
                "uptime": status.get("uptime", ""),
                "running": status.get("server_running", False),
                "error": None,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)})


app.register_blueprint(logs_api)
app.register_blueprint(chat_api)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=settings.web_service.port, use_reloader=False)
