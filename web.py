from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from functools import wraps
import storage
import playlist_mgr
from Config import ADMIN_PASSWORD, CHANNEL_TAG, GROUP_LINK, OWNER_IDS

app = Flask(__name__)
app.secret_key = "ls_secret_2026_admin"

# ─────────────────────────────────────────────
#  Auth decorator
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
#  Base HTML template
# ─────────────────────────────────────────────

BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{ title }} — LS Admin</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh;display:flex}
  a{color:#58a6ff;text-decoration:none}
  a:hover{text-decoration:underline}

  /* Sidebar */
  .sidebar{width:230px;min-height:100vh;background:#161b22;border-right:1px solid #30363d;padding:0;display:flex;flex-direction:column;flex-shrink:0}
  .sidebar-header{padding:20px 16px 14px;border-bottom:1px solid #30363d}
  .sidebar-header h2{font-size:15px;color:#58a6ff;font-weight:700;letter-spacing:.3px}
  .sidebar-header p{font-size:11px;color:#8b949e;margin-top:3px}
  .sidebar nav{padding:10px 0;flex:1}
  .nav-section{font-size:10px;color:#484f58;font-weight:700;text-transform:uppercase;letter-spacing:.8px;padding:10px 16px 4px}
  .nav-link{display:flex;align-items:center;gap:10px;padding:9px 16px;color:#8b949e;font-size:13px;transition:all .15s;border-left:3px solid transparent}
  .nav-link:hover,.nav-link.active{color:#e6edf3;background:#1f2937;border-left-color:#58a6ff;text-decoration:none}
  .nav-link .icon{font-size:15px;width:20px;text-align:center}
  .sidebar-footer{padding:14px 16px;border-top:1px solid #30363d;font-size:11px;color:#8b949e}

  /* Main */
  .main{flex:1;padding:28px;overflow-y:auto;max-width:100%}
  .page-header{margin-bottom:24px}
  .page-title{font-size:22px;font-weight:700;margin-bottom:4px}
  .page-sub{font-size:13px;color:#8b949e}

  /* Cards */
  .card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px;margin-bottom:20px}
  .card-title{font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.7px;margin-bottom:16px;display:flex;align-items:center;gap:8px}
  .card-title span{flex:1}

  /* Stats grid */
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:24px}
  .stat-card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px 16px;text-align:center;transition:border .15s}
  .stat-card:hover{border-color:#58a6ff}
  .stat-num{font-size:30px;font-weight:700;color:#58a6ff;line-height:1}
  .stat-label{font-size:11px;color:#8b949e;margin-top:6px}
  .stat-sub{font-size:10px;color:#484f58;margin-top:2px}

  /* Table */
  .table-wrap{overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;padding:10px 12px;color:#8b949e;font-weight:600;border-bottom:1px solid #30363d;font-size:11px;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
  td{padding:10px 12px;border-bottom:1px solid #21262d;vertical-align:middle}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:#1c2128}
  .badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
  .badge-green{background:#0d4429;color:#3fb950}
  .badge-red{background:#3d1212;color:#f85149}
  .badge-blue{background:#0c2d6b;color:#58a6ff}
  .badge-gray{background:#21262d;color:#8b949e}
  .badge-purple{background:#2d1c6b;color:#a371f7}
  .badge-orange{background:#3d2000;color:#f0883e}

  /* Forms */
  .form-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:14px}
  input,select,textarea{background:#0d1117;border:1px solid #30363d;color:#e6edf3;border-radius:6px;padding:8px 12px;font-size:13px;outline:none;transition:border .15s;font-family:inherit}
  input:focus,select:focus,textarea:focus{border-color:#58a6ff;box-shadow:0 0 0 3px rgba(88,166,255,.1)}
  input[type=text],input[type=password],input[type=number],input[type=url]{width:100%}
  textarea{width:100%;resize:vertical;min-height:60px}
  .form-group{display:flex;flex-direction:column;gap:5px;flex:1;min-width:140px}
  label{font-size:12px;color:#8b949e;font-weight:500}
  .btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s;text-decoration:none}
  .btn:hover{text-decoration:none;opacity:.9}
  .btn-primary{background:#238636;color:#fff}
  .btn-primary:hover{background:#2ea043}
  .btn-danger{background:#da3633;color:#fff}
  .btn-danger:hover{background:#f85149}
  .btn-secondary{background:#21262d;color:#e6edf3;border:1px solid #30363d}
  .btn-secondary:hover{background:#30363d}
  .btn-warning{background:#9e6a03;color:#fff}
  .btn-warning:hover{background:#d4a217}
  .btn-info{background:#0c2d6b;color:#58a6ff;border:1px solid #1f52a0}
  .btn-info:hover{background:#1a3c7c}
  .btn-sm{padding:4px 10px;font-size:12px}

  /* Alerts */
  .alert{padding:12px 16px;border-radius:8px;font-size:13px;margin-bottom:16px;display:flex;align-items:center;gap:10px}
  .alert-success{background:#0d4429;border:1px solid #238636;color:#3fb950}
  .alert-error{background:#3d1212;border:1px solid #da3633;color:#f85149}
  .alert-info{background:#0c2d6b;border:1px solid #1f6feb;color:#58a6ff}

  /* Login */
  .login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0d1117;width:100%}
  .login-card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:40px;width:360px}
  .login-card h1{font-size:20px;margin-bottom:6px;color:#e6edf3}
  .login-card p{color:#8b949e;font-size:13px;margin-bottom:24px}
  .login-card input{width:100%;margin-bottom:12px}

  /* URL display */
  .url-box{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:10px 12px;font-family:monospace;font-size:12px;color:#8b949e;word-break:break-all;margin-top:8px}
  .url-text{font-family:monospace;font-size:11px;color:#8b949e;word-break:break-all}

  /* Toggle switch */
  .toggle-wrap{display:flex;align-items:center;gap:14px}
  .toggle{position:relative;width:44px;height:24px;flex-shrink:0}
  .toggle input{opacity:0;width:0;height:0}
  .slider{position:absolute;inset:0;background:#21262d;border-radius:24px;cursor:pointer;transition:.3s;border:1px solid #30363d}
  .slider:before{position:absolute;content:"";height:16px;width:16px;left:3px;bottom:3px;background:#8b949e;border-radius:50%;transition:.3s}
  input:checked + .slider{background:#238636;border-color:#2ea043}
  input:checked + .slider:before{transform:translateX(20px);background:#fff}
  .toggle-label{font-size:13px;color:#e6edf3;font-weight:500}

  /* Status dot */
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
  .dot-green{background:#3fb950}
  .dot-red{background:#f85149}
  .dot-yellow{background:#d4a217}

  /* Divider */
  .divider{height:1px;background:#30363d;margin:16px 0}

  @media(max-width:768px){
    body{flex-direction:column}
    .sidebar{width:100%;min-height:auto}
    .main{padding:16px}
    .stats{grid-template-columns:repeat(2,1fr)}
  }
</style>
</head>
<body>
{% if show_sidebar %}
<div class="sidebar">
  <div class="sidebar-header">
    <h2>📡 LS Admin</h2>
    <p>@{{ tag }}</p>
  </div>
  <nav>
    <div class="nav-section">Main</div>
    <a class="nav-link {{ 'active' if active=='dashboard' }}" href="/"><span class="icon">🏠</span>Dashboard</a>
    <div class="nav-section">Users</div>
    <a class="nav-link {{ 'active' if active=='dosts' }}" href="/dosts"><span class="icon">👥</span>Dost List</a>
    <a class="nav-link {{ 'active' if active=='premium' }}" href="/premium"><span class="icon">💎</span>Premium</a>
    <a class="nav-link {{ 'active' if active=='verified' }}" href="/verified"><span class="icon">✅</span>Verified Users</a>
    <div class="nav-section">Content</div>
    <a class="nav-link {{ 'active' if active=='channels' }}" href="/channels"><span class="icon">📺</span>Channels</a>
    <a class="nav-link {{ 'active' if active=='playlist' }}" href="/playlist"><span class="icon">🔗</span>Playlist</a>
    <div class="nav-section">System</div>
    <a class="nav-link {{ 'active' if active=='settings' }}" href="/settings"><span class="icon">⚙️</span>Settings</a>
  </nav>
  <div class="sidebar-footer">
    <a href="/logout" class="btn btn-secondary btn-sm" style="width:100%;justify-content:center">🚪 Logout</a>
  </div>
</div>
{% endif %}
<div class="{{ 'main' if show_sidebar else 'login-wrap' }}">
  {% for msg in get_flashed_messages(category_filter=['success']) %}
    <div class="alert alert-success">✅ {{ msg }}</div>
  {% endfor %}
  {% for msg in get_flashed_messages(category_filter=['error']) %}
    <div class="alert alert-error">❌ {{ msg }}</div>
  {% endfor %}
  {% for msg in get_flashed_messages(category_filter=['info']) %}
    <div class="alert alert-info">ℹ️ {{ msg }}</div>
  {% endfor %}
  {% block content %}{% endblock %}
</div>
</body>
</html>
"""

# ─────────────────────────────────────────────
#  Login / Logout
# ─────────────────────────────────────────────

LOGIN_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="login-card">
  <h1>🔐 Admin Login</h1>
  <p>LittleSingham Bot — Admin Panel</p>
  {% for msg in get_flashed_messages(category_filter=['error']) %}
    <div class="alert alert-error">❌ {{ msg }}</div>
  {% endfor %}
  <form method="POST">
    <label>Password</label>
    <input type="password" name="password" placeholder="Enter admin password" autofocus required style="margin-top:6px"/>
    <button class="btn btn-primary" style="width:100%;justify-content:center;margin-top:12px">Login →</button>
  </form>
</div>
""")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Wrong password.", "error")
    return render_template_string(LOGIN_TMPL, title="Login", show_sidebar=False, tag=CHANNEL_TAG)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    dosts    = storage.get_dosts()
    premium  = storage.get_all_premium()
    channels = storage.get_all_channels()
    verified = storage.get_all_verified() if hasattr(storage, "get_all_verified") else {}
    now = datetime.now()

    active_premium = sum(
        1 for v in premium.values()
        if datetime.fromisoformat(v["expiry"]) > now
    )
    active_verified = sum(
        1 for v in verified.values()
        if datetime.fromisoformat(v["expiry"]) > now
    ) if verified else 0
    verify_on = storage.is_verification_enabled()

    tmpl = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-header">
  <div class="page-title">🏠 Dashboard</div>
  <div class="page-sub">LittleSingham Bot — Admin Overview</div>
</div>

<div class="stats">
  <div class="stat-card">
    <div class="stat-num">{{ dost_count }}</div>
    <div class="stat-label">👥 Dosts</div>
  </div>
  <div class="stat-card">
    <div class="stat-num" style="color:#a371f7">{{ premium_count }}</div>
    <div class="stat-label">💎 Premium Active</div>
  </div>
  <div class="stat-card">
    <div class="stat-num" style="color:#3fb950">{{ verified_count }}</div>
    <div class="stat-label">✅ Verified Active</div>
  </div>
  <div class="stat-card">
    <div class="stat-num" style="color:#f0883e">{{ channel_count }}</div>
    <div class="stat-label">📺 Channels</div>
  </div>
  <div class="stat-card">
    <div class="stat-num" style="color:{{ '#3fb950' if verify_on else '#f85149' }};font-size:18px;padding-top:6px">
      {{ '🟢 ON' if verify_on else '🔴 OFF' }}
    </div>
    <div class="stat-label">🔐 Verification</div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">

<div class="card">
  <div class="card-title"><span>👥 Recent Dosts</span> <a href="/dosts" class="btn btn-secondary btn-sm">View All →</a></div>
  {% if dosts %}
  <div class="table-wrap">
  <table>
    <tr><th>Name</th><th>User ID</th><th>Date</th></tr>
    {% for uid, info in dosts.items() %}
    <tr>
      <td><strong>{{ info.username }}</strong></td>
      <td><span class="badge badge-blue">{{ uid }}</span></td>
      <td style="color:#8b949e;font-size:12px">{{ info.added_at[:10] }}</td>
    </tr>
    {% endfor %}
  </table>
  </div>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No dosts yet. <a href="/dosts">Add one →</a></p>
  {% endif %}
</div>

<div class="card">
  <div class="card-title"><span>💎 Premium Users</span> <a href="/premium" class="btn btn-secondary btn-sm">View All →</a></div>
  {% if premium_users %}
  <div class="table-wrap">
  <table>
    <tr><th>User ID</th><th>Status</th><th>Expires</th></tr>
    {% for uid, info in premium_users.items() %}
    <tr>
      <td><span class="badge badge-blue">{{ uid }}</span></td>
      <td>
        {% if info.active %}<span class="badge badge-green">Active</span>
        {% else %}<span class="badge badge-red">Expired</span>{% endif %}
      </td>
      <td style="font-size:12px;color:#8b949e">{{ info.expiry[:10] }}</td>
    </tr>
    {% endfor %}
  </table>
  </div>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No premium users yet.</p>
  {% endif %}
</div>

</div>

<div class="card">
  <div class="card-title"><span>🔗 Quick Actions</span></div>
  <div style="display:flex;gap:10px;flex-wrap:wrap">
    <a href="/dosts" class="btn btn-secondary">👥 Dosts</a>
    <a href="/premium" class="btn btn-secondary">💎 Premium</a>
    <a href="/verified" class="btn btn-secondary">✅ Verified</a>
    <a href="/channels" class="btn btn-secondary">📺 Channels</a>
    <a href="/playlist" class="btn btn-secondary">🔗 Playlist URL</a>
    <a href="/settings" class="btn btn-secondary">⚙️ Settings</a>
  </div>
</div>
""")

    # build premium summary
    premium_users = {}
    for uid, v in list(premium.items())[:5]:
        try:
            expiry = datetime.fromisoformat(v["expiry"])
            premium_users[uid] = {"expiry": v["expiry"], "active": expiry > now}
        except Exception:
            premium_users[uid] = {"expiry": v.get("expiry","?"), "active": False}

    return render_template_string(tmpl,
        title="Dashboard", active="dashboard", show_sidebar=True, tag=CHANNEL_TAG,
        dost_count=len(dosts), premium_count=active_premium,
        verified_count=active_verified, channel_count=len(channels),
        verify_on=verify_on, dosts=dosts, premium_users=premium_users,
    )

# ─────────────────────────────────────────────
#  Dosts
# ─────────────────────────────────────────────

DOSTS_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-header">
  <div class="page-title">👥 Dost List</div>
  <div class="page-sub">Add, view and remove registered Dosts</div>
</div>

<div class="card">
  <div class="card-title"><span>➕ Add New Dost</span></div>
  <form method="POST" action="/dosts/add">
    <div class="form-row">
      <div class="form-group">
        <label>User ID *</label>
        <input type="number" name="user_id" placeholder="e.g. 123456789" required/>
      </div>
      <div class="form-group">
        <label>Name / Username</label>
        <input type="text" name="username" placeholder="Display name"/>
      </div>
      <button class="btn btn-primary" style="align-self:flex-end">➕ Add Dost</button>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title"><span>👥 All Dosts ({{ dosts|length }})</span></div>
  {% if dosts %}
  <div class="table-wrap">
  <table>
    <tr><th>Name</th><th>User ID</th><th>Added By</th><th>Date</th><th>Action</th></tr>
    {% for uid, info in dosts.items() %}
    <tr>
      <td><strong>{{ info.username }}</strong></td>
      <td><span class="badge badge-blue">{{ uid }}</span></td>
      <td><span class="badge badge-gray">{{ info.added_by }}</span></td>
      <td style="color:#8b949e;font-size:12px">{{ info.added_at[:10] }}</td>
      <td>
        <form method="POST" action="/dosts/remove/{{ uid }}" style="display:inline" onsubmit="return confirm('Remove this dost?')">
          <button class="btn btn-danger btn-sm">🗑 Remove</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>
  </div>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No dosts registered yet.</p>
  {% endif %}
</div>
""")

@app.route("/dosts")
@login_required
def dosts():
    return render_template_string(DOSTS_TMPL,
        title="Dosts", active="dosts", show_sidebar=True, tag=CHANNEL_TAG,
        dosts=storage.get_dosts(),
    )

@app.route("/dosts/add", methods=["POST"])
@login_required
def dosts_add():
    try:
        uid      = int(request.form["user_id"])
        username = request.form.get("username", "").strip() or str(uid)
        storage.add_dost(uid, username, OWNER_IDS[0])
        flash(f"Dost '{username}' ({uid}) added successfully.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("dosts"))

@app.route("/dosts/remove/<uid>", methods=["POST"])
@login_required
def dosts_remove(uid):
    removed = storage.remove_dost(int(uid))
    if removed:
        flash(f"Dost {uid} removed.", "success")
    else:
        flash(f"Dost {uid} not found.", "error")
    return redirect(url_for("dosts"))

# ─────────────────────────────────────────────
#  Premium
# ─────────────────────────────────────────────

PREMIUM_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-header">
  <div class="page-title">💎 Premium Users</div>
  <div class="page-sub">Activate, extend or remove premium plans</div>
</div>

<div class="card">
  <div class="card-title"><span>➕ Add / Extend Premium</span></div>
  <form method="POST" action="/premium/add">
    <div class="form-row">
      <div class="form-group">
        <label>User ID *</label>
        <input type="number" name="user_id" placeholder="e.g. 123456789" required/>
      </div>
      <div class="form-group" style="max-width:200px">
        <label>Plan</label>
        <select name="days">
          <option value="7">1 Week (7 days)</option>
          <option value="15">15 Days</option>
          <option value="30" selected>1 Month (30 days)</option>
          <option value="90">3 Months</option>
          <option value="365">1 Year</option>
        </select>
      </div>
      <button class="btn btn-primary" style="align-self:flex-end">⚡ Activate</button>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title"><span>💎 All Premium Users ({{ users|length }})</span></div>
  {% if users %}
  <div class="table-wrap">
  <table>
    <tr><th>User ID</th><th>Status</th><th>Expires</th><th>Days Left</th><th>Action</th></tr>
    {% for uid, info in users.items() %}
    <tr>
      <td><span class="badge badge-blue">{{ uid }}</span></td>
      <td>
        {% if info.active %}<span class="badge badge-green">● Active</span>
        {% else %}<span class="badge badge-red">● Expired</span>{% endif %}
      </td>
      <td style="font-size:12px;color:#8b949e">{{ info.expiry[:10] }}</td>
      <td>
        {% if info.days_left > 0 %}<span class="badge badge-green">{{ info.days_left }}d</span>
        {% else %}<span class="badge badge-red">0d</span>{% endif %}
      </td>
      <td>
        <form method="POST" action="/premium/remove/{{ uid }}" style="display:inline" onsubmit="return confirm('Remove premium for {{ uid }}?')">
          <button class="btn btn-danger btn-sm">🗑 Remove</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>
  </div>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No premium users yet.</p>
  {% endif %}
</div>
""")

@app.route("/premium")
@login_required
def premium():
    raw   = storage.get_all_premium()
    now   = datetime.now()
    users = {}
    for uid, v in raw.items():
        try:
            expiry = datetime.fromisoformat(v["expiry"])
            delta  = expiry - now
            users[uid] = {"expiry": v["expiry"], "active": expiry > now, "days_left": max(0, delta.days)}
        except Exception:
            users[uid] = {"expiry": v.get("expiry","?"), "active": False, "days_left": 0}
    return render_template_string(PREMIUM_TMPL,
        title="Premium", active="premium", show_sidebar=True, tag=CHANNEL_TAG, users=users,
    )

@app.route("/premium/add", methods=["POST"])
@login_required
def premium_add():
    try:
        uid   = int(request.form["user_id"])
        days  = int(request.form["days"])
        expiry = storage.add_premium(uid, days)
        flash(f"Premium activated for user {uid} — expires {expiry.strftime('%d-%m-%Y')}", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("premium"))

@app.route("/premium/remove/<uid>", methods=["POST"])
@login_required
def premium_remove(uid):
    removed = storage.remove_premium(int(uid))
    if removed:
        flash(f"Premium removed for user {uid}.", "success")
    else:
        flash(f"User {uid} not found in premium list.", "error")
    return redirect(url_for("premium"))

# ─────────────────────────────────────────────
#  Verified Users
# ─────────────────────────────────────────────

VERIFIED_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-header">
  <div class="page-title">✅ Verified Users</div>
  <div class="page-sub">Manually add, view and remove verified users</div>
</div>

<div class="card">
  <div class="card-title"><span>➕ Add / Grant Verification</span></div>
  <form method="POST" action="/verified/add">
    <div class="form-row">
      <div class="form-group">
        <label>User ID *</label>
        <input type="number" name="user_id" placeholder="e.g. 123456789" required/>
      </div>
      <div class="form-group">
        <label>Name</label>
        <input type="text" name="name" placeholder="Display name"/>
      </div>
      <div class="form-group" style="max-width:200px">
        <label>Duration</label>
        <select name="hours">
          <option value="4">4 Hours (default)</option>
          <option value="24">24 Hours</option>
          <option value="168">7 Days</option>
          <option value="720" selected>30 Days</option>
          <option value="8760">1 Year</option>
          <option value="438000">Permanent (50yr)</option>
        </select>
      </div>
      <button class="btn btn-primary" style="align-self:flex-end">✅ Grant Access</button>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title"><span>✅ All Verified Users ({{ users|length }})</span></div>
  {% if users %}
  <div class="table-wrap">
  <table>
    <tr><th>Name</th><th>User ID</th><th>Status</th><th>Expires</th><th>Action</th></tr>
    {% for uid, info in users.items() %}
    <tr>
      <td><strong>{{ info.name }}</strong></td>
      <td><span class="badge badge-blue">{{ uid }}</span></td>
      <td>
        {% if info.active %}<span class="badge badge-green">● Active</span>
        {% else %}<span class="badge badge-red">● Expired</span>{% endif %}
      </td>
      <td style="font-size:12px;color:#8b949e">{{ info.expiry[:16].replace('T',' ') }}</td>
      <td>
        <form method="POST" action="/verified/remove/{{ uid }}" style="display:inline" onsubmit="return confirm('Revoke verification for {{ uid }}?')">
          <button class="btn btn-danger btn-sm">🗑 Revoke</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>
  </div>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No verified users yet.</p>
  {% endif %}
</div>
""")

@app.route("/verified")
@login_required
def verified_page():
    raw   = storage.get_all_verified() if hasattr(storage, "get_all_verified") else {}
    now   = datetime.now()
    users = {}
    for uid, v in raw.items():
        try:
            expiry = datetime.fromisoformat(v["expiry"])
            users[uid] = {"name": v.get("name", uid), "expiry": v["expiry"], "active": expiry > now}
        except Exception:
            users[uid] = {"name": v.get("name", uid), "expiry": v.get("expiry","?"), "active": False}
    return render_template_string(VERIFIED_TMPL,
        title="Verified Users", active="verified", show_sidebar=True, tag=CHANNEL_TAG, users=users,
    )

@app.route("/verified/add", methods=["POST"])
@login_required
def verified_add():
    try:
        uid   = int(request.form["user_id"])
        name  = request.form.get("name","").strip() or str(uid)
        hours = int(request.form.get("hours", 720))
        expiry = storage.add_verified(uid, name, hours)
        flash(f"Verification granted to {name} ({uid}) — expires {expiry.strftime('%d-%m-%Y %H:%M')}", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("verified_page"))

@app.route("/verified/remove/<uid>", methods=["POST"])
@login_required
def verified_remove(uid):
    removed = storage.remove_verified(int(uid))
    if removed:
        flash(f"Verification revoked for user {uid}.", "success")
    else:
        flash(f"User {uid} not found in verified list.", "error")
    return redirect(url_for("verified_page"))

# ─────────────────────────────────────────────
#  Channels
# ─────────────────────────────────────────────

CHANNELS_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-header">
  <div class="page-title">📺 Channels</div>
  <div class="page-sub">View, add, edit and delete M3U8 channel links</div>
</div>

<div class="card">
  <div class="card-title"><span>➕ Add New Channel</span></div>
  <form method="POST" action="/channels/add">
    <div class="form-row">
      <div class="form-group" style="max-width:160px">
        <label>Key (for /record) *</label>
        <input type="text" name="key" placeholder="e.g. pogo2" required/>
      </div>
      <div class="form-group">
        <label>Channel Name *</label>
        <input type="text" name="name" placeholder="e.g. Pogo HD" required/>
      </div>
      <div class="form-group" style="max-width:90px">
        <label>Emoji</label>
        <input type="text" name="emoji" placeholder="📺" value="📺"/>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>TPlay URL</label>
        <input type="text" name="tplay_url" placeholder="http://...index.m3u8"/>
      </div>
      <div class="form-group">
        <label>JioTV URL</label>
        <input type="text" name="jiotv_url" placeholder="http://...live/XXX.m3u8"/>
      </div>
      <button class="btn btn-primary" style="align-self:flex-end">➕ Add</button>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title"><span>📺 All Channels ({{ channels|length }})</span></div>
  {% if channels %}
  <div class="table-wrap">
  <table>
    <tr><th>Channel</th><th>Key</th><th>TPlay</th><th>JioTV</th><th>Type</th><th>Actions</th></tr>
    {% for key, ch in channels.items() %}
    <tr>
      <td><strong>{{ ch.emoji }} {{ ch.name }}</strong></td>
      <td><span class="badge badge-blue">{{ key }}</span></td>
      <td class="url-text" style="max-width:140px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis" title="{{ ch.sources.get('TPlay','—') }}">
        {{ ch.sources.get('TPlay','—')[:40] }}{% if ch.sources.get('TPlay','') | length > 40 %}…{% endif %}
      </td>
      <td class="url-text" style="max-width:140px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis" title="{{ ch.sources.get('JioTV','—') }}">
        {{ ch.sources.get('JioTV','—')[:40] }}{% if ch.sources.get('JioTV','') | length > 40 %}…{% endif %}
      </td>
      <td>
        {% if ch._source == 'custom' %}<span class="badge badge-green">Custom</span>
        {% else %}<span class="badge badge-gray">Default</span>{% endif %}
      </td>
      <td style="white-space:nowrap">
        <a href="/channels/edit/{{ key }}" class="btn btn-warning btn-sm">✏️ Edit</a>
        {% if ch._source == 'custom' %}
        <form method="POST" action="/channels/remove/{{ key }}" style="display:inline" onsubmit="return confirm('Remove channel {{ ch.name }}?')">
          <button class="btn btn-danger btn-sm">🗑</button>
        </form>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
  </div>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No channels yet.</p>
  {% endif %}
</div>
""")

CHANNEL_EDIT_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div style="margin-bottom:16px">
  <a href="/channels" class="btn btn-secondary btn-sm">← Back to Channels</a>
</div>
<div class="page-header">
  <div class="page-title">✏️ Edit Channel</div>
  <div class="page-sub">Key: <span class="badge badge-blue">{{ key }}</span>
    {% if is_default %}<span class="badge badge-gray" style="margin-left:8px">Default — saves as custom override</span>{% endif %}
  </div>
</div>

<div class="card">
  <div class="card-title"><span>Channel Details</span></div>
  <form method="POST" action="/channels/update/{{ key }}">
    <div class="form-row">
      <div class="form-group">
        <label>Channel Name *</label>
        <input type="text" name="name" value="{{ ch.name }}" required/>
      </div>
      <div class="form-group" style="max-width:100px">
        <label>Emoji</label>
        <input type="text" name="emoji" value="{{ ch.emoji }}"/>
      </div>
    </div>
    <div class="form-group" style="margin-bottom:14px">
      <label>TPlay URL</label>
      <input type="text" name="tplay_url" value="{{ ch.sources.get('TPlay','') }}" placeholder="http://...index.m3u8"/>
    </div>
    <div class="form-group" style="margin-bottom:20px">
      <label>JioTV URL</label>
      <input type="text" name="jiotv_url" value="{{ ch.sources.get('JioTV','') }}" placeholder="http://...live/XXX.m3u8"/>
    </div>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <button class="btn btn-primary">💾 Save Changes</button>
      <a href="/channels" class="btn btn-secondary">Cancel</a>
      {% if not is_default %}
      <form method="POST" action="/channels/remove/{{ key }}" style="margin-left:auto" onsubmit="return confirm('Delete channel {{ ch.name }}?')">
        <button class="btn btn-danger">🗑 Delete Channel</button>
      </form>
      {% endif %}
    </div>
  </form>
</div>
""")

@app.route("/channels")
@login_required
def channels():
    return render_template_string(CHANNELS_TMPL,
        title="Channels", active="channels", show_sidebar=True, tag=CHANNEL_TAG,
        channels=storage.get_all_channels(),
    )

@app.route("/channels/edit/<path:key>")
@login_required
def channels_edit(key):
    all_ch     = storage.get_all_channels()
    ch         = all_ch.get(key)
    if not ch:
        flash(f"Channel '{key}' not found.", "error")
        return redirect(url_for("channels"))
    is_default = ch.get("_source","custom") == "default"
    return render_template_string(CHANNEL_EDIT_TMPL,
        title=f"Edit {ch['name']}", active="channels", show_sidebar=True, tag=CHANNEL_TAG,
        key=key, ch=ch, is_default=is_default,
    )

@app.route("/channels/update/<path:key>", methods=["POST"])
@login_required
def channels_update(key):
    try:
        name      = request.form["name"].strip()
        emoji     = request.form.get("emoji","📺").strip() or "📺"
        tplay_url = request.form.get("tplay_url","").strip()
        jiotv_url = request.form.get("jiotv_url","").strip()
        if not name:
            flash("Channel name is required.", "error")
            return redirect(url_for("channels_edit", key=key))
        storage.update_channel(key, name, emoji, tplay_url, jiotv_url)
        flash(f"Channel '{name}' updated.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("channels"))

@app.route("/channels/add", methods=["POST"])
@login_required
def channels_add():
    try:
        key       = request.form["key"].strip().lower()
        name      = request.form["name"].strip()
        emoji     = request.form.get("emoji","📺").strip() or "📺"
        tplay_url = request.form.get("tplay_url","").strip()
        jiotv_url = request.form.get("jiotv_url","").strip()
        if not key or not name:
            flash("Key and Name are required.", "error")
        else:
            storage.add_channel(key, name, emoji, tplay_url, jiotv_url)
            flash(f"Channel '{name}' added with key '{key}'.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("channels"))

@app.route("/channels/remove/<path:key>", methods=["POST"])
@login_required
def channels_remove(key):
    removed = storage.remove_channel(key)
    if removed:
        flash(f"Channel '{key}' removed.", "success")
    else:
        flash(f"Channel '{key}' not found in custom channels.", "error")
    return redirect(url_for("channels"))

# ─────────────────────────────────────────────
#  Playlist — Update URL & Cache
# ─────────────────────────────────────────────

PLAYLIST_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-header">
  <div class="page-title">🔗 Playlist</div>
  <div class="page-sub">Update the IPTV playlist M3U8 source URL and manage cache</div>
</div>

<div class="card">
  <div class="card-title"><span>📡 Current Playlist URL</span></div>
  <div class="url-box">{{ current_url }}</div>
  <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
    <form method="POST" action="/playlist/clear_cache" style="display:inline">
      <button class="btn btn-info">🔄 Clear Cache (Force Reload)</button>
    </form>
  </div>
  {% if cache_size %}
  <div style="margin-top:12px;font-size:13px;color:#8b949e">
    <span class="badge badge-green">{{ cache_size }} channels cached</span>
    &nbsp; Last refreshed from remote source
  </div>
  {% else %}
  <div style="margin-top:12px;font-size:13px;color:#8b949e">
    <span class="badge badge-orange">Cache empty</span>
    &nbsp; Will fetch on next /PlaylistChannels use
  </div>
  {% endif %}
</div>

<div class="card">
  <div class="card-title"><span>✏️ Update Playlist URL</span></div>
  <form method="POST" action="/playlist/update">
    <div class="form-group" style="margin-bottom:14px">
      <label>New M3U8 URL *</label>
      <input type="url" name="url" value="{{ current_url }}" placeholder="https://..." required style="font-family:monospace;font-size:12px"/>
    </div>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <button class="btn btn-primary">💾 Save & Apply URL</button>
      <span style="font-size:12px;color:#8b949e">Cache will be cleared automatically</span>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title"><span>ℹ️ How It Works</span></div>
  <div style="font-size:13px;color:#8b949e;line-height:1.8">
    <p>• Bot uses this URL for <code style="background:#0d1117;padding:1px 5px;border-radius:3px">/PlaylistChannels</code> and <code style="background:#0d1117;padding:1px 5px;border-radius:3px">/search</code> commands</p>
    <p>• Channels are cached in memory for <strong style="color:#e6edf3">1 hour</strong> to avoid repeated fetches</p>
    <p>• Clicking <em>Clear Cache</em> forces a fresh fetch on next use</p>
    <p>• URLs are hidden from users — only channel names are shown</p>
    <p>• Bot me bhi update ho jaata hai <code style="background:#0d1117;padding:1px 5px;border-radius:3px">/PlaylistChannels update &lt;url&gt;</code> command se</p>
  </div>
</div>
""")

@app.route("/playlist")
@login_required
def playlist_page():
    from playlist_mgr import _cache, get_current_url
    return render_template_string(PLAYLIST_TMPL,
        title="Playlist", active="playlist", show_sidebar=True, tag=CHANNEL_TAG,
        current_url=get_current_url(),
        cache_size=len(_cache),
    )

@app.route("/playlist/update", methods=["POST"])
@login_required
def playlist_update():
    url = request.form.get("url","").strip()
    if not url:
        flash("URL cannot be empty.", "error")
        return redirect(url_for("playlist_page"))
    try:
        playlist_mgr.update_url(url)
        flash(f"Playlist URL updated and cache cleared. New URL: {url}", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("playlist_page"))

@app.route("/playlist/clear_cache", methods=["POST"])
@login_required
def playlist_clear_cache():
    playlist_mgr.clear_cache()
    flash("Playlist cache cleared. Fresh data will be fetched on next use.", "info")
    return redirect(url_for("playlist_page"))

# ─────────────────────────────────────────────
#  Settings
# ─────────────────────────────────────────────

SETTINGS_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-header">
  <div class="page-title">⚙️ Settings</div>
  <div class="page-sub">Bot-wide configuration and toggles</div>
</div>

<div class="card">
  <div class="card-title"><span>🔐 Verification System</span></div>
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">
    <div>
      <div style="font-size:14px;font-weight:600;margin-bottom:4px">
        <span class="dot {{ 'dot-green' if verify_on else 'dot-red' }}"></span>
        Verification is currently <strong>{{ 'ON' if verify_on else 'OFF' }}</strong>
      </div>
      <div style="font-size:13px;color:#8b949e">
        When ON, free users must complete shortlink verification before using the bot.
        Owners, Dosts, Premium, and Auth users are always exempt.
      </div>
    </div>
    <div style="display:flex;gap:10px">
      {% if verify_on %}
      <form method="POST" action="/settings/verify_off">
        <button class="btn btn-danger">🔴 Turn OFF Verification</button>
      </form>
      {% else %}
      <form method="POST" action="/settings/verify_on">
        <button class="btn btn-primary">🟢 Turn ON Verification</button>
      </form>
      {% endif %}
    </div>
  </div>
</div>

<div class="card">
  <div class="card-title"><span>🤖 Bot Info</span></div>
  <div class="table-wrap">
  <table>
    <tr><td style="color:#8b949e;width:180px">Bot Username</td><td><span class="badge badge-blue">@{{ bot_username }}</span></td></tr>
    <tr><td style="color:#8b949e">Channel Tag</td><td><span class="badge badge-gray">@{{ tag }}</span></td></tr>
    <tr><td style="color:#8b949e">Group Link</td><td><a href="{{ group_link }}" target="_blank" style="font-size:12px">{{ group_link }}</a></td></tr>
    <tr><td style="color:#8b949e">Owner IDs</td><td>
      {% for oid in owner_ids %}<span class="badge badge-purple" style="margin:2px">{{ oid }}</span>{% endfor %}
    </td></tr>
    <tr><td style="color:#8b949e">Max Recordings</td><td><span class="badge badge-gray">{{ max_rec }} per user</span></td></tr>
    <tr><td style="color:#8b949e">Free Duration Limit</td><td><span class="badge badge-gray">{{ free_hrs }} hours</span></td></tr>
    <tr><td style="color:#8b949e">Verify Grant Duration</td><td><span class="badge badge-gray">{{ verify_hrs }} hours</span></td></tr>
  </table>
  </div>
</div>

<div class="card">
  <div class="card-title"><span>🔑 Change Admin Password</span></div>
  <form method="POST" action="/settings/change_password">
    <div class="form-row">
      <div class="form-group">
        <label>Current Password *</label>
        <input type="password" name="current" required/>
      </div>
      <div class="form-group">
        <label>New Password *</label>
        <input type="password" name="new_pass" required/>
      </div>
      <div class="form-group">
        <label>Confirm New Password *</label>
        <input type="password" name="confirm" required/>
      </div>
      <button class="btn btn-warning" style="align-self:flex-end">🔑 Change Password</button>
    </div>
    <div style="font-size:12px;color:#8b949e;margin-top:4px">⚠️ Password change is session-only. Update your Config.py ADMIN_PASSWORD to make it permanent.</div>
  </form>
</div>
""")

@app.route("/settings")
@login_required
def settings():
    from Config import (BOT_USERNAME, GROUP_LINK, VERIFY_HOURS,
                        FREE_MAX_DURATION_HOURS)
    return render_template_string(SETTINGS_TMPL,
        title="Settings", active="settings", show_sidebar=True, tag=CHANNEL_TAG,
        verify_on=storage.is_verification_enabled(),
        bot_username=BOT_USERNAME, group_link=GROUP_LINK,
        owner_ids=OWNER_IDS, max_rec=4,
        free_hrs=FREE_MAX_DURATION_HOURS,
        verify_hrs=VERIFY_HOURS,
    )

@app.route("/settings/verify_on", methods=["POST"])
@login_required
def settings_verify_on():
    storage.set_verification_enabled(True)
    flash("Verification turned ON. Free users must now verify.", "success")
    return redirect(url_for("settings"))

@app.route("/settings/verify_off", methods=["POST"])
@login_required
def settings_verify_off():
    storage.set_verification_enabled(False)
    flash("Verification turned OFF. All users can use the bot freely.", "success")
    return redirect(url_for("settings"))

@app.route("/settings/change_password", methods=["POST"])
@login_required
def settings_change_password():
    current  = request.form.get("current","")
    new_pass = request.form.get("new_pass","").strip()
    confirm  = request.form.get("confirm","").strip()
    if current != ADMIN_PASSWORD:
        flash("Current password is incorrect.", "error")
    elif not new_pass:
        flash("New password cannot be empty.", "error")
    elif new_pass != confirm:
        flash("New passwords do not match.", "error")
    else:
        session["temp_password"] = new_pass
        flash("Password changed for this session. Update ADMIN_PASSWORD in Config.py to make it permanent.", "info")
    return redirect(url_for("settings"))

# ─────────────────────────────────────────────
#  Run helper
# ─────────────────────────────────────────────

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
