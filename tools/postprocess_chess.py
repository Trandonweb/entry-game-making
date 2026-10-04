import io, json, tarfile, hashlib
from pathlib import Path

ENT = Path("outputs/우노카드_체스_체스.ent")
with tarfile.open(ENT, "r:gz") as t:
    members = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
data = json.loads(members["temp/project.json"].decode())

# ---------------------------------------------------------------------------
# Entry block helpers
# ---------------------------------------------------------------------------
def bid(seed):
    return hashlib.md5(seed.encode()).hexdigest()[:4]

def block(t, params=None, statements=None, seed=""):
    return {
        "id": bid(t + seed + str(params) + str(statements)), "x": 0, "y": 0,
        "type": t, "params": params or [], "statements": statements or [],
        "movable": None, "deletable": 1, "emphasized": False,
        "readOnly": None, "copyable": True, "assemble": True, "extensions": []
    }

def num(v): return {"type":"number", "params":[str(v)]}
def text(v): return {"type":"text", "params":[str(v)]}
def getv(vid): return {"type":"get_variable", "params":[vid,None]}

def setv(vid, value):
    return block("set_variable", [vid, value, None])

# ---------------------------------------------------------------------------
# User function: 체스진행(횟수)(플레이어)
# Entry's function ribbon stores parameters as a linked chain.
# Both parameters are string parameters so the user can pass either a number
# or text; the first is copied into '남은 이동' and the second into '현재 턴'.
# ---------------------------------------------------------------------------
func_id = "chess_turn"
p1 = "stringParam_ct01"
p2 = "stringParam_ct02"

def param_block(pid):
    return block("function_field_string", [pid, None])

label = block(
    "function_field_label",
    ["체스진행", param_block(p1)],
    seed="label"
)
# Chain the second ribbon parameter through the first field's second slot.
label["params"][1]["params"][1] = param_block(p2)

body = [
    setv("mlw3", {"type":"stringParam_ct01", "params":[]}),
    setv("nktz", {"type":"stringParam_ct02", "params":[]}),
    block("message_cast", ["v9go", None], seed="render")
]

fdef = block("function_create", [label, None], [body], seed="chess_turn_def")
fdef["x"] = 50
fdef["y"] = 30

new_func = {
    "id": func_id,
    "type": "normal",
    "localVariables": [],
    "useLocalVariables": False,
    "content": json.dumps([[fdef]], ensure_ascii=False)
}

# Keep every existing function (including the existing harmless '폰' function)
# and replace only an older copy of our own function if present.
funcs = [f for f in data.get("functions", []) if f.get("id") != func_id]
funcs.append(new_func)
data["functions"] = funcs

