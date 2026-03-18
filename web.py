from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from functools import wraps
import storage
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
  .sidebar{width:220px;min-height:100vh;background:#161b22;border-right:1px solid #30363d;padding:0;display:flex;flex-direction:column;flex-shrink:0}
  .sidebar-header{padding:20px 16px 16px;border-bottom:1px solid #30363d}
  .sidebar-header h2{font-size:15px;color:#58a6ff;font-weight:700}
  .sidebar-header p{font-size:11px;color:#8b949e;margin-top:3px}
  .sidebar nav{padding:12px 0;flex:1}
  .nav-link{display:flex;align-items:center;gap:10px;padding:10px 16px;color:#8b949e;font-size:13px;transition:all .15s;border-left:3px solid transparent}
  .nav-link:hover,.nav-link.active{color:#e6edf3;background:#1f2937;border-left-color:#58a6ff;text-decoration:none}
  .nav-link .icon{font-size:16px;width:20px;text-align:center}
  .sidebar-footer{padding:14px 16px;border-top:1px solid #30363d;font-size:11px;color:#8b949e}

  /* Main */
  .main{flex:1;padding:24px;overflow-y:auto}
  .page-title{font-size:22px;font-weight:700;margin-bottom:4px}
  .page-sub{font-size:13px;color:#8b949e;margin-bottom:24px}

  /* Cards */
  .card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px;margin-bottom:18px}
  .card-title{font-size:13px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:16px}

  /* Stats grid */
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:24px}
  .stat-card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;text-align:center}
  .stat-num{font-size:32px;font-weight:700;color:#58a6ff}
  .stat-label{font-size:12px;color:#8b949e;margin-top:4px}

  /* Table */
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;padding:10px 12px;color:#8b949e;font-weight:600;border-bottom:1px solid #30363d;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
  td{padding:10px 12px;border-bottom:1px solid #21262d;vertical-align:middle}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:#1c2128}
  .badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
  .badge-green{background:#0d4429;color:#3fb950}
  .badge-red{background:#3d1212;color:#f85149}
  .badge-blue{background:#0c2d6b;color:#58a6ff}
  .badge-gray{background:#21262d;color:#8b949e}

  /* Forms */
  .form-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:14px}
  input,select{background:#0d1117;border:1px solid #30363d;color:#e6edf3;border-radius:6px;padding:8px 12px;font-size:13px;outline:none;transition:border .15s}
  input:focus,select:focus{border-color:#58a6ff}
  input[type=text],input[type=password],input[type=number]{width:100%}
  .form-group{display:flex;flex-direction:column;gap:5px;flex:1;min-width:140px}
  label{font-size:12px;color:#8b949e;font-weight:500}
  .btn{padding:8px 16px;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s}
  .btn-primary{background:#238636;color:#fff}
  .btn-primary:hover{background:#2ea043}
  .btn-danger{background:#da3633;color:#fff}
  .btn-danger:hover{background:#f85149}
  .btn-secondary{background:#21262d;color:#e6edf3;border:1px solid #30363d}
  .btn-secondary:hover{background:#30363d}
  .btn-sm{padding:4px 10px;font-size:12px}
  .btn-warning{background:#9e6a03;color:#fff}
  .btn-warning:hover{background:#b07a00}

  /* Alerts */
  .alert{padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px}
  .alert-success{background:#0d4429;border:1px solid #238636;color:#3fb950}
  .alert-error{background:#3d1212;border:1px solid #da3633;color:#f85149}

  /* Login */
  .login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0d1117;width:100%}
  .login-card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:36px;width:340px}
  .login-card h1{font-size:20px;margin-bottom:6px;color:#e6edf3}
  .login-card p{color:#8b949e;font-size:13px;margin-bottom:24px}
  .login-card input{width:100%;margin-bottom:12px}

  /* Chip */
  .chip{display:inline-block;background:#1f2937;border:1px solid #30363d;border-radius:20px;padding:2px 10px;font-size:11px;color:#8b949e;margin:2px}

  /* URL text */
  .url-text{font-family:monospace;font-size:11px;color:#8b949e;word-break:break-all}

  @media(max-width:640px){
    body{flex-direction:column}
    .sidebar{width:100%;min-height:auto}
    .main{padding:14px}
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
    <a class="nav-link {{ 'active' if active=='dashboard' }}" href="/"><span class="icon">🏠</span>Dashboard</a>
    <a class="nav-link {{ 'active' if active=='dosts' }}" href="/dosts"><span class="icon">👥</span>Dost List</a>
    <a class="nav-link {{ 'active' if active=='premium' }}" href="/premium"><span class="icon">💎</span>Premium</a>
    <a class="nav-link {{ 'active' if active=='channels' }}" href="/channels"><span class="icon">📺</span>Channels</a>
  </nav>
  <div class="sidebar-footer">
    <a href="/logout" class="btn btn-secondary btn-sm">🚪 Logout</a>
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
  <p>LittleSingham Bot Dashboard</p>
  {% for msg in get_flashed_messages(category_filter=['error']) %}
    <div class="alert alert-error">❌ {{ msg }}</div>
  {% endfor %}
  <form method="POST">
    <label>Password</label>
    <input type="password" name="password" placeholder="Enter admin password" autofocus required/>
    <button class="btn btn-primary" style="width:100%;margin-top:4px">Login →</button>
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

@app.route("/")
@login_required
def dashboard():
    dosts   = storage.get_dosts()
    premium = storage.get_all_premium()
    channels = storage.get_all_channels()
    now = datetime.now()

    active_premium = sum(
        1 for v in premium.values()
        if datetime.fromisoformat(v["expiry"]) > now
    )

    tmpl = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-title">🏠 Dashboard</div>
<div class="page-sub">LittleSingham Bot — Admin Overview</div>

<div class="stats">
  <div class="stat-card">
    <div class="stat-num">{{ dost_count }}</div>
    <div class="stat-label">👥 Dosts</div>
  </div>
  <div class="stat-card">
    <div class="stat-num" style="color:#a371f7">{{ premium_count }}</div>
    <div class="stat-label">💎 Premium Users</div>
  </div>
  <div class="stat-card">
    <div class="stat-num" style="color:#3fb950">{{ channel_count }}</div>
    <div class="stat-label">📺 Channels</div>
  </div>
</div>

<div class="card">
  <div class="card-title">🔗 Quick Links</div>
  <div style="display:flex;gap:10px;flex-wrap:wrap">
    <a href="/dosts" class="btn btn-secondary">👥 Manage Dosts</a>
    <a href="/premium" class="btn btn-secondary">💎 Manage Premium</a>
    <a href="/channels" class="btn btn-secondary">📺 Manage Channels</a>
  </div>
</div>

<div class="card">
  <div class="card-title">📋 Recent Dosts</div>
  {% if dosts %}
  <table>
    <tr><th>Name</th><th>User ID</th><th>Added</th></tr>
    {% for uid, info in dosts.items() %}
    <tr>
      <td>{{ info.username }}</td>
      <td><span class="badge badge-blue">{{ uid }}</span></td>
      <td style="color:#8b949e;font-size:12px">{{ info.added_at[:10] }}</td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No dosts yet. <a href="/dosts">Add one →</a></p>
  {% endif %}
</div>
""")
    return render_template_string(tmpl,
        title="Dashboard", active="dashboard", show_sidebar=True, tag=CHANNEL_TAG,
        dost_count=len(dosts), premium_count=active_premium,
        channel_count=len(channels), dosts=dosts,
    )

# ─────────────────────────────────────────────
#  Dosts
# ─────────────────────────────────────────────

DOSTS_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-title">👥 Dost List</div>
<div class="page-sub">Add, view and remove registered Dosts</div>

<div class="card">
  <div class="card-title">➕ Add New Dost</div>
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
      <button class="btn btn-primary" style="align-self:flex-end">Add Dost</button>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title">👥 All Dosts ({{ dosts|length }})</div>
  {% if dosts %}
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
          <button class="btn btn-danger btn-sm">Remove</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>
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
<div class="page-title">💎 Premium Users</div>
<div class="page-sub">Activate, extend or remove premium plans</div>

<div class="card">
  <div class="card-title">➕ Add / Extend Premium</div>
  <form method="POST" action="/premium/add">
    <div class="form-row">
      <div class="form-group">
        <label>User ID *</label>
        <input type="number" name="user_id" placeholder="e.g. 123456789" required/>
      </div>
      <div class="form-group" style="max-width:180px">
        <label>Plan</label>
        <select name="days">
          <option value="7">1 Week ($25)</option>
          <option value="15">15 Days ($50)</option>
          <option value="30" selected>1 Month ($75)</option>
          <option value="90">3 Months</option>
          <option value="365">1 Year</option>
        </select>
      </div>
      <button class="btn btn-primary" style="align-self:flex-end">Activate</button>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title">💎 Premium Users ({{ users|length }})</div>
  {% if users %}
  <table>
    <tr><th>User ID</th><th>Status</th><th>Expires</th><th>Days Left</th><th>Action</th></tr>
    {% for uid, info in users.items() %}
    <tr>
      <td><span class="badge badge-blue">{{ uid }}</span></td>
      <td>
        {% if info.active %}
          <span class="badge badge-green">Active</span>
        {% else %}
          <span class="badge badge-red">Expired</span>
        {% endif %}
      </td>
      <td style="font-size:12px">{{ info.expiry[:10] }}</td>
      <td>
        {% if info.days_left > 0 %}
          <span class="badge badge-green">{{ info.days_left }}d</span>
        {% else %}
          <span class="badge badge-red">0d</span>
        {% endif %}
      </td>
      <td>
        <form method="POST" action="/premium/remove/{{ uid }}" style="display:inline" onsubmit="return confirm('Remove premium?')">
          <button class="btn btn-danger btn-sm">Remove</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No premium users yet.</p>
  {% endif %}
</div>
""")

@app.route("/premium")
@login_required
def premium():
    raw  = storage.get_all_premium()
    now  = datetime.now()
    users = {}
    for uid, v in raw.items():
        try:
            expiry = datetime.fromisoformat(v["expiry"])
            delta  = expiry - now
            users[uid] = {
                "expiry":    v["expiry"],
                "active":    expiry > now,
                "days_left": max(0, delta.days),
            }
        except Exception:
            users[uid] = {"expiry": v.get("expiry", "?"), "active": False, "days_left": 0}
    return render_template_string(PREMIUM_TMPL,
        title="Premium", active="premium", show_sidebar=True, tag=CHANNEL_TAG,
        users=users,
    )

@app.route("/premium/add", methods=["POST"])
@login_required
def premium_add():
    try:
        uid  = int(request.form["user_id"])
        days = int(request.form["days"])
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
#  Channels
# ─────────────────────────────────────────────

CHANNELS_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div class="page-title">📺 Channels</div>
<div class="page-sub">View, add, edit and delete M3U8 channel links</div>

<div class="card">
  <div class="card-title">➕ Add New Channel</div>
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
  <div class="card-title">📺 All Channels ({{ channels|length }})</div>
  {% if channels %}
  <table>
    <tr><th>Channel</th><th>Key</th><th>TPlay URL</th><th>JioTV URL</th><th>Type</th><th>Actions</th></tr>
    {% for key, ch in channels.items() %}
    <tr>
      <td><strong>{{ ch.emoji }} {{ ch.name }}</strong></td>
      <td><span class="badge badge-blue">{{ key }}</span></td>
      <td class="url-text" style="max-width:160px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis" title="{{ ch.sources.get('TPlay','—') }}">
        {{ ch.sources.get('TPlay','—')[:45] }}{% if ch.sources.get('TPlay','') | length > 45 %}…{% endif %}
      </td>
      <td class="url-text" style="max-width:160px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis" title="{{ ch.sources.get('JioTV','—') }}">
        {{ ch.sources.get('JioTV','—')[:45] }}{% if ch.sources.get('JioTV','') | length > 45 %}…{% endif %}
      </td>
      <td>
        {% if ch._source == 'custom' %}
          <span class="badge badge-green">Custom</span>
        {% else %}
          <span class="badge badge-gray">Default</span>
        {% endif %}
      </td>
      <td style="white-space:nowrap">
        <a href="/channels/edit/{{ key }}" class="btn btn-warning btn-sm">✏️ Edit</a>
        {% if ch._source == 'custom' %}
        <form method="POST" action="/channels/remove/{{ key }}" style="display:inline" onsubmit="return confirm('Remove channel {{ ch.name }}?')">
          <button class="btn btn-danger btn-sm">🗑 Del</button>
        </form>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p style="color:#8b949e;font-size:13px">No channels yet.</p>
  {% endif %}
</div>

<div class="card">
  <div class="card-title">ℹ️ Bot mein use kaise karein</div>
  <p style="font-size:13px;color:#8b949e;line-height:1.6">
    Channel <strong>key</strong> se record command use karo:<br>
    <code style="background:#0d1117;padding:2px 6px;border-radius:4px">/record pogo 01:30:00</code><br>
    Ya sabhi channels browse karo: <code style="background:#0d1117;padding:2px 6px;border-radius:4px">/Channels</code>
  </p>
</div>
""")

CHANNEL_EDIT_TMPL = BASE.replace("{% block content %}{% endblock %}", """
<div style="margin-bottom:12px">
  <a href="/channels" class="btn btn-secondary btn-sm">← Back to Channels</a>
</div>
<div class="page-title">✏️ Edit Channel</div>
<div class="page-sub">
  Key: <span class="badge badge-blue">{{ key }}</span>
  &nbsp;
  {% if is_default %}<span class="badge badge-gray">Default — editing saves as custom override</span>{% else %}<span class="badge badge-green">Custom</span>{% endif %}
</div>

<div class="card" style="margin-top:20px">
  <div class="card-title">Channel Details</div>
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
    <div style="display:flex;gap:10px;align-items:center">
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
    all_ch = storage.get_all_channels()
    return render_template_string(CHANNELS_TMPL,
        title="Channels", active="channels", show_sidebar=True, tag=CHANNEL_TAG,
        channels=all_ch,
    )

@app.route("/channels/edit/<path:key>")
@login_required
def channels_edit(key):
    all_ch  = storage.get_all_channels()
    ch      = all_ch.get(key)
    if not ch:
        flash(f"Channel '{key}' not found.", "error")
        return redirect(url_for("channels"))
    is_default = ch.get("_source", "custom") == "default"
    return render_template_string(CHANNEL_EDIT_TMPL,
        title=f"Edit {ch['name']}", active="channels", show_sidebar=True, tag=CHANNEL_TAG,
        key=key, ch=ch, is_default=is_default,
    )

@app.route("/channels/update/<path:key>", methods=["POST"])
@login_required
def channels_update(key):
    try:
        name      = request.form["name"].strip()
        emoji     = request.form.get("emoji", "📺").strip() or "📺"
        tplay_url = request.form.get("tplay_url", "").strip()
        jiotv_url = request.form.get("jiotv_url", "").strip()
        if not name:
            flash("Channel name is required.", "error")
            return redirect(url_for("channels_edit", key=key))
        storage.update_channel(key, name, emoji, tplay_url, jiotv_url)
        flash(f"Channel '{name}' updated successfully.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("channels"))

@app.route("/channels/add", methods=["POST"])
@login_required
def channels_add():
    try:
        key       = request.form["key"].strip().lower()
        name      = request.form["name"].strip()
        emoji     = request.form.get("emoji", "📺").strip() or "📺"
        tplay_url = request.form.get("tplay_url", "").strip()
        jiotv_url = request.form.get("jiotv_url", "").strip()
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
#  Run helper
# ─────────────────────────────────────────────

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
