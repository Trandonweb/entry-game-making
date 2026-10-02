import json, random, string, hashlib, tarfile, io, os

# 「우노카드 + 체스」 Entry .ent 생성기
# GitHub Actions에서 실행되도록 ChatGPT 실행환경 전용 경로를 제거한 버전입니다.

rnd = random.Random(2024)
used = set()

def nid():
    while True:
        s = ''.join(rnd.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        if s not in used:
            used.add(s)
            return s

def fl(xs):
    out = []
    for x in xs:
        if isinstance(x, list):
            out += fl(x)
        elif x is not None:
            out.append(x)
    return out

def blk(t, p=None, st=None):
    return {
        "id": nid(), "x": 0, "y": 0, "type": t,
        "params": p if p is not None else [],
        "statements": st or [], "movable": None, "deletable": 1,
        "emphasized": False, "readOnly": None, "copyable": True,
        "assemble": True, "extensions": []
    }

VARS, LISTS, MSGS, OBJ = {}, {}, {}, {}

def VAR(n):
    if n not in VARS:
        VARS[n] = {"id": nid(), "name": n, "shown": False, "x": 0, "y": 0, "obj": None}
    return VARS[n]["id"]

def shown(n, x, y):
    VAR(n)
    VARS[n].update(shown=True, x=x, y=y)

def local(obj, *names):
    for n in names:
        VAR(n)
        VARS[n]["obj"] = obj

def LID(n):
    if n not in LISTS:
        LISTS[n] = {"id": nid(), "name": n, "array": []}
    return LISTS[n]["id"]

def MID(n):
    if n not in MSGS:
        MSGS[n] = nid()
    return MSGS[n]

def a(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, (int, float)):
        return blk("number", [str(x)])
    return blk("text", [x])

def V(n): return blk("get_variable", [VAR(n),None])
def op(o, x, y): return blk("calc_basic", [a(x), o, a(y)])
def add(x,y): return op("PLUS",x,y)
def sub(x,y): return op("MINUS",x,y)
def mul(x,y): return op("MULTIPLE",x,y)
def cmp_(o,x,y): return blk("boolean_basic_operator",[a(x),o,a(y)])
def eq(x,y): return cmp_("EQUAL",x,y)
def ne(x,y): return cmp_("NOT_EQUAL",x,y)
def gt(x,y): return cmp_("GREATER",x,y)
def lt(x,y): return cmp_("LESS",x,y)
def ge(x,y): return cmp_("GREATER_OR_EQUAL",x,y)
def le(x,y): return cmp_("LESS_OR_EQUAL",x,y)
def AND(x,y): return blk("boolean_and_or",[x,"AND",y])
def OR(x,y): return blk("boolean_and_or",[x,"OR",y])
def item(l,i): return blk("value_of_index_from_list",[None,LID(l),None,a(i),None])
def ln(l): return blk("length_of_list",[None,LID(l),None])
def rand(x,y): return blk("calc_rand",[None,a(x),None,a(y),None])
def idx(c,r): return add(mul(sub(c,1),8),r)
def S(n,x): return blk("set_variable",[VAR(n),a(x),None])
def C(n,x): return blk("change_variable",[VAR(n),a(x),None])
def LA(l,x): return blk("add_value_to_list",[a(x),LID(l),None])
def LR(l,i): return blk("remove_value_from_list",[a(i),LID(l),None])
def LS(l,i,x): return blk("change_value_list_index",[a(x),LID(l),a(i),None])
def CAST(m): return blk("message_cast",[MID(m),None])
def CASTW(m): return blk("message_cast_wait",[MID(m),None])
def REP(n,*b): return blk("repeat_basic",[a(n),None],[fl(b)])
def IF(c,*b): return blk("_if",[c,None],[fl(b)])
def IFE(c,t,f): return blk("if_else",[c,None],[fl([t]),fl([f])])
def CLONE(): return blk("create_clone",["self",None])
def DEL(): return blk("delete_clone",[None])
def SHOW(): return blk("show",[None])
def CLEAR(l): return REP(ln(l), LR(l,1))
def MSG(t): return S("안내",t)
def WHEN(m): return blk("when_message_cast",[MID(m),None])
def RUN(): return blk("when_run_button_click",[None])
def CLK(): return blk("when_object_click",[None])
def CST(): return blk("when_clone_start",[None])

def svg(w,h,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>'

def btn(t,w=100,h=34,col="#3b6fd4"):
    return svg(w,h,f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="8" fill="{col}"/><text x="{w/2}" y="{h/2+6}" font-size="16" font-weight="bold" text-anchor="middle" fill="#fff" font-family="sans-serif">{t}</text>')

def piece(col,t):
    bg,stroke,text = ("#f4f4f4","#222","#222") if col=="백" else ("#333","#ddd","#fff")
    return svg(64,64,f'<circle cx="32" cy="32" r="28" fill="{bg}" stroke="{stroke}" stroke-width="3"/><text x="32" y="42" font-size="{22 if len(t)<3 else 15}" font-weight="bold" text-anchor="middle" fill="{text}" font-family="sans-serif">{t}</text>')

def sq(c): return svg(56,56,f'<rect width="56" height="56" fill="{c}"/>')

TYPES = ["킹","퀸","룩","비숍","나이트","폰"]
names = ["게임관리","판정","덱","판데이터","칸_밝음","칸_어두움","말","힌트","선택창","뽑기버튼","사용버튼","턴종료버튼"]
SC = {n: [] for n in names}
for n in names: OBJ[n] = nid()

PICS = {}
def pics(obj,*ps): PICS[obj] = list(ps)
BLANK=("blank",svg(4,4,'<rect width="4" height="4" fill="none"/>'),4,4)
for n in ["게임관리","판정","덱","판데이터"]: pics(n,BLANK)
pics("칸_밝음",("light",sq("#f0d9b5"),56,56))
pics("칸_어두움",("dark",sq("#b58863"),56,56))
pics("말",*[(c+t,piece(c,t),64,64) for c in ("백","흑") for t in TYPES])
pics("힌트",("hint",svg(56,56,'<rect x="2" y="2" width="52" height="52" fill="#00e676" fill-opacity=".45" stroke="#00b248" stroke-width="4"/>'),56,56))
PT=["퀸","룩","비숍","나이트","폰"]
pics("선택창",*[(t,btn(t,80,28,"#666"),80,28) for t in PT])
pics("뽑기버튼",("b",btn("카드 뽑기",100,34)))
pics("사용버튼",("b",btn("카드 사용",100,34,"#2e9e4f")))
pics("턴종료버튼",("b",btn("턴 종료",100,34,"#c0392b")))

PID={}
for o,ps in PICS.items():
    for p in ps: PID[(o,p[0])] = nid()

def costume(o,n):
    return blk("change_to_some_shape",[blk("get_pictures",[PID[(o,n)]]),None])

for n,x,y in [
    ("현재 턴",4,26),("남은 이동",4,50),("카드 색",4,74),("카드 값",4,98),
    ("안내",130,2),("선택 말 색",375,26),("선택 말 종류",375,50),
    ("선택 열",375,74),("선택 행",375,98)
]:
    shown(n,x,y)

def alias(py,ko): VARS[py]=VARS[ko]
for py,ko in [
    ("turn","현재 턴"),("moves","남은 이동"),("cardC","카드 색"),("cardV","카드 값"),
    ("selColor","선택 말 색"),("selType","선택 말 종류"),("selCol","선택 열"),("selRow","선택 행")
]: alias(py,ko)

STATIC={
    "files":list("ABCDEFGH"), "ptypes":PT, "backtypes":back,
    "dcl":[1,-1,0,0,1,1,-1,-1,1,2,-1,-2,1,2,-1,-2],
    "drl":[0,0,1,-1,1,-1,1,-1,2,1,2,1,-2,-1,-2,-1]
}
for k,v in STATIC.items():
    LID(k); LISTS[k]["array"]=[str(x) for x in v]
for k in ["bc","bt","lc","lr","deckC","deckV","discC","discV","deadC","deadT"]:
    LID(k)
# Entry 리스트는 존재하지 않는 인덱스를 0으로 취급하지 않는다.
# 따라서 병렬 리스트는 항상 함께 채우고, 읽기 전 길이를 검사한다.

# 체스판 데이터
# 64개의 LA 블록을 한 줄에 길게 연결하지 않고, Entry에서 확실하게
# 연결/대상 인식이 되는 8x8 반복 구조로 초기화한다.
back=["룩","나이트","비숍","퀸","킹","비숍","나이트","룩"]
SC["판데이터"].append([
    WHEN("init_board_data"),
    CLEAR("bc"), CLEAR("bt"),
    S("bc_col",1),
    REP(8,
        S("bc_row",1),
        REP(8,
            IF(eq(V("bc_row"),1),
               [LA("bc","백"),LA("bt",item("backtypes",V("bc_col")))],
               [IF(eq(V("bc_row"),2),
                   [LA("bc","백"),LA("bt","폰")],
                   [IF(eq(V("bc_row"),7),
                       [LA("bc","흑"),LA("bt","폰")],
                       [IF(eq(V("bc_row"),8),
                           [LA("bc","흑"),LA("bt",item("backtypes",V("bc_col")))],
                           [LA("bc","-"),LA("bt","-")])])])]),
            C("bc_row",1)
        ),
        C("bc_col",1)
    )
])

# UNO 덱
deck=[CLEAR("deckC"),CLEAR("deckV")]
for col in ["빨강","노랑","초록","파랑"]:
    vals=[str(i) for i in range(10)]+[str(i) for i in range(1,10)]+["+2","+2","금지","금지","순서바꾸기","순서바꾸기"]
    for v in vals: deck += [LA("deckC",col),LA("deckV",v)]
for _ in range(4): deck += [LA("deckC","검정"),LA("deckV","색바꾸기")]
SC["덱"] += [[WHEN("build_deck")]+deck]
SC["덱"] += [[WHEN("shuffle"),REP(300,
    S("di",rand(1,ln("deckC"))),S("dj",rand(1,ln("deckC"))),
    S("dt1",item("deckC",V("di"))),S("dt2",item("deckV",V("di"))),
    LS("deckC",V("di"),item("deckC",V("dj"))),LS("deckV",V("di"),item("deckV",V("dj"))),
    LS("deckC",V("dj"),V("dt1")),LS("deckV",V("dj"),V("dt2"))
)]]
SC["덱"] += [[WHEN("recycle"),
    REP(ln("discC"),LA("deckC",item("discC",1)),LA("deckV",item("discV",1)),LR("discC",1),LR("discV",1)),
    CASTW("shuffle")]]
SC["덱"] += [[WHEN("do_draw"),
    IF(eq(V("phase"),"draw"),
       [IF(eq(ln("deckC"),0),CASTW("recycle")),
        IF(gt(ln("deckC"),0),
           [S("cardC",item("deckC",1)),S("cardV",item("deckV",1)),
            LR("deckC",1),LR("deckV",1),S("phase","card"),
            MSG("카드 사용 버튼을 누르세요")],
           [MSG("덱과 버림더미가 모두 비었습니다")])],
       [MSG("지금은 카드를 뽑을 수 없습니다")])]]

# 보드 칸
for o,tag,target in [("칸_밝음","L",1),("칸_어두움","D",0)]:
    P,Cc,R=tag+"par",tag+"col",tag+"row"
    local(OBJ[o],P,Cc,R)
    SC[o] += [
        [WHEN("build_board"),S(P,0),S(Cc,1),
         REP(8,S(P,V(P)),S(R,1),REP(8,IF(eq(V(P),target),CLONE()),S(P,sub(1,V(P))),C(R,1)),S(P,sub(1,V(P))),C(Cc,1))],
        [CST(),SHOW()],
        [WHEN("clear_squares"),DEL()]
    ]

# 말 렌더링과 선택
local(OBJ["말"],"pcol","prow","pk","pcc","pty","hit")
SC["말"] += [
    [WHEN("render"),CASTW("clear_pieces"),
     IF(AND(eq(ln("bc"),64),eq(ln("bt"),64)),
        [S("pcol",1),
         REP(8,S("prow",1),REP(8,S("pk",idx(V("pcol"),V("prow"))),
            IF(ne(item("bc",V("pk")),"-"),
               [S("pcc",item("bc",V("pk"))),S("pty",item("bt",V("pk"))),CLONE()]),C("prow",1)),C("pcol",1))],
        [MSG("체스판 데이터가 아직 준비되지 않았습니다")])],
    [CST(),SHOW()],
    [WHEN("clear_pieces"),DEL()],
    [CLK(),S("pk",idx(V("pcol"),V("prow"))),
     IFE(eq(V("phase"),"move"),
         [IFE(eq(item("bc",V("pk")),V("turn")),
              [S("sel_c",V("pcol")),S("sel_r",V("prow")),
               S("selColor",item("bc",V("pk"))),S("selType",item("bt",V("pk"))),
               S("selCol",item("files",V("pcol"))),S("selRow",V("prow")),
               CASTW("clear_hints"),CASTW("calc_legal"),CAST("show_hints")],
              [MSG("자기 말만 움직일 수 있습니다")])],
         [IF(eq(V("phase"),"recolor1"),
             IF(AND(eq(item("bc",V("pk")),V("turn")),ne(item("bt",V("pk")),"킹")),
                [S("sel_c",V("pcol")),S("sel_r",V("prow")),S("phase","recolor2"),
                 MSG("바꿀 종류를 오른쪽에서 고르세요"),CAST("show_picker")]))])]
]

# 힌트
local(OBJ["힌트"],"hi","hc","hr")
SC["힌트"] += [
    [WHEN("show_hints"),S("hi",1),
     IF(AND(gt(ln("lc"),0),gt(ln("lr"),0)),
        [REP(ln("lc"),S("hc",item("lc",V("hi"))),S("hr",item("lr",V("hi"))),CLONE(),C("hi",1))])],
    [CST(),SHOW()],
    [WHEN("clear_hints"),DEL()],
    [CLK(),S("qc",V("hc")),S("qr",V("hr")),CAST("do_move")]
]

# 선택창
local(OBJ["선택창"],"bi","bty","by")
SC["선택창"] += [
    [WHEN("show_picker"),CASTW("clear_picker"),S("bi",1),
     REP(5,S("bty",item("ptypes",V("bi"))),S("by",sub(35,mul(30,V("bi")))),CLONE(),C("bi",1))],
    [CST(),SHOW()],
    [CLK(),S("pick",V("bty")),CAST("picked")],
    [WHEN("clear_picker"),DEL()]
]

for o,m in [("뽑기버튼","do_draw"),("사용버튼","do_use"),("턴종료버튼","do_end")]:
    SC[o].append([CLK(),CAST(m)])

# 이동 판정: 기본적인 가로 이동 후보 생성
SC["판정"] += [
    [WHEN("calc_legal"),
     CLEAR("lc"),CLEAR("lr"),
     S("sc",V("sel_c")),S("sr",V("sel_r")),
     S("qk",idx(V("sc"),V("sr"))),
     IF(AND(ge(V("sc"),1),le(V("sc"),8)),
        [IF(AND(ge(V("sr"),1),le(V("sr"),8)),
             [IF(AND(ge(V("qk"),1),le(V("qk"),ln("bc"))),
                  [IF(AND(ge(V("qk"),1),le(V("qk"),ln("bt"))),
                       [S("mc",item("bc",V("qk"))),S("mt",item("bt",V("qk"))),
                        CASTW("gen_legal")])])])])],
    [WHEN("gen_legal"),
     S("tc",V("sc")),S("tr",V("sr")),
     REP(7,
         C("tc",1),
         IF(AND(ge(V("tc"),1),le(V("tc"),8)),
            [S("rk",idx(V("tc"),V("sr"))),
             IF(AND(ge(V("rk"),1),le(V("rk"),ln("bc"))),
                [IF(AND(ge(V("rk"),1),le(V("rk"),ln("bt"))),
                     [IF(eq(item("bc",V("rk")),"-"),
                         [LA("lc",V("tc")),LA("lr",V("sr"))])])])]))]
]
# 게임 관리자
SC["게임관리"] += [
    [RUN(),S("turn","백"),S("flip",0),S("skip",0),S("win",0),
     S("moves",0),S("cardC","-"),S("cardV","-"),S("phase","draw"),
     S("sel_c",0),S("sel_r",0),S("selColor","-"),S("selType","-"),
     S("selCol","-"),S("selRow","-"),MSG("카드 뽑기 버튼을 누르세요"),
     CLEAR("deadC"),CLEAR("deadT"),CLEAR("discC"),CLEAR("discV"),
     CASTW("init_board_data"),CASTW("build_deck"),CASTW("shuffle"),
     CASTW("clear_squares"),CASTW("build_board"),CASTW("render")],
    [WHEN("do_use"),
     IF(eq(V("phase"),"card"),
        [LA("discC",V("cardC")),LA("discV",V("cardV")),
         IFE(eq(V("cardV"),"+2"),
             [S("moves",2),S("phase","move"),MSG("+2: 연속 이동 2회")],
             [IFE(eq(V("cardV"),"금지"),
                  [S("skip",1),S("moves",1),S("phase","move"),MSG("금지: 이번 턴 이동")],
                  [IFE(eq(V("cardV"),"순서바꾸기"),
                       [S("flip",sub(1,V("flip"))),CASTW("render"),S("moves",1),S("phase","move"),MSG("보드가 180도 회전했습니다")],
                       [IFE(eq(V("cardV"),"색바꾸기"),
                            [S("phase","recolor1"),MSG("바꿀 말을 클릭하세요")],
                            [S("moves",V("cardV")),S("phase","move"),MSG("말을 움직이세요")])])])])])],
    [WHEN("do_end"),IF(eq(V("phase"),"move"),CAST("end_turn"))],
    [WHEN("end_turn"),
     IFE(eq(V("skip"),1),
         [S("skip",0)],
         [IFE(eq(V("turn"),"백"),[S("turn","흑")],[S("turn","백")])]),
     S("phase","draw"),S("cardC","-"),S("cardV","-"),S("moves",0),
     CAST("clear_hints"),MSG("카드를 뽑으세요")],
    [WHEN("do_move"),
     IF(eq(V("phase"),"move"),
        [IF(AND(ge(V("sel_c"),1),le(V("sel_c"),8)),
             [IF(AND(ge(V("sel_r"),1),le(V("sel_r"),8)),
                  [IF(AND(ge(V("qc"),1),le(V("qc"),8)),
                       [IF(AND(ge(V("qr"),1),le(V("qr"),8)),
                            [S("mk",idx(V("sel_c"),V("sel_r"))),S("mk2",idx(V("qc"),V("qr"))),
                             IF(AND(ge(V("mk"),1),le(V("mk"),ln("bc"))),
                                [IF(AND(ge(V("mk"),1),le(V("mk"),ln("bt"))),
                                     [IF(AND(ge(V("mk2"),1),le(V("mk2"),ln("bc"))),
                                          [IF(AND(ge(V("mk2"),1),le(V("mk2"),ln("bt"))),
                                               [S("mc",item("bc",V("mk"))),S("mt",item("bt",V("mk"))),
                                                IF(ne(item("bc",V("mk2")),"-"),
                                                   [LA("deadC",item("bc",V("mk2"))),LA("deadT",item("bt",V("mk2"))),
                                                    IF(eq(item("bt",V("mk2")),"킹"),S("win",1))]),
                                                IF(AND(eq(V("mt"),"폰"),OR(eq(V("qr"),8),eq(V("qr"),1))),S("mt","퀸")),
                                                LS("bc",V("mk2"),V("mc")),LS("bt",V("mk2"),V("mt")),
                                                LS("bc",V("mk"),"-"),LS("bt",V("mk"),"-"),
                                                CASTW("clear_hints"),CASTW("render"),
                                                IFE(eq(V("win"),1),
                                                    [S("phase","over"),MSG("게임 종료!")],
                                                    [C("moves",-1),IF(le(V("moves"),0),CAST("end_turn"),MSG("계속 이동하세요"))])])])])])])])])])],
        [MSG("지금은 말을 이동할 수 없습니다")])],
    [WHEN("picked"),
     IF(eq(V("phase"),"recolor2"),
        [LS("bt",idx(V("sel_c"),V("sel_r")),V("pick")),
         S("phase","move"),S("moves",1),CASTW("clear_picker"),CASTW("render"),
         MSG("말을 움직이세요")])]
]

# 그림 파일과 Entry 프로젝트 JSON 구성
objects=[]
files={}
for i,n in enumerate(names):
    ps=[]
    for item in PICS[n]:
        if len(item) == 2:
            pn,sv = item
            w,h = 100,34
        else:
            pn,sv,w,h = item
        fn=hashlib.md5((n+pn+sv).encode()).hexdigest()
        path=f"temp/{fn[:2]}/{fn[2:4]}/image/{fn}.svg"
        files[path]=sv.encode()
        ps.append({"id":PID[(n,pn)],"name":pn,"filename":fn,"fileurl":path,
                   "imageType":"svg","dimension":{"width":w,"height":h},"scale":100})
    first=PICS[n][0]
    if len(first)==2:
        w,h=100,34
    else:
        w,h=first[2],first[3]
    vis=n in ("뽑기버튼","사용버튼","턴종료버튼")
    scale={"말":0.4,"칸_밝음":0.5,"칸_어두움":0.5,"힌트":0.5}.get(n,1)
    pos={"뽑기버튼":(-180,-10),"사용버튼":(-180,-50),"턴종료버튼":(-180,-90)}.get(n,(0,0))
    threads=SC[n]
    for k,t in enumerate(threads):
        if t:
            t[0]["x"]=20+(k%3)*700
            t[0]["y"]=20+(k//3)*900
    objects.append({
        "id":OBJ[n],"name":n,"order":i,"objectType":"sprite",
        "rotateMethod":"free","scene":"sc01","lock":False,
        "sprite":{"pictures":ps,"sounds":[]},
        "selectedPictureId":PID[(n,PICS[n][0][0])],
        "script":json.dumps(threads,ensure_ascii=False),
        "entity":{"x":pos[0],"y":pos[1],"regX":w/2,"regY":h/2,
                  "scaleX":scale,"scaleY":scale,"rotation":0,"direction":90,
                  "width":w,"height":h,"font":"undefinedpx ","visible":vis}
    })

variables=[]
seen=set()
for n,v in VARS.items():
    if v["id"] in seen: continue
    seen.add(v["id"])
    obj=v["obj"]
    variables.append({
        "name":v["name"],"id":v["id"],"visible":v["shown"],
        "value":"" if v["name"]=="안내" else "0",
        "variableType":"variable","isCloud":False,"isRealTime":False,
        "cloudDate":False,"object":obj,"x":v["x"],"y":v["y"]
    })

for l in LISTS.values():
    variables.append({
        "name":l["name"],"id":l["id"],"visible":False,"value":"",
        "variableType":"list","isCloud":False,"isRealTime":False,
        "cloudDate":False,"object":None,"x":0,"y":0,"width":100,
        "height":120,"array":[{"data":d} for d in l["array"]]
    })

proj={
    "name":"우노카드 + 체스 v0.1.4","category":"기타","speed":60,
    "objects":objects,"scenes":[{"name":"장면 1","id":"sc01"}],
    "variables":variables,
    "messages":[{"id":i,"name":n} for n,i in MSGS.items()],
    "functions":[],"tables":[],"externalModules":[],"expansionBlocks":[],
    "aiUtilizeBlocks":[],"hardwareLiteBlocks":[],"externalModulesLite":[],
    "learning":{},"cloudVariable":"[]","isPracticalCourse":False,
    "interface":{"canvasWidth":640,"menuWidth":280,"object":objects[0]["id"]}
}

os.makedirs("outputs",exist_ok=True)
out="outputs/우노카드_체스.ent"
with tarfile.open(out,"w:gz") as t:
    def addb(path,data):
        ti=tarfile.TarInfo(path)
        ti.size=len(data)
        t.addfile(ti,io.BytesIO(data))
    addb("temp/project.json",json.dumps(proj,ensure_ascii=False).encode())
    for path,data in files.items():
        addb(path,data)

print(f"생성 완료: {out}")
print(f"크기: {os.path.getsize(out)} bytes")
print(f"오브젝트: {len(objects)}, 변수/리스트: {len(variables)}, 메시지: {len(MSGS)}")
