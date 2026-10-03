from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import secrets
import socket
import subprocess
import time
from functools import wraps

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from mbiiez import settings
from mbiiez.api.client import Client, NodeError, nodes, selected_node, save_node, remove_node
from mbiiez.web.remote import controller as remote_controller, instance_admin, bansync, guidbans
from mbiiez.db import db

# Web Tools


# Controllers are API presentation adapters, including the local node.
chat_c = remote_controller("chat")
config_c = remote_controller("config")
dashboard_c = remote_controller("dashboard")
instance_c = remote_controller("instance")
logs_c = remote_controller("logs")
mod_c = remote_controller("mod")
players_c = remote_controller("players")
rcon_c = remote_controller("rcon")
stats_c = remote_controller("stats")
plugin_page_c = remote_controller("plugin_page")
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
from mbiiez.web.views.plugin_page import view as plugin_page_v


app = Flask(
    __name__,
    static_url_path="/assets",
    static_folder="mbiiez/web/static",
    template_folder="mbiiez/web/templates",
)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def _load_secret_key():
    """The key that signs login cookies. Anyone who knows it can forge a
    session, so it must never be a value from the source: use
    MBIIEZ_WEB_SECRET_KEY if set, else a random key generated once and kept
    beside the users file (owner-only)."""
    key = os.environ.get("MBIIEZ_WEB_SECRET_KEY", "").strip()
    if key:
        return key

    key_dir = os.path.dirname(settings.web_service.users_file or "") or os.path.dirname(os.path.abspath(__file__))
    key_file = os.path.join(key_dir, "web_secret.key")
    try:
        with open(key_file, "r", encoding="utf-8") as f:
            key = f.read().strip()
    except FileNotFoundError:
        key = ""
    if len(key) < 32:
        key = secrets.token_hex(32)
        os.makedirs(key_dir, exist_ok=True)
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)
    return key


app.secret_key = _load_secret_key()


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


def _password_fingerprint(stored_password):
    return hashlib.sha256(("mbiiez-session:" + str(stored_password)).encode("utf-8")).hexdigest()[:32]


def _set_session_auth(username, role):
    session["mbiiez_user"] = username
    session["mbiiez_role"] = _normalize_role(role)
    user = _load_users().get(username) or {}
    session["mbiiez_pw"] = _password_fingerprint(user.get("password", ""))


def _validate_session_user():
    """The logged-in user's current role from the users file, or None if the
    session is no longer valid (user deleted or password changed), in which
    case it's cleared. The role stored in the cookie is never trusted."""
    user = _load_users().get(_session_user())
    if not user or session.get("mbiiez_pw") != _password_fingerprint(user.get("password", "")):
        _clear_session_auth()
        return None
    session["mbiiez_role"] = user.get("role", "viewer")
    return user.get("role", "viewer")


def _clear_session_auth():
    session.pop("mbiiez_user", None)
    session.pop("mbiiez_role", None)
    session.pop("mbiiez_pw", None)


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
        "/nodes",
        "/config",
        "/instance/",
        "/instances",
        "/api/audit",
        "/admin",
    ]

    mod_prefixes = [
        "/mod",
        "/rcon",
        "/bans",
        "/guidbans",
    ]

    if path.startswith("/instance/") and path.endswith("/command"):
        return "admin"

    if path.startswith("/instance/") and path.endswith("/command_async"):
        return "admin"

    if path == "/config/save":
        return "admin"

    if path == "/config/sync_smod_admin":
        return "admin"

    if path.startswith("/rcon") or path.startswith("/nodes"):
        return "admin"

    if path == "/chat/send":
        return "mod"

    if path.startswith("/admin"):
        return "admin"

    if path.startswith("/plugin/") or path.startswith("/plugins/") or path.startswith("/instance-plugins"):
        return "admin"

    if any(path.startswith(prefix) for prefix in admin_prefixes):
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


def _node_metadata():
    if not hasattr(g, "node_metadata"):
        g.node_metadata = {"instances": [], "plugins": {}, "global": []}
        g.node_metadata = Client().call("GET", "menus") if _role_allows(_current_role(), "admin") else {
            "instances": Client().call("GET", "instances"), "plugins": {}, "global": []}
    return g.node_metadata


