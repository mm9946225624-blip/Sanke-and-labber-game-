"""Snake & Ladder — Streamlit multiplayer game.

Run locally with:
    pip install -r requirements.txt
    streamlit run app.py

The SQLite database is shared by sessions on the same running app instance.
On Streamlit Community Cloud, local database files may be reset when the app
restarts; use a managed database for durable production storage.
"""
import hashlib
import html
import json
import os
import secrets
import sqlite3
import string
import time
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Snake & Ladder", page_icon="🐍", layout="centered")

# Set SNAKE_DB_PATH to a persistent mounted path if your deployment provides one.
DB_PATH = os.getenv("SNAKE_DB_PATH", str(Path(__file__).with_name("snake_ladder.db")))
MAX_PLAYERS = 4
SNAKES = {17: 7, 54: 34, 62: 19, 64: 60, 87: 24, 93: 73, 95: 75, 98: 79}
LADDERS = {4: 14, 9: 31, 20: 38, 28: 84, 40: 59, 51: 67, 63: 81, 71: 91}
COLORS = ["#2563eb", "#dc2626", "#16a34a", "#9333ea"]
DICE_FACES = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

CSS = """
<style>
:root {color-scheme:dark}
.stApp {background:radial-gradient(ellipse at 50% 10%,#087e78 0%,#064e59 42%,#052e3a 100%);color:#f0fdf4}
#MainMenu, footer {visibility:hidden}
.block-container {padding-top:.8rem;max-width:760px;padding-bottom:1rem}
.title {text-align:center;font-size:clamp(1.7rem,5vw,2.5rem);font-weight:900;color:#f0fdf4;text-shadow:0 3px 0 #14532d;margin-bottom:0}
.subtitle {text-align:center;color:#a7f3d0;margin-bottom:1rem}
.jungle-bar {display:flex;justify-content:space-between;align-items:center;margin:.2rem 0 .7rem}
.round-icon {display:inline-flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:50%;
background:linear-gradient(#a3e635,#4d9d16);border:3px solid #ecfccb;color:#14532d;font-size:1.6rem;box-shadow:0 4px 0 #166534}
.boost {border-radius:25px;padding:8px 12px;background:linear-gradient(#22d3ee,#0891b2);border:3px solid #a5f3fc;font-weight:900;color:white}
.board-wrap {padding:10px;border-radius:22px;background:linear-gradient(135deg,#0e7490,#064e3b 45%,#134e4a);box-shadow:0 12px 30px #001d26aa;border:2px solid #2dd4bf}
.board {display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:3px;width:100%;margin:0 auto;padding:7px;
background:linear-gradient(135deg,#14532d,#064e3b);border-radius:14px}
.cell {position:relative;aspect-ratio:1/1;border-radius:5px;background:linear-gradient(145deg,#4ade80,#16a34a 65%,#15803d);
color:#ecfdf5;padding:3px;overflow:hidden;font-size:clamp(.48rem,1.55vw,.8rem);font-weight:800;
box-shadow:inset 0 -4px 0 #16653455,inset 0 1px 0 #bbf7d0; text-shadow:0 1px 1px #14532d}
.cell.alt {background:linear-gradient(145deg,#22c55e,#15803d 75%,#166534)}
.cell.snake {background:linear-gradient(145deg,#65a30d,#15803d)}
.cell.ladder {background:linear-gradient(145deg,#86efac,#22c55e)}
.cell.end {background:linear-gradient(145deg,#fde047,#ca8a04);color:#713f12}
.tag {position:absolute;bottom:1px;left:2px;font-size:clamp(.38rem,1.1vw,.65rem);font-weight:900}
.cell.snake .tag {color:#fef08a}.cell.ladder .tag {color:#fef9c3}
.tokens {position:absolute;inset:0;display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px;padding-top:5px}
.token {width:clamp(12px,2.6vw,22px);height:clamp(12px,2.6vw,22px);border-radius:50%;border:2px solid #fff;color:#fff;
font-size:clamp(.42rem,1vw,.65rem);font-weight:900;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 4px #052e16}
.dice {text-align:center;font-size:3.5rem;line-height:1.1;filter:drop-shadow(0 3px 0 #064e3b);margin:.25rem 0}
.chip {display:inline-block;padding:5px 11px;border-radius:999px;color:white;font-weight:800;font-size:.82rem;margin:3px 4px 3px 0;border:1px solid #ffffff55}
.roomcode {text-align:center;font-size:1.8rem;font-weight:900;letter-spacing:.35rem;background:#ecfeff;border-radius:12px;padding:.45rem;color:#0e7490}
.player-panel {display:flex;gap:10px;align-items:center;justify-content:space-between;margin-top:12px}
.player-card {flex:1;text-align:center;border-radius:18px;padding:10px 6px;background:linear-gradient(#1d4ed8,#1e40af);border:3px solid #bfdbfe;box-shadow:0 4px 0 #172554}
.computer-card {background:linear-gradient(#b91c1c,#7f1d1d);border-color:#fecaca}
.dice-button {font-size:2rem;line-height:1.1;background:#1d4ed8;border:3px solid white;border-radius:50%;padding:8px;width:66px;height:66px;margin:5px auto}
.small-label {font-weight:900;letter-spacing:.04em}
.stButton>button {border-radius:14px;font-weight:800}
div[data-testid="stAlert"] {background:#ecfdf522;color:#f0fdf4}
@media(max-width:480px){.block-container{padding-left:.35rem;padding-right:.35rem}.board-wrap{padding:5px}.board{gap:2px;padding:4px}.cell{border-radius:3px;padding:2px}.player-card{padding:7px 3px}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT NOT NULL,
            password_hash TEXT, guest INTEGER NOT NULL DEFAULT 0
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS rooms (
            code TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL
        )""")


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240000).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        return secrets.compare_digest(password_hash(password, salt).split("$", 1)[1], expected)
    except (ValueError, AttributeError):
        return False


