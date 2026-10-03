import io, json, tarfile, hashlib
from pathlib import Path

ENT = Path('outputs/우노카드_체스.ent')

def block(t, params=None, statements=None):
    seed = t + json.dumps(params or [], ensure_ascii=False) + json.dumps(statements or [], ensure_ascii=False)
    return {'id': hashlib.md5(seed.encode()).hexdigest()[:4], 'x': 0, 'y': 0, 'type': t,
            'params': params or [], 'statements': statements or [], 'movable': None,
            'deletable': 1, 'emphasized': False, 'readOnly': None, 'copyable': True,
            'assemble': True, 'extensions': []}

def text(v): return {'type':'text','params':[str(v)]}
def num(v): return {'type':'number','params':[str(v)]}
def var(vid): return {'type':'get_variable','params':[vid,None]}
def add(x,y): return block('calc_basic',[x if isinstance(x,dict) else num(x),'PLUS',y if isinstance(y,dict) else num(y)])
def get_item(lid,i): return block('value_of_index_from_list',[None,lid,None,var(i) if isinstance(i,str) else num(i),None])
def setv(vid,x): return block('set_variable',[vid,x if isinstance(x,dict) else text(x),None])
def addlist(lid,x): return block('add_value_to_list',[x if isinstance(x,dict) else text(x),lid,None])
def length(lid): return block('length_of_list',[None,lid,None])
def clear(lid): return block('repeat_basic',[length(lid),None],[[block('remove_value_from_list',[num(1),lid,None])]])
def repeat(n,body): return block('repeat_basic',[num(n),None],[body])
def change(vid,x): return block('change_variable',[vid,num(x),None])

def read():
    with tarfile.open(ENT,'r:gz') as t:
        return {m.name:t.extractfile(m).read() for m in t.getmembers() if m.isfile()}

def write(members):
    tmp=ENT.with_suffix('.tmp.ent')
    with tarfile.open(tmp,'w:gz',compresslevel=6) as t:
        for path,raw in members.items():
            ti=tarfile.TarInfo(path); ti.size=len(raw); ti.mtime=0; ti.mode=0o644
            t.addfile(ti,io.BytesIO(raw))
    tmp.replace(ENT)

def ensure_list(data,name,values=None):
    for v in data['variables']:
        if v.get('name') == name and v.get('variableType') == 'list':
            return v['id']
    vid=hashlib.md5(('list:'+name).encode()).hexdigest()[:4]
    data['variables'].append({'id':vid,'name':name,'shown':False,'x':0,'y':0,'obj':None,
                              'variableType':'list','value':'0','array':values or []})
    return vid