# ---------------------------------------------------------------------------
# Preserve the existing chess engine.  Only replace the visible presentation
# layer with the user's manually arranged coordinates.
# ---------------------------------------------------------------------------
def svg(w, h, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>'

def asset(name, content):
    raw = content.encode()
    fn = hashlib.md5((name + content).encode()).hexdigest()
    path = f"temp/{fn[:2]}/{fn[2:4]}/image/{fn}.svg"
    members[path] = raw
    return fn

def pic(pid, name, fn, w, h):
    return {"id":pid,"name":name,"filename":fn,
            "fileurl":f"temp/{fn[:2]}/{fn[2:4]}/image/{fn}.svg",
            "imageType":"svg","dimension":{"width":w,"height":h},"scale":100}

def oid(s): return hashlib.md5(s.encode()).hexdigest()[:8]

def visible_obj(name, content, w, h, x, y, script="[[]]"):
    fn = asset(name, content)
    pid = oid("pic:" + name)
    return {
        "id": oid("obj:" + name), "name": name, "order": -10000,
        "objectType":"sprite", "rotateMethod":"free", "scene":"sc01",
        "lock":False,
        "sprite":{"pictures":[pic(pid,name,fn,w,h)],"sounds":[]},
        "selectedPictureId":pid, "script":script,
        "entity":{"x":x,"y":y,"regX":w/2,"regY":h/2,
                  "scaleX":1,"scaleY":1,"rotation":0,"direction":90,
                  "width":w,"height":h,"font":"undefinedpx ","visible":True}
    }

bg = svg(480,360,
    '<rect width="480" height="360" fill="#17202b"/>'
    '<rect x="8" y="8" width="464" height="344" rx="10" fill="#202b38" stroke="#506070" stroke-width="2"/>'
    '<text x="240" y="27" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold" fill="white">UNO CARD + CHESS</text>')

board_parts=[]
for r in range(8):
    for c in range(8):
        col="#f0d9b5" if (r+c)%2==0 else "#b58863"
        board_parts.append(f'<rect x="{c*40}" y="{r*40}" width="40" height="40" fill="{col}"/>')
board = svg(320,320,''.join(board_parts)+'<rect width="320" height="320" fill="none" stroke="#111" stroke-width="4"/>')
panel = svg(120,300,
    '<rect x="2" y="2" width="116" height="296" rx="10" fill="#303b49" stroke="#718096" stroke-width="2"/>'
    '<text x="60" y="27" text-anchor="middle" font-family="sans-serif" font-size="15" font-weight="bold" fill="white">UNO CARD</text>'
    '<rect x="22" y="48" width="76" height="100" rx="8" fill="white" stroke="#111" stroke-width="3"/>'
    '<text x="60" y="105" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="bold" fill="#111">CARD</text>')

# Remove only old visible presentation objects. Logic objects remain untouched.
visible_names = {"게임 배경","체스판","UNO 패널"}
for color in ("흑","백"):
    for k in ("룩","나이트","비숍","퀸","킹"):
        for f in "ABCDEFGH": visible_names.add(f"{color} {k} {f}")
    for f in "ABCDEFGH": visible_names.add(f"{color} 폰 {f}")
for n in ("뽑기버튼","사용버튼","턴종료버튼"):
    visible_names.add(n)

data["objects"] = [o for o in data["objects"] if o.get("name") not in visible_names]

vis = [visible_obj("게임 배경",bg,480,360,0,0)]
b = visible_obj("체스판",board,320,320,-70,0)
b["entity"]["scaleX"] = 0.825; b["entity"]["scaleY"] = 0.825
vis.append(b)

files = "ABCDEFGH"
kinds = ["룩","나이트","비숍","퀸","킹","비숍","나이트","룩"]
symbols = {"킹":"♔","퀸":"♕","룩":"♖","비숍":"♗","나이트":"♘","폰":"♙"}
for color,fill,stroke,y in [("흑","#30343b","#eee",115.5),("백","#f7f7f2","#222",-115.5)]:
    for c,k in enumerate(kinds):
        body=svg(40,40,f'<text x="20" y="31" text-anchor="middle" font-family="DejaVu Sans,sans-serif" font-size="32" font-weight="bold" fill="{fill}" stroke="{stroke}" stroke-width="1">{symbols[k]}</text>')
        vis.append(visible_obj(f"{color} {k} {files[c]}",body,40,40,-185.5+c*33,y))
for color,fill,stroke,y in [("흑","#30343b","#eee",82.5),("백","#f7f7f2","#222",-82.5)]:
    for c in range(8):
        body=svg(40,40,f'<text x="20" y="31" text-anchor="middle" font-family="DejaVu Sans,sans-serif" font-size="32" font-weight="bold" fill="{fill}" stroke="{stroke}" stroke-width="1">{symbols["폰"]}</text>')
        vis.append(visible_obj(f"{color} 폰 {files[c]}",body,40,40,-185.5+c*33,y))

vis.append(visible_obj("UNO 패널",panel,120,300,170,10))

# Button SVGs retain the positions from the uploaded layout.
def button(label, fill):
    return svg(100,34,f'<rect x="1" y="1" width="98" height="32" rx="8" fill="{fill}"/><text x="50" y="23" text-anchor="middle" font-family="sans-serif" font-size="15" font-weight="bold" fill="white">{label}</text>')
vis.append(visible_obj("뽑기버튼",button("카드 뽑기","#3b6fd4"),100,34,170,95))
vis[-1]["entity"]["scaleX"]=0.85; vis[-1]["entity"]["scaleY"]=0.85
vis.append(visible_obj("사용버튼",button("카드 사용","#2e9e4f"),100,34,170,45))
vis[-1]["entity"]["scaleX"]=0.85; vis[-1]["entity"]["scaleY"]=0.85
vis.append(visible_obj("턴종료버튼",button("턴 종료","#c0392b"),100,34,170,-5))
vis[-1]["entity"]["scaleX"]=0.85; vis[-1]["entity"]["scaleY"]=0.85

# Reconnect the visible interaction objects to the already-built chess engine.
def msg(mid): return block("message_cast", [mid,None])
def click_thread(message_id):
    return json.dumps([[block("when_object_click",[None]),msg(message_id)]],ensure_ascii=False)

for o in vis:
    n=o["name"]
    if n=="뽑기버튼": o["script"]=click_thread(next(m["id"] for m in data["messages"] if m["name"]=="do_draw"))
    elif n=="사용버튼": o["script"]=click_thread(next(m["id"] for m in data["messages"] if m["name"]=="do_use"))
    elif n=="턴종료버튼": o["script"]=click_thread(next(m["id"] for m in data["messages"] if m["name"]=="do_end"))

data["objects"].extend(vis)
data["interface"]["canvasWidth"] = 480
data["interface"]["canvasHeight"] = 360
data["name"] = "우노카드 + 체스"

members["temp/project.json"] = json.dumps(data, ensure_ascii=False, separators=(",",":")).encode()
tmp = ENT.with_suffix(".tmp.ent")
with tarfile.open(tmp,"w:gz",compresslevel=6) as t:
    for path, raw in members.items():
        ti=tarfile.TarInfo(path); ti.size=len(raw); ti.mtime=0; ti.mode=0o644
        t.addfile(ti,io.BytesIO(raw))
tmp.replace(ENT)
print("installed chess presentation + 체스진행(횟수)(플레이어); UNO logic untouched")