def clean_name(name):
    return " ".join((name or "").split())[:24]


def register(email, name, password):
    email = (email or "").strip().lower()
    name = clean_name(name)
    if not name:
        return False, "Enter a display name.", None
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Enter a valid email address.", None
    if len(password or "") < 8:
        return False, "Password must be at least 8 characters.", None
    user = {"id": secrets.token_hex(12), "email": email, "name": name, "guest": False}
    try:
        with connect() as con:
            con.execute("INSERT INTO users (id,email,name,password_hash,guest) VALUES (?,?,?,?,0)",
                        (user["id"], email, name, password_hash(password)))
        return True, "Account created.", user
    except sqlite3.IntegrityError:
        return False, "An account with that email already exists.", None


def login(email, password):
    email = (email or "").strip().lower()
    with connect() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not verify_password(password or "", row["password_hash"]):
        return False, "Incorrect email or password.", None
    return True, "Logged in.", {"id": row["id"], "email": row["email"], "name": row["name"], "guest": False}


def guest_user(name):
    name = clean_name(name)
    if not name:
        return False, "Enter a nickname.", None
    return True, "Ready to play.", {"id": "guest_" + secrets.token_hex(10), "email": "", "name": name, "guest": True}


def new_state(host):
    return {
        "host": host["id"], "players": [{
            "id": host["id"], "name": host["name"], "color": COLORS[0], "pos": 0
        }],
        "status": "waiting", "turn": 0, "last_roll": None, "winner": None,
        "log": [f"{host['name']} created the room."]
    }


def save_state(code, state):
    with connect() as con:
        con.execute("INSERT INTO rooms(code,state,updated) VALUES(?,?,?) "
                    "ON CONFLICT(code) DO UPDATE SET state=excluded.state,updated=excluded.updated",
                    (code, json.dumps(state), time.time()))


def get_state(code):
    with connect() as con:
        row = con.execute("SELECT state FROM rooms WHERE code=?", (code,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["state"])
    except (ValueError, TypeError):
        return None


def mutate_room(code, callback):
    # SQLite's write transaction serializes updates from concurrent players.
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT state FROM rooms WHERE code=?", (code,)).fetchone()
        if not row:
            return False, "Room not found."
        try:
            state = json.loads(row["state"])
            ok, msg = callback(state)
            if ok:
                con.execute("UPDATE rooms SET state=?,updated=? WHERE code=?",
                            (json.dumps(state), time.time(), code))
            return ok, msg
        except Exception:
            con.rollback()
            raise


def create_room(user):
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(5))
        try:
            save_state(code, new_state(user))
            return code
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Could not create a room. Please try again.")