def _list_instances_cached():
    try:
        return _node_metadata()["instances"]
    except NodeError:
        return []


def _global_menus_cached():
    try:
        return _node_metadata()["global"]
    except NodeError:
        return []


def _plugin_menus_cached():
    try:
        return _node_metadata()["plugins"]
    except NodeError:
        return {}


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
        role = _validate_session_user()
        if role:
            g.current_user = _session_user()
            g.current_role = _normalize_role(role)

    required_role = _required_role_for_path(path, request.method)

    if required_role is None:
        return None

    if settings.web_service.auth_enabled and not _is_logged_in():
        return _auth_failed_response(path)

    if not _role_allows(_current_role(), required_role):
        return jsonify({"error": "Insufficient permissions"}), 403

    return None


@app.before_request
def select_api_node():
    data = nodes()
    chosen = request.headers.get("X-MBIIEZ-Node") or request.args.get("node") or request.form.get("node") or session.get("mbiiez_node") or next(iter(data), "na")
    if chosen not in data and data:
        return jsonify(error="Unknown node"), 404
    g.node_id = chosen
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and _is_logged_in():
        token = request.headers.get("X-MBIIEZ-CSRF") or request.form.get("csrf_token", "")
        if not secrets.compare_digest(token, session["csrf_token"]):
            return jsonify(error="Invalid CSRF token; reload the page"), 403
    # GET navigation may choose a default; JS commands always carry the page's node ID.
    if request.method == "GET" and request.args.get("node") and chosen in data:
        session["mbiiez_node"] = chosen


@app.errorhandler(NodeError)
def node_error(error):
    if request.method == "GET" and not _is_api_request(request.path) and not request.path.endswith("/data"):
        g.node_metadata = {"instances": [], "plugins": {}, "global": []}
        return render_template("pages/node-offline.html", error=str(error)), 502
    return jsonify(error=str(error)), 502


@app.route("/nodes")
@require_role("admin")
def nodes_page():
    def check(item):
        identifier, node = item
        try:
            info = Client(identifier).call("GET", "info")
            status = "Online" if info.get("api_version") == 1 else "API version mismatch"
            version = info.get("version", "")[:12]
        except NodeError:
            status, version = "Offline", ""
        return {"id": identifier, "name": node["name"], "url": node["url"], "status": status, "version": version}
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(check, nodes().items()))
    return render_template("pages/nodes.html", node_statuses=statuses)


@app.route("/nodes/save", methods=["POST"])
@require_role("admin")
def nodes_save():
    data = request.form
    try:
        save_node(data.get("id", ""), data.get("name", ""), data.get("url", ""), data.get("key", ""))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    _audit("node_save", details=data.get("id", ""))
    return redirect("/nodes")


@app.route("/nodes/<identifier>/test", methods=["POST"])
@require_role("admin")
def nodes_test(identifier):
    if identifier not in nodes():
        abort(404)
    return jsonify(Client(identifier).call("GET", "info"))


@app.route("/nodes/<identifier>/delete", methods=["POST"])
@require_role("admin")
def nodes_delete(identifier):
    remove_node(identifier)
    _audit("node_delete", details=identifier)
    return redirect("/nodes")