def svg(w,h,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>'

def make_asset(members,name,svg_text):
    raw=svg_text.encode(); fn=hashlib.md5((name+svg_text).encode()).hexdigest()
    path=f'temp/{fn[:2]}/{fn[2:4]}/image/{fn}.svg'; members[path]=raw
    return fn,path

def make_obj(members,name,svg_text,w,h,x,y,order=-100):
    fn,path=make_asset(members,name,svg_text); pid=hashlib.md5(('pic:'+name).encode()).hexdigest()[:4]
    oid=hashlib.md5(('obj:'+name).encode()).hexdigest()[:4]
    return {'id':oid,'name':name,'order':order,'objectType':'sprite','rotateMethod':'free','scene':'sc01','lock':False,
            'sprite':{'pictures':[{'id':pid,'name':name,'filename':fn,'fileurl':path,'imageType':'svg',
                                  'dimension':{'width':w,'height':h},'scale':100}], 'sounds':[]},
            'selectedPictureId':pid,'script':'[[]]',
            'entity':{'x':x,'y':y,'regX':w/2,'regY':h/2,'scaleX':1,'scaleY':1,'rotation':0,
                      'direction':90,'width':w,'height':h,'font':'undefinedpx ','visible':True}}

def main():
    members=read(); data=json.loads(members['temp/project.json'].decode())
    vars_by_name={v['name']:v['id'] for v in data['variables']}
    dc=vars_by_name.get('덱 색') or vars_by_name.get('deckC')
    dv=vars_by_name.get('덱 카드') or vars_by_name.get('deckV')
    if not dc or not dv:
        raise RuntimeError('deckC/deckV lists not found')

    colors=ensure_list(data,'UNO 색상',['빨강','노랑','초록','파랑'])
    values=ensure_list(data,'UNO 숫자',['0','1','2','3','4','5','6','7','8','9'])
    dci=vars_by_name.get('덱 색상 순번')
    dvi=vars_by_name.get('덱 카드 순번')
    dt1=vars_by_name.get('임시 카드 색')
    dt2=vars_by_name.get('임시 카드 값')
    if not all([dci,dvi,dt1,dt2]):
        raise RuntimeError('deck helper variables not found')

    # Compact function: color + value combinations for normal cards;
    # action cards and wild cards are handled separately.
    body=[clear(dc),clear(dv),setv(dci,num(1))]
    normal=[]
    normal += [setv(dt1,get_item(colors,dci)), setv(dvi,num(1))]
    one_copy=[
        setv(dt2,get_item(values,dvi)),
        addlist(dc,var(dt1)), addlist(dv,var(dt2)),
        change(dvi,1)
    ]
    normal.append(repeat(10,one_copy))
    normal.append(setv(dvi,num(1)))
    normal.append(repeat(9,[
        change(dvi,1),
        setv(dt2,get_item(values,dvi)),
        addlist(dc,var(dt1)), addlist(dv,var(dt2))
    ]))
    # second 1-9 copy (the first loop above already includes 0 once).
    normal.append(setv(dvi,num(1)))
    normal.append(repeat(9,[
        setv(dt2,get_item(values,dvi)),
        addlist(dc,var(dt1)), addlist(dv,var(dt2)),
        change(dvi,1)
    ]))
    for action in ['+2','+2','금지','금지','순서바꾸기','순서바꾸기']:
        normal += [addlist(dc,var(dt1)),addlist(dv,action)]
    normal.append(change(dci,1))
    body.append(repeat(4,normal))
    body.append(repeat(4,[addlist(dc,'검정'),addlist(dv,'색바꾸기')]))

    fid='deck_build_v2'
    label=block('function_field_label',['덱 생성',None])
    fdef=block('function_create',[label,None],[body])
    data['functions']=[f for f in data.get('functions',[]) if f.get('id') != fid]
    data['functions'].append({'id':fid,'type':'normal','localVariables':[],'useLocalVariables':False,
                              'content':json.dumps([[fdef]],ensure_ascii=False)})
    call=block('func_'+fid,[])
    for o in data['objects']:
        if o.get('name')=='덱':
            o['script']=json.dumps([[block('when_run_button_click',[None]),call]],ensure_ascii=False)
            o['entity']['visible']=False
            break

    # Entry stage is 480x360, centered at (0,0). Keep all visible content
    # strictly inside x=-220..220 and y=-160..160.
    old_names={'게임 배경','체스판','UNO 패널'}
    data['objects']=[o for o in data['objects'] if o.get('name') not in old_names]
    vis=[]
    bg=svg(440,320,'<rect width="440" height="320" rx="12" fill="#17202b"/><rect x="3" y="3" width="434" height="314" rx="10" fill="#202b38" stroke="#52606d" stroke-width="2"/><text x="220" y="22" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="white">UNO CARD + CHESS</text>')
    vis.append(make_obj(members,'게임 배경',bg,440,320,0,0,-1000))
    # 280x280 board at x=-60: edges -200..80. Its top/bottom are y=140/-140.
    squares=[]
    for r in range(8):
        for c in range(8):
            col='#f0d9b5' if (r+c)%2==0 else '#b58863'
            squares.append(f'<rect x="{c*35}" y="{r*35}" width="35" height="35" fill="{col}"/>')
    board=svg(280,280,''.join(squares)+'<rect width="280" height="280" fill="none" stroke="#111" stroke-width="3"/>')
    vis.append(make_obj(members,'체스판',board,280,280,-60,0,-900))
    # Pieces centered on each square. y is inverted relative to SVG rows so top rank is +.
    pieces={('백','킹'):'♔',('백','퀸'):'♕',('백','룩'):'♖',('백','비숍'):'♗',('백','나이트'):'♘',('백','폰'):'♙',
            ('흑','킹'):'♚',('흑','퀸'):'♛',('흑','룩'):'♜',('흑','비숍'):'♝',('흑','나이트'):'♞',('흑','폰'):'♟'}
    back=['룩','나이트','비숍','퀸','킹','비숍','나이트','룩']
    for color,row,kinds in [('백',3,back),('흑',-3,back)]:
        for c,k in enumerate(kinds):
            ch=pieces[(color,k)]; fill='#f8f8f8' if color=='백' else '#20242a'; stroke='#111' if color=='백' else '#eee'
            p=svg(30,30,f'<text x="15" y="23" text-anchor="middle" font-family="DejaVu Sans" font-size="25" font-weight="bold" fill="{fill}" stroke="{stroke}" stroke-width="1">{ch}</text>')
            vis.append(make_obj(members,f'{color} {k} {c+1}',p,30,30,-60-122.5+c*35, row*35,-800))
    for color,row in [('백',2),('흑',-2)]:
        ch=pieces[(color,'폰')]; fill='#f8f8f8' if color=='백' else '#20242a'; stroke='#111' if color=='백' else '#eee'
        for c in range(8):
            p=svg(30,30,f'<text x="15" y="23" text-anchor="middle" font-family="DejaVu Sans" font-size="25" font-weight="bold" fill="{fill}" stroke="{stroke}" stroke-width="1">{ch}</text>')
            vis.append(make_obj(members,f'{color} 폰 {c+1}',p,30,30,-60-122.5+c*35,row*35,-800))

    panel=svg(100,280,'<rect x="2" y="2" width="96" height="276" rx="10" fill="#303b49" stroke="#718096" stroke-width="2"/><text x="50" y="24" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="bold" fill="white">UNO</text><rect x="20" y="38" width="60" height="86" rx="7" fill="white" stroke="#111" stroke-width="2"/><text x="50" y="88" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="bold" fill="#111">CARD</text>')
    vis.append(make_obj(members,'UNO 패널',panel,100,280,160,0,-700))

    # Existing interactive buttons are repositioned relative to the right panel.
    for o in data['objects']:
        n=o.get('name')
        if n=='뽑기버튼': o['entity'].update(x=160,y=-65,scaleX=.8,scaleY=.8,visible=True)
        elif n=='사용버튼': o['entity'].update(x=160,y=-105,scaleX=.8,scaleY=.8,visible=True)
        elif n=='턴종료버튼': o['entity'].update(x=160,y=-145,scaleX=.8,scaleY=.8,visible=True)

    data['objects']=vis+data['objects']
    data['interface']['canvasWidth']=480
    data['interface']['object']=vis[0]['id']
    data['name']='우노카드 + 체스 v0.2.1'
    members['temp/project.json']=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
    write(members)
    print('v2.1 deck function + centered stage layout written')

if __name__=='__main__': main()