def add_player(state, user):
    if state["status"] != "waiting":
        return False, "This game has already started."
    if any(p["id"] == user["id"] for p in state["players"]):
        return True, "You are already in this room."
    if len(state["players"]) >= MAX_PLAYERS:
        return False, "This room is full (maximum 4 players)."
    state["players"].append({"id": user["id"], "name": user["name"],
                             "color": COLORS[len(state["players"])], "pos": 0})
    state["log"].append(f"{user['name']} joined the room.")
    return True, "Joined room."


def start_game(state, user_id):
    if state["host"] != user_id:
        return False, "Only the host can start the game."
    if state["status"] != "waiting":
        return False, "The game has already started."
    if len(state["players"]) < 2:
        return False, "Invite at least one more player before starting."
    state["status"] = "playing"
    state["turn"] = 0
    state["log"].append("The game has started!")
    return True, "Game started."


def roll_dice(state, user_id):
    if state["status"] != "playing":
        return False, "The game is not currently playing."
    if not state["players"] or state["players"][state["turn"]]["id"] != user_id:
        return False, "It is not your turn."
    import random
    player = state["players"][state["turn"]]
    value = random.randint(1, 6)
    old = player["pos"]
    new = old + value
    if new <= 100:
        player["pos"] = new
        message = f"{player['name']} rolled {value}: {old} → {new}."
        if new in SNAKES:
            player["pos"] = SNAKES[new]
            message += f" Snake! Down to {player['pos']}."
        elif new in LADDERS:
            player["pos"] = LADDERS[new]
            message += f" Ladder! Up to {player['pos']}."
        if player["pos"] == 100:
            state["status"] = "finished"
            state["winner"] = player["name"]
            message += f" {player['name']} wins!"
    else:
        message = f"{player['name']} rolled {value}; needs an exact roll to reach 100."
    state["last_roll"] = {"value": value, "player": player["name"]}
    state["log"].append(message)
    if state["status"] == "playing":
        if value == 6:
            message += " Rolled a 6 — take another turn!"
            state["log"][-1] = message
        else:
            state["turn"] = (state["turn"] + 1) % len(state["players"])
    return True, message


def rematch(state, user_id):
    if state["host"] != user_id:
        return False, "Only the host can start a rematch."
    if state["status"] != "finished":
        return False, "The current game has not finished."
    for player in state["players"]:
        player["pos"] = 0
    state["status"] = "playing"
    state["turn"] = 0
    state["last_roll"] = None
    state["winner"] = None
    state["log"].append("Rematch started!")
    return True, "Rematch started."


def leave_player(state, user_id):
    state["players"] = [p for p in state["players"] if p["id"] != user_id]
    if not state["players"]:
        return True, "Room is empty."
    if state["host"] == user_id:
        state["host"] = state["players"][0]["id"]
        state["log"].append(f"{state['players'][0]['name']} is now the host.")
    state["turn"] = min(state["turn"], len(state["players"]) - 1)
    state["log"].append("A player left the room.")
    return True, "Left room."


def cell_to_rc(number):
    row_from_bottom = (number - 1) // 10
    col = (number - 1) % 10
    if row_from_bottom % 2:
        col = 9 - col
    return 9 - row_from_bottom, col