@app.context_processor
def include_instances_and_auth():
    users = _load_users() if settings.web_service.auth_enabled else {}

    return dict(
        csrf_token=session.get("csrf_token", ""),
        nodes={identifier: {"name": node["name"]} for identifier, node in nodes().items()},
        selected_node=getattr(g, "node_id", "na"),
        instances=_list_instances_cached(),
        current_user=_current_user(),
        current_role=_current_role(),
        can_mod=_role_allows(_current_role(), "mod"),
        can_admin=_role_allows(_current_role(), "admin"),
        setup_required=_setup_required(),
        users_count=len(users),
        plugin_menus=_plugin_menus_cached() if _role_allows(_current_role(), "admin") else {},
        global_plugin_menus=_global_menus_cached() if _role_allows(_current_role(), "admin") else [],
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


LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SECONDS = 15 * 60
_login_failures = {}


def _login_blocked(ip):
    now = time.time()
    recent = [t for t in _login_failures.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    _login_failures[ip] = recent
    return len(recent) >= LOGIN_MAX_FAILURES


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
        ip = request.remote_addr or ""
        username = str(request.form.get("username", "")).strip()
        password = str(request.form.get("password", "")).strip()

        if _login_blocked(ip):
            error = "Too many failed logins. Try again in 15 minutes."
            return render_template("pages/login.html", error=error, next_path=next_path), 429

        ok, role = _authenticate_credentials(username, password)
        if ok:
            _login_failures.pop(ip, None)
            _set_session_auth(username, role)
            return redirect(_safe_next_path(request.form.get("next")), code=302)

        _login_failures.setdefault(ip, []).append(time.time())
        _audit("login_failed", details="user={}".format(username))
        error = "Invalid username or password."

    return render_template("pages/login.html", error=error, next_path=next_path)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    response = redirect("/login", code=302)
    response.delete_cookie(app.config.get("SESSION_COOKIE_NAME", "session"))
    return response


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
    c = dashboard_c()
    return dashboard_v(c).render()


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
@app.route("/instance/<instance_name>/command_async", methods=["POST"])
@require_role("admin")
def instance_command(instance_name):
    data = request.get_json() or {}
    command = data.get("command")
    if command not in ("start", "stop", "restart"):
        return jsonify(error="Unknown command"), 400
    return jsonify(Client().call("POST", "instances/" + instance_name + "/" + command,
                                 {"force": data.get("force", False)})), 202


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


@app.route("/mod/plugin_action", methods=["POST"])
@require_role("mod")
def mod_plugin_action():
    data = request.get_json(silent=True) or {}
    instance_name = str(data.get("instance", ""))
    plugin_name = str(data.get("plugin", ""))
    action_name = str(data.get("action", ""))
    success, msg = mod_c.run_plugin_action(instance_name, plugin_name, action_name, data.get("data") or {})
    if success:
        _audit("mod_plugin_action", instance_name, f"plugin={plugin_name};action={action_name}")
    return jsonify({"success": success, "message": msg})


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
    success, msg = bansync.add_ban(data.get("ip"), by="{} (web, from {})".format(_current_user(), data.get("instance", "")))
    if success:
        _audit("mod_ban", data.get("instance"), data.get("ip", ""))
    return {"success": success, "error": None if success else msg}


@app.route("/mod/unban", methods=["POST"])
@require_role("mod")
def mod_unban():
    data = request.get_json() or {}
    success, msg = bansync.remove_ban(data.get("ip"))
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


@app.route("/bans", methods=["GET"])
@require_role("mod")
def bans_page():
    bans = bansync.list_bans()
    for b in bans:
        b["added_text"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(b.get("added", 0))) if b.get("added") else ""
    return render_template("pages/bans.html", view_bag={"bans": bans})


@app.route("/bans/add", methods=["POST"])
@require_role("mod")
def bans_add():
    data = request.get_json(silent=True) or {}
    success, msg = bansync.add_ban(data.get("ip"), str(data.get("note", ""))[:200], by="{} (web)".format(_current_user()))
    if success:
        _audit("ban_add", details="{} {}".format(data.get("ip", ""), data.get("note", ""))[:200])
    return {"success": success, "message": msg, "error": None if success else msg}


@app.route("/bans/remove", methods=["POST"])
@require_role("mod")
def bans_remove():
    data = request.get_json(silent=True) or {}
    success, msg = bansync.remove_ban(data.get("ip"))
    if success:
        _audit("ban_remove", details=str(data.get("ip", "")))
    return {"success": success, "message": msg, "error": None if success else msg}


@app.route("/bans/note", methods=["POST"])
@require_role("mod")
def bans_note():
    data = request.get_json(silent=True) or {}
    success, msg = bansync.set_note(data.get("ip"), data.get("note", ""))
    return {"success": success, "message": msg, "error": None if success else msg}


def _when(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else ""


@app.route("/guidbans", methods=["GET"])
@require_role("mod")
def guidbans_page():
    bans = guidbans.list_bans()
    for b in bans:
        b["added_text"] = _when(b["added"])
        b["last_drop_text"] = _when(b["last_drop"])
    return render_template("pages/guidbans.html", view_bag={
        "bans": bans,
        "total_drops": sum(b["drops"] for b in bans),
    })


@app.route("/guidbans/add", methods=["POST"])
@require_role("mod")
def guidbans_add():
    data = request.get_json(silent=True) or {}
    note = str(data.get("note", "")).strip() or "by {} (web)".format(_current_user())
    success, msg = guidbans.add_ban(data.get("guid"), note[:200])
    if success:
        _audit("guidban_add", details="{} {}".format(data.get("guid", ""), note)[:200])
    return {"success": success, "message": msg, "error": None if success else msg}


@app.route("/guidbans/remove", methods=["POST"])
@require_role("mod")
def guidbans_remove():
    data = request.get_json(silent=True) or {}
    success, msg = guidbans.remove_ban(data.get("guid"))
    if success:
        _audit("guidban_remove", details=str(data.get("guid", "")))
    return {"success": success, "message": msg, "error": None if success else msg}


@app.route("/guidbans/note", methods=["POST"])
@require_role("mod")
def guidbans_note():
    data = request.get_json(silent=True) or {}
    success, msg = guidbans.set_note(data.get("guid"), data.get("note", ""))
    return {"success": success, "message": msg, "error": None if success else msg}


@app.route("/rcon", methods=["GET"])
@require_role("admin")
def rcon():
    instance = request.args.get("instance")
    c = rcon_c(instance)
    return rcon_v(c).render()


@app.route("/rcon/send", methods=["POST"])
@require_role("admin")
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


@app.route("/instance-plugins", methods=["GET"])
@require_role("admin")
def instance_plugins():
    instance = request.args.get("instance", "")
    if instance not in _list_instances_cached():
        abort(404)
    return render_template("pages/plugins.html", view_bag=config_c.plugins_page(instance))


@app.route("/plugins/<plugin_name>/<slug>", methods=["GET"])
@require_role("admin")
def global_plugin_page(plugin_name, slug):
    return render_template("pages/plugin.html", view_bag=plugin_page_c.global_page(plugin_name, slug))


@app.route("/plugins/<plugin_name>/<slug>/action/<action_name>", methods=["POST"])
@require_role("admin")
def global_plugin_action(plugin_name, slug, action_name):
    data = request.get_json(silent=True) or {}
    success, message = plugin_page_c.run_global_action(plugin_name, slug, action_name, data)
    if success:
        _audit("plugin_action", None, f"plugin={plugin_name};slug={slug};action={action_name}")
    return jsonify({"success": success, "message": message})


@app.route("/plugin/<instance_name>/<slug>", methods=["GET"])
@require_role("admin")
def plugin_page(instance_name, slug):
    c = plugin_page_c(instance_name, slug)
    return plugin_page_v(c).render()


@app.route("/plugin/<instance_name>/<slug>/action/<action_name>", methods=["POST"])
@require_role("admin")
def plugin_action(instance_name, slug, action_name):
    data = request.get_json(silent=True) or {}
    success, message = plugin_page_c.run_action(instance_name, slug, action_name, data)
    if success:
        _audit("plugin_action", instance_name, f"slug={slug};action={action_name}")
    return jsonify({"success": success, "message": message})


@app.route("/config/save", methods=["POST"])
@require_role("admin")
def config_save():
    data = request.get_json() or {}
    success, msg = config_c.save_config(data["instance"], data["content"])
    if success:
        _audit("config_save", data.get("instance"), "saved")
    return {"success": success, "error": None if success else msg}


def _forget_instance_lists():
    g.pop("node_metadata", None)


@app.route("/instances/new", methods=["GET"])
@require_role("admin")
def instance_new_page():
    return render_template("pages/instance-new.html", view_bag=instance_admin.wizard_bag())


@app.route("/instances/create", methods=["POST"])
@require_role("admin")
def instance_create():
    data = request.get_json(silent=True) or {}
    success, msg = instance_admin.create_instance(data)
    if success:
        _forget_instance_lists()
        _audit("instance_create", str(data.get("name", "")).lower(),
               f"port={data.get('port')};source={data.get('source') or 'template'}")
    return jsonify({"success": success, "message": msg})


@app.route("/instances/<instance_name>/running", methods=["GET"])
@require_role("admin")
def instance_running(instance_name):
    return jsonify({"running": instance_admin.is_running(instance_name)})


@app.route("/instances/<instance_name>/delete", methods=["POST"])
@require_role("admin")
def instance_delete(instance_name):
    data = request.get_json(silent=True) or {}
    # Server-side half of the "type the name to confirm" check.
    if str(data.get("confirm", "")).strip().lower() != instance_name.lower():
        return jsonify({"success": False, "message": "Confirmation didn't match the instance name."})
    success, msg = instance_admin.delete_instance(instance_name)
    if success:
        _forget_instance_lists()
        _audit("instance_delete", instance_name, msg)
    return jsonify({"success": success, "message": msg})


@app.route("/config/sync_smod_admin", methods=["POST"])
@require_role("admin")
def config_sync_smod_admin():
    data = request.get_json() or {}
    source_instance = data.get("source_instance")
    # admin_keys (list) is the current shape - a single admin's "Sync to
    # instances..." button sends a one-item list, the "Sync all admins..."
    # button sends every smod.admin_N key at once. admin_key (singular,
    # string) is accepted too for any older client still sending it.
    admin_keys = data.get("admin_keys")
    if admin_keys is None and data.get("admin_key"):
        admin_keys = [data["admin_key"]]
    admin_keys = admin_keys or []
    target_instances = data.get("target_instances") or []
    success, msg = config_c.sync_smod_admins(source_instance, admin_keys, target_instances)
    if success:
        _audit(
            "config_sync_smod_admin",
            source_instance,
            f"admins={','.join(admin_keys)};targets={','.join(target_instances)}",
        )
    return {"success": success, "message": msg}


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


@app.route("/api/check_server/<instance_name>")
@require_role("viewer")
def check_server_status(instance_name):
    status = Client().call("GET", "instances/" + instance_name + "/status")
    return jsonify(running=status.get("server_running", False), error=None)


@app.route("/api/instance_status/<instance_name>")
@require_role("viewer")
def status_api(instance_name):
    status = Client().call("GET", "instances/" + instance_name + "/status")
    return jsonify(dict(status, running=status.get("server_running", False), error=None))


@app.route("/logs/data")
@require_role("viewer")
def logs_data():
    return jsonify(Client().call("GET", "logs", params=request.args.to_dict()))


@app.route("/chat/data")
@require_role("viewer")
def chat_data():
    return jsonify(Client().call("GET", "chat", params=request.args.to_dict()))


@app.route("/chat/send", methods=["POST"])
@require_role("mod")
def chat_send():
    return jsonify(Client().call("POST", "chat", request.get_json() or {}))


@app.route("/api/web/restart", methods=["POST"])
@require_role("admin")
def web_restart():
    """Restart the mbii-web systemd service."""
    _audit("web_restart", details="requested by {}".format(_current_user()))
    try:
        subprocess.Popen(
            ["systemctl", "restart", "mbii-web"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return jsonify({"success": True, "message": "Web service restart initiated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/web/update", methods=["POST"])
@require_role("admin")
def web_update():
    """git pull the mbiiez repo; restart the web service only if files changed."""
    _audit("web_update", details="requested by {}".format(_current_user()))
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = (result.stdout or "").strip()
        changed = result.returncode == 0 and "Already up to date." not in output
        if changed:
            subprocess.Popen(
                ["systemctl", "restart", "mbii-web"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return jsonify({
            "success": result.returncode == 0,
            "output": output,
            "changed": changed,
            "restarted": changed,
            "error": (result.stderr or "").strip() if result.returncode != 0 else None,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=settings.web_service.port, use_reloader=False)