def board_html(state):
    by_cell = {}
    for player in state["players"]:
        if player["pos"] > 0:
            by_cell.setdefault(player["pos"], []).append(player)
    grid = [[""] * 10 for _ in range(10)]
    for n in range(1, 101):
        r, c = cell_to_rc(n)
        classes, tag = ["cell"], ""
        if (r + c) % 2:
            classes.append("alt")
        if n in SNAKES:
            classes.append("snake")
            tag = f"🐍{SNAKES[n]}"
        elif n in LADDERS:
            classes.append("ladder")
            tag = f"🪜{LADDERS[n]}"
        if n == 100:
            classes.append("end")
            tag = "🏁"
        tokens = "".join(
            f'<div class="token" style="background:{html.escape(p["color"])}">{html.escape(p["name"][:1].upper())}</div>'
            for p in by_cell.get(n, [])
        )
        token_html = f'<div class="tokens">{tokens}</div>' if tokens else ""
        grid[r][c] = f'<div class="{" ".join(classes)}">{n}<span class="tag">{tag}</span>{token_html}</div>'
    return '<div class="board-wrap"><div class="board">' + "".join("".join(row) for row in grid) + "</div></div>"


def player_chips(state):
    chips = []
    for index, player in enumerate(state["players"]):
        crown = "👑 " if player["id"] == state["host"] else ""
        position = f" · {player['pos']}" if state["status"] != "waiting" else ""
        turn = " ◀" if state["status"] == "playing" and index == state["turn"] else ""
        chips.append(
            f'<span class="chip" style="background:{html.escape(player["color"])}">'
            f'{crown}{html.escape(player["name"])}{position}{turn}</span>'
        )
    return "".join(chips)


def leave_room():
    code = st.session_state.get("room")
    user = st.session_state.get("user")
    if code and user:
        mutate_room(code, lambda state: leave_player(state, user["id"]))
    st.session_state.room = None
    st.query_params.clear()


def show_rules():
    """Display the game rules supplied by the project owner."""
    with st.expander("📖 How to Play — Rules", expanded=False):
        st.markdown("### Equipment and Setup")
        st.markdown("""
        - **Players:** 2 to 4 players.
        - **Equipment:** A board numbered 1 to 100, one six-sided die (or spinner), and one counter per player.
        - **Starting position:** Counters start off the board or on square 1.
        - **First player:** Each player rolls once; the highest roll goes first. Turns then proceed clockwise.
        """)
        st.markdown("### How to Play")
        st.markdown("""
        - **Move:** Roll the die and move forward by the number shown.
        - **Ladders:** Landing on the bottom of a ladder moves you up to its top square.
        - **Snakes:** Landing on a snake's head sends you down to its tail.
        - **Extra roll:** Rolling a 6 gives you another turn.
        """)
        st.markdown("### Winning the Game")
        st.markdown("""
        - **Exact roll:** Reach square 100 with an exact roll to win.
        - **Overshooting 100:** If your roll is too high, your counter stays where it is.
        """)
        st.caption("This version uses the stay-in-place option for excess rolls. The starting player is currently the first player in the room; highest-roll selection is described here but is not yet implemented automatically.")


def auth_screen():
    st.markdown('<div class="title">🐍 Snake & Ladder 🪜</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Play with friends online — race to 100!</div>', unsafe_allow_html=True)
    login_tab, signup_tab, guest_tab = st.tabs(["Log in", "Sign up", "Play as guest"])
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
        if submitted:
            ok, message, user = login(email, password)
            if ok:
                st.session_state.user = user
                st.rerun()
            st.error(message)
    with signup_tab:
        with st.form("signup_form"):
            name = st.text_input("Display name")
            email = st.text_input("Email address", key="signup_email")
            password = st.text_input("Password (minimum 8 characters)", type="password", key="signup_password")
            submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if submitted:
            ok, message, user = register(email, name, password)
            if ok:
                st.session_state.user = user
                st.rerun()
            st.error(message)
    with guest_tab:
        with st.form("guest_form"):
            nickname = st.text_input("Nickname")
            submitted = st.form_submit_button("Continue as guest", type="primary", use_container_width=True)
        if submitted:
            ok, message, user = guest_user(nickname)
            if ok:
                st.session_state.user = user
                st.rerun()
            st.error(message)
        st.caption("Guest accounts are temporary and do not retain progress.")


def lobby_screen():
    user = st.session_state.user
    show_rules()
    st.markdown('<div class="title">🐍 Snake & Ladder 🪜</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">Hi, {html.escape(user["name"])}! Create a room or join a friend.</div>',
                unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Create a room")
        st.caption("Share the room code with up to 3 friends.")
        if st.button("➕ New game room", type="primary", use_container_width=True):
            st.session_state.room = create_room(user)
            st.rerun()
    with col2:
        st.subheader("Join a room")
        code = st.text_input("Room code", value=st.query_params.get("room", ""), max_chars=5).strip().upper()
        if st.button("Join room", use_container_width=True):
            if not code:
                st.error("Enter a room code.")
            else:
                ok, message = mutate_room(code, lambda state: add_player(state, user))
                if ok:
                    st.session_state.room = code
                    st.rerun()
                st.error(message)


@st.fragment(run_every=2)
def game_view():
    user = st.session_state.user
    code = st.session_state.room
    state = get_state(code)
    if state is None:
        st.warning("This room no longer exists.")
        st.session_state.room = None
        st.rerun()
        return
    if not any(player["id"] == user["id"] for player in state["players"]):
        st.warning("You are no longer in this room.")
        st.session_state.room = None
        st.rerun()
        return
    is_host = state["host"] == user["id"]
    st.markdown('<div class="jungle-bar"><span class="round-icon">⬅</span><span class="boost">🏃 BOOST 🔒</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="roomcode">{html.escape(code)}</div>', unsafe_allow_html=True)
    st.caption("Share this code with your friends.")
    st.markdown(player_chips(state), unsafe_allow_html=True)
    if state["status"] == "waiting":
        st.info(f"Waiting for players… ({len(state['players'])}/{MAX_PLAYERS})")
        if is_host:
            if st.button("▶️ Start game", type="primary", use_container_width=True):
                ok, message = mutate_room(code, lambda s: start_game(s, user["id"]))
                if not ok:
                    st.error(message)
                st.rerun(scope="fragment")
        else:
            st.caption("The host will start the game.")
    else:
        st.markdown(board_html(state), unsafe_allow_html=True)
        last_roll = state["last_roll"]
        face = DICE_FACES[last_roll["value"] - 1] if last_roll else "🎲"
        st.markdown(f'<div class="dice">{face}</div>', unsafe_allow_html=True)
        st.markdown('<div class="player-panel"><div class="player-card"><div style="font-size:2rem">🎲</div><div class="small-label">PLAYER</div></div><div class="player-card computer-card"><div style="font-size:2rem">🎲</div><div class="small-label">FRIENDS</div></div></div>', unsafe_allow_html=True)
        if state["status"] == "playing":
            current = state["players"][state["turn"]]
            if current["id"] == user["id"]:
                if st.button("🎲 Roll the dice", type="primary", use_container_width=True):
                    ok, message = mutate_room(code, lambda s: roll_dice(s, user["id"]))
                    if not ok:
                        st.error(message)
                    st.rerun(scope="fragment")
            else:
                st.info(f"Waiting for {current['name']} to roll…")
        else:
            st.success(f"🏆 {state['winner']} wins!")
            celebration_key = (code, state["winner"])
            if st.session_state.get("celebrated") != celebration_key:
                st.balloons()
                st.session_state.celebrated = celebration_key
            if is_host and st.button("🔁 Rematch", type="primary", use_container_width=True):
                ok, message = mutate_room(code, lambda s: rematch(s, user["id"]))
                if not ok:
                    st.error(message)
                st.rerun(scope="fragment")
    with st.expander("Game log", expanded=True):
        for line in reversed(state["log"][-30:]):
            st.write(line)


def game_screen():
    show_rules()
    st.markdown('<div class="title">🐍 Snake & Ladder 🪜</div>', unsafe_allow_html=True)
    game_view()
    if st.button("🚪 Leave room", use_container_width=True):
        leave_room()
        st.rerun()


def main():
    init_db()
    if "user" not in st.session_state:
        auth_screen()
        return
    with st.sidebar:
        user = st.session_state.user
        st.write(f"**{html.escape(user['name'])}**")
        st.caption("Guest" if user["guest"] else user["email"])
        if st.button("Log out", use_container_width=True):
            leave_room()
            del st.session_state["user"]
            st.rerun()
    if st.session_state.get("room"):
        game_screen()
    else:
        lobby_screen()


main()
