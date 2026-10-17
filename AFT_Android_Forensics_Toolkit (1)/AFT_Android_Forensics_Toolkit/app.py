from flask import Flask, render_template, jsonify, request, send_file
from pathlib import Path
import csv, json, hashlib, sqlite3, subprocess, shutil, os, re, html as _html
from datetime import datetime
from collections import Counter
from urllib.parse import urlparse

app = Flask(__name__)
BASE = Path(__file__).parent
DATA = BASE / 'data'
DATA.mkdir(exist_ok=True)
CASE = DATA / 'case.json'
DEFAULT = {
 'case_id':'CT-2026-041',
 'calls':[{'timestamp':'2026-10-12 09:15','contact':'+91 98••• 1428','channel':'CALL','direction':'Incoming','duration':'04:28','risk':'Medium'}],
 'messages':[{'timestamp':'2026-10-12 09:12','contact':'+91 77••• 9041','channel':'SMS','direction':'Incoming','duration':'—','risk':'Low'}],
 'browser_history':[{'timestamp':'2026-10-12 08:40','title':'Example research page','url':'https://example.com/research','browser':'Chrome','visits':'3','risk':'Low'}],
 'app_history':[{'timestamp':'2026-10-12 08:35','app_name':'Chrome','package':'com.android.chrome','event':'Foreground session','duration':'00:14:22','risk':'Low'}]
}
def load_case():
 if not CASE.exists(): CASE.write_text(json.dumps(DEFAULT,indent=2),encoding='utf-8')
 return json.loads(CASE.read_text(encoding='utf-8'))
def save_case(c): CASE.write_text(json.dumps(c,indent=2),encoding='utf-8')
def sha256(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()
def field(row,*keys,default=''):
 for key in keys:
  if row.get(key) not in (None,''): return str(row[key])
 return default

def find_adb():
 found=shutil.which('adb')
 if found: return found
 exe='adb.exe' if os.name=='nt' else 'adb'
 cands=[BASE/'platform-tools'/exe, BASE/'adb'/exe, BASE/exe]
 for env in ('ANDROID_HOME','ANDROID_SDK_ROOT'):
  if os.environ.get(env): cands.append(Path(os.environ[env])/'platform-tools'/exe)
 if os.name=='nt':
  for env in ('LOCALAPPDATA','ProgramFiles','ProgramFiles(x86)','USERPROFILE'):
   v=os.environ.get(env)
   if v: cands+=[Path(v)/'Android'/'Sdk'/'platform-tools'/exe, Path(v)/'platform-tools'/exe, Path(v)/'Downloads'/'platform-tools'/exe]
  cands+=[Path('C:/platform-tools')/exe, Path('C:/adb')/exe]
 else:
  cands+=[Path(x) for x in ('/usr/bin/adb','/usr/local/bin/adb','/snap/bin/adb','/opt/android-sdk/platform-tools/adb','/usr/lib/android-sdk/platform-tools/adb')]
  cands.append(Path.home()/'Android'/'Sdk'/'platform-tools'/'adb')
 for c in cands:
  if c.is_file() and os.access(c,os.X_OK): return str(c)
 return None

_server_checked=False
def start_adb_server(adb):
 # The adb daemon must NOT inherit our capture pipes, otherwise subprocess.run()
 # waits for the daemon to exit and the USB tab hangs until timeout.
 kw=dict(stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 if os.name=='nt': kw['creationflags']=0x08000000  # CREATE_NO_WINDOW
 try: subprocess.Popen([adb,'start-server'],**kw).wait(timeout=20)
 except Exception: pass

def run_adb(args, timeout=10):
 global _server_checked
 adb=find_adb()
 if not adb: return None, 'adb not found. Install Android Platform Tools (Windows: put adb.exe in PATH or in a "platform-tools" folder next to app.py; Linux: sudo apt install adb), then restart AFT.'
 if not _server_checked:
  start_adb_server(adb); _server_checked=True
 try:
  p=subprocess.run([adb,*args],capture_output=True,text=True,timeout=timeout,check=False,stdin=subprocess.DEVNULL)
  return {'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'adb':adb}, None
 except subprocess.TimeoutExpired: return None, 'ADB command timed out. Use the "Restart ADB server" button or run `adb kill-server` then `adb start-server`.'
 except Exception as e: return None, str(e)

def parse_devices(raw):
 devices=[]
 for line in raw.splitlines():
  line=line.strip()
  if not line or line.lower().startswith('list of devices') or line.startswith('*') or line.startswith('adb server'): continue
  parts=line.split()
  if len(parts)<2: continue
  serial=parts[0]
  if parts[1]=='no' and len(parts)>2 and parts[2].startswith('permissions'):
   state='no permissions'; details=' '.join(parts[2:])
  else:
   state=parts[1]; details=' '.join(parts[2:])
  devices.append({'serial':serial,'state':state,'details':details})
 return devices

def usb_bus_phones():
 # OS-level view of USB devices (Linux only) to tell "phone not seen by OS" from "ADB problem"
 if not shutil.which('lsusb'): return ''
 try: return subprocess.run(['lsusb'],capture_output=True,text=True,timeout=5,stdin=subprocess.DEVNULL).stdout
 except Exception: return ''

@app.route('/')
def index(): return render_template('index.html')
@app.route('/api/case')
def api_case():
 c=load_case(); comm=c['calls']+c['messages']
 return jsonify(case_id=c['case_id'],calls=len(c['calls']),messages=len(c['messages']),browser_history=len(c['browser_history']),app_history=len(c['app_history']),contacts=len(set(x.get('contact','') for x in comm if x.get('contact'))),anomalies=sum(1 for group in ('calls','messages','browser_history','app_history') for x in c[group] if x.get('risk')=='High'),communications=sorted(comm,key=lambda x:x.get('timestamp',''),reverse=True),browser_events=sorted(c['browser_history'],key=lambda x:x.get('timestamp',''),reverse=True),app_events=sorted(c['app_history'],key=lambda x:x.get('timestamp',''),reverse=True))
@app.route('/api/import/<kind>',methods=['POST'])
def import_csv(kind):
 if kind not in ('communications','browser','apps'): return jsonify(error='Unsupported import type'),400
 f=request.files.get('file')
 if not f: return jsonify(error='Choose a CSV file'),400
 p=DATA/Path(f.filename).name; f.save(p)
 try:
  with p.open(encoding='utf-8-sig',newline='') as fp: rows=list(csv.DictReader(fp))
  c=load_case()
  for r in rows:
   if kind=='communications':
    item={'timestamp':field(r,'timestamp','date','datetime'),'contact':field(r,'contact','number','address'),'channel':field(r,'channel',default='CALL').upper(),'direction':field(r,'direction'),'duration':field(r,'duration',default='—'),'risk':field(r,'risk',default='Low')}
    (c['messages'] if item['channel'] in ('SMS','MMS','MESSAGE') else c['calls']).append(item)
   elif kind=='browser': c['browser_history'].append({'timestamp':field(r,'timestamp','visit_time','date','last_visit_time'),'title':field(r,'title','page_title'),'url':field(r,'url','URL','visit_url'),'browser':field(r,'browser','source',default='Unknown'),'visits':field(r,'visits','visit_count',default='1'),'risk':field(r,'risk',default='Low')})
   else: c['app_history'].append({'timestamp':field(r,'timestamp','date','time'),'app_name':field(r,'app_name','application','name'),'package':field(r,'package','package_name','packageName'),'event':field(r,'event','event_type','type',default='Usage record'),'duration':field(r,'duration','foreground_time',default='—'),'risk':field(r,'risk',default='Low')})
  save_case(c); return jsonify(status='imported',rows=len(rows),sha256=sha256(p))
 except Exception as e: return jsonify(error=f'Could not import CSV: {e}'),400
@app.route('/api/hash',methods=['POST'])
def hash_upload():
 f=request.files.get('file')
 if not f:return jsonify(error='Choose a file'),400
 p=DATA/Path(f.filename).name; f.save(p); return jsonify(filename=p.name,size_bytes=p.stat().st_size,sha256=sha256(p))
@app.route('/api/inspect-sqlite',methods=['POST'])
def inspect_sqlite():
 f=request.files.get('file')
 if not f:return jsonify(error='Choose a SQLite file'),400
 p=DATA/Path(f.filename).name; f.save(p)
 try:
  con=sqlite3.connect(f'file:{p}?mode=ro',uri=True); names=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
  tables={}
  for t in names: tables[t]=[x[1] for x in con.execute('PRAGMA table_info("'+t.replace('"','""')+'")')]
  con.close(); return jsonify(filename=p.name,sha256=sha256(p),tables=tables)
 except sqlite3.Error as e:return jsonify(error=str(e)),400
@app.route('/api/usb/status')
def usb_status():
 result,error=run_adb(['devices','-l'])
 if error:return jsonify(adb_installed=bool(find_adb()),adb_path=find_adb(),connected=False,devices=[],message=error,raw='',stderr='',lsusb=usb_bus_phones()),200
 raw=result['stdout']; devices=parse_devices(raw)
 ready=[d for d in devices if d['state']=='device']
 states={d['state'] for d in devices}
 if ready: message='Authorized Android device detected.'
 elif 'unauthorized' in states: message='Device detected but not authorized. Unlock the phone and tap "Allow" on the USB debugging prompt (tick "Always allow").'
 elif 'no permissions' in states: message='Linux USB permission problem. Install udev rules (sudo apt install android-sdk-platform-tools-common), replug the phone, then run: adb kill-server && adb start-server.'
 elif 'offline' in states: message='Device is offline. Replug the cable, toggle USB debugging off/on, then restart the ADB server.'
 elif result['returncode']!=0: message=result['stderr'].strip() or 'ADB returned an error.'
 else: message='ADB ran successfully but returned no devices. Use a data-capable USB cable, enable Developer options > USB debugging, set USB mode to File Transfer (MTP), and replug.'
 return jsonify(adb_installed=True,adb_path=result['adb'],connected=bool(ready),devices=devices,message=message,raw=raw,stderr=result['stderr'],returncode=result['returncode'],lsusb=usb_bus_phones())
@app.route('/api/usb/restart',methods=['POST'])
def usb_restart():
 adb=find_adb()
 if not adb:return jsonify(error='adb not found'),503
 try: subprocess.run([adb,'kill-server'],capture_output=True,timeout=10,stdin=subprocess.DEVNULL)
 except Exception: pass
 start_adb_server(adb)
 return jsonify(status='restarted',adb=adb)
@app.route('/api/usb/device-info',methods=['POST'])
def usb_device_info():
 body=request.get_json(silent=True) or {}; serial=body.get('serial','').strip()
 status,err=run_adb(['devices','-l'])
 if err:return jsonify(error=err),503
 available=[(d['serial'],d['state']) for d in parse_devices(status['stdout'])]
 if (serial,'device') not in available:return jsonify(error='Selected device is not authorized/online. Press Detect USB device again and select a device with state `device`.'),400
 props={'Manufacturer':'ro.product.manufacturer','Model':'ro.product.model','Android version':'ro.build.version.release','SDK level':'ro.build.version.sdk','Build fingerprint':'ro.build.fingerprint'}; info={}
 for label,key in props.items():
  r,e=run_adb(['-s',serial,'shell','getprop',key])
  info[label]=r['stdout'].strip() if r and r['returncode']==0 else (e or r['stderr'].strip() or 'Unavailable')
 return jsonify(serial=serial,properties=info,note='Read-only device metadata. No private app data was extracted.')
# ================= AUTO-ACQUISITION, TARGET EXTRACTION, AFT REPORT =================
GROUPS={'calls':'calls','messages':'messages','browser':'browser_history','apps':'app_history'}
CALL_TYPES={'1':'Incoming','2':'Outgoing','3':'Missed','4':'Voicemail','5':'Rejected','6':'Blocked'}
SMS_TYPES={'1':'Incoming','2':'Outgoing','3':'Draft','4':'Outbox','5':'Failed','6':'Queued'}

def ready_serial():
 r,e=run_adb(['devices','-l'])
 if e: return None,e
 devs=parse_devices(r['stdout'])
 for d in devs:
  if d['state']=='device': return d['serial'],None
 if devs: return None,'Device found but state is "%s". Fix it in the USB Device tab (authorize / restart ADB). Showing imported data only.'%devs[0]['state']
 return None,'No Android device connected. Connect and authorize the phone (see USB Device tab). Showing imported data only.'

def parse_rows(out,keys):
 rows=[]; pat=re.compile(r'(?:^|, )('+'|'.join(keys)+r')=')
 for chunk in re.split(r'(?m)^Row: \d+ ',out):
  chunk=chunk.strip('\r\n')
  if '=' not in chunk: continue
  ms=list(pat.finditer(chunk)); rec={}
  for i,m in enumerate(ms):
   end=ms[i+1].start() if i+1<len(ms) else len(chunk)
   v=chunk[m.end():end].strip(); rec[m.group(1)]='' if v=='NULL' else v
  if rec: rows.append(rec)
 return rows

def content_query(serial,uri,proj):
 r,e=run_adb(['-s',serial,'shell','content','query','--uri',uri,'--projection',proj],timeout=90)
 if e: return None,e
 out=r['stdout']+'\n'+r['stderr']
 if re.search(r'Permission Denial|SecurityException|requires android\.permission',out,re.I):
  return None,'Android blocked read access to this data (permission denial). Use the phone maker backup tool, a lawful forensic acquisition, or CSV import.'
 rows=parse_rows(r['stdout'],proj.split(':'))
 if not rows:
  if 'No result found' in out: return [],None
  return None,'Data provider not accessible on this Android version: '+(out.strip()[:160] or 'no output')
 return rows,None

def fmt_ts(ms):
 try: return datetime.fromtimestamp(int(ms)/1000).strftime('%Y-%m-%d %H:%M:%S')
 except Exception: return ''
def fmt_dur(s):
 try: s=int(s)
 except Exception: return '—'
 return f'{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}' if s>=3600 else f'{s//60:02d}:{s%60:02d}'
def dur_secs(d):
 try: p=[int(x) for x in str(d).split(':')]
 except Exception: return 0
 return sum(v*m for v,m in zip(reversed(p),(1,60,3600)))

# ---- browser history: stored-database parsing + live root pull ----
BROWSER_DBS=[
 ('Chrome','com.android.chrome',['app_chrome/Default/History']),
 ('Chrome Beta','com.chrome.beta',['app_chrome/Default/History']),
 ('Brave','com.brave.browser',['app_chrome/Default/History']),
 ('Edge','com.microsoft.emmx',['app_chrome/Default/History']),
 ('Opera','com.opera.browser',['app_opera/Default/History','app_chrome/Default/History']),
 ('Vivaldi','com.vivaldi.browser',['app_chrome/Default/History']),
 ('Samsung Internet','com.sec.android.app.sbrowser',['app_sbrowser/Default/History']),
 ('Firefox','org.mozilla.firefox',['files/places.sqlite','databases/places.sqlite']),
 ('Firefox Beta','org.mozilla.firefox_beta',['files/places.sqlite','databases/places.sqlite']),
]
def _ts_from_unix(sec):
    try: return datetime.fromtimestamp(float(sec)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception: return ''
VISIT_CAP=20000
def parse_browser_db(path,browser='Unknown',source='DB import'):
    """Read a Chrome-family (urls/visits) or Firefox (moz_places/moz_historyvisits) history database. Returns (items,error)."""
    import tempfile
    tmpdir=tempfile.mkdtemp(prefix='aft_')
    work=Path(tmpdir)/'work.sqlite'
    try:
        shutil.copyfile(path,work)
        for ext in ('-wal','-journal'):
            side=Path(str(path)+ext)
            if side.exists(): shutil.copyfile(side,Path(str(work)+ext))
        con=sqlite3.connect(str(work)); items=[]
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def row(ts,title,url,vc): return {'timestamp':ts,'title':title or '','url':url or '','browser':browser,'visits':str(vc),'risk':'Low','source':source}
        if 'urls' in tables:   # Chrome / Chromium family: WebKit epoch (1601, microseconds)
            wk=lambda v:_ts_from_unix(int(v)/1e6-11644473600) if v else ''
            rows=[]
            if 'visits' in tables:
                rows=con.execute('SELECT u.url,u.title,v.visit_time FROM visits v JOIN urls u ON u.id=v.url ORDER BY v.visit_time DESC LIMIT ?',(VISIT_CAP,)).fetchall()
            if rows: items=[row(wk(t),ti,u,1) for u,ti,t in rows]
            else: items=[row(wk(t),ti,u,vc or 1) for u,ti,vc,t in con.execute('SELECT url,title,visit_count,last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT ?',(VISIT_CAP,))]
        elif 'moz_places' in tables:   # Firefox: Unix epoch, microseconds
            fx=lambda v:_ts_from_unix(int(v)/1e6) if v else ''
            rows=[]
            if 'moz_historyvisits' in tables:
                rows=con.execute('SELECT p.url,p.title,h.visit_date FROM moz_historyvisits h JOIN moz_places p ON p.id=h.place_id ORDER BY h.visit_date DESC LIMIT ?',(VISIT_CAP,)).fetchall()
            if rows: items=[row(fx(t),ti,u,1) for u,ti,t in rows]
            else: items=[row(fx(t),ti,u,vc or 1) for u,ti,vc,t in con.execute('SELECT url,title,visit_count,last_visit_date FROM moz_places WHERE last_visit_date IS NOT NULL ORDER BY last_visit_date DESC LIMIT ?',(VISIT_CAP,))]
        else:
            con.close(); return None,'Not a recognised browser history database (no Chrome "urls" or Firefox "moz_places" table found).'
        con.close(); return items,None
    except sqlite3.Error as e: return None,f'SQLite error: {e}'
    except Exception as e: return None,str(e)
    finally: shutil.rmtree(tmpdir,ignore_errors=True)

def adb_bytes(args,timeout=60):
    adb=find_adb()
    if not adb: return None
    try:
        p=subprocess.run([adb,*args],capture_output=True,timeout=timeout,check=False,stdin=subprocess.DEVNULL)
        return p.stdout if p.returncode==0 else None
    except Exception: return None

def _root_mode(serial):
    for mode,cmd in (('direct',['shell','id']),('su',['shell','su','-c','id']),('su0',['shell','su','0','id'])):
        r,e=run_adb(['-s',serial,*cmd],timeout=20)
        if r and 'uid=0' in (r['stdout']+r['stderr']): return mode
    return None
def _cat_remote(serial,mode,remote):
    cmd={'direct':f'cat {remote}','su':f"su -c 'cat {remote}'",'su0':f'su 0 cat {remote}'}[mode]
    return adb_bytes(['-s',serial,'exec-out',cmd],timeout=120)

def pull_browser_dbs(serial):
    """Stored history: read browser history databases from the phone (needs root / adb root). Returns (items,error)."""
    mode=_root_mode(serial)
    if not mode: return None,'phone is not rooted (no su / adb root), so app-private browser databases cannot be read over ADB.'
    outdir=DATA/'browser_acquired'; outdir.mkdir(exist_ok=True)
    items=[]; found=[]
    for name,pkg,rels in BROWSER_DBS:
        for rel in rels:
            remote=f'/data/data/{pkg}/{rel}'
            blob=_cat_remote(serial,mode,remote)
            if not blob or not blob.startswith(b'SQLite format 3'): continue
            local=outdir/f'{pkg}_{Path(rel).name}'; local.write_bytes(blob)
            for side in ('-wal','-journal'):
                sb=_cat_remote(serial,mode,remote+side)
                if sb: Path(str(local)+side).write_bytes(sb)
            got,perr=parse_browser_db(local,browser=name,source='ADB')
            if got is not None: items+=got; found.append(name)
            break
    if not found: return None,'phone is rooted but no supported browser history database was found.'
    return items,None

def devtools_tabs(serial):
    """Live history without root: ask the running browser (Chrome-family DevTools socket, same mechanism as chrome://inspect) for its open tabs."""
    import urllib.request
    r,e=run_adb(['-s',serial,'shell','cat','/proc/net/unix'],timeout=20)
    if e or not r: return None,e or 'could not list sockets.'
    socks=sorted(set(re.findall(r'@([\w.\-]*devtools_remote[\w.\-]*)',r['stdout'])))
    if not socks: return None,'no browser DevTools socket found. Open Chrome on the phone, keep it running with the pages open, then re-acquire.'
    now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'); items=[]
    for s in socks:
        f,fe=run_adb(['-s',serial,'forward','tcp:0','localabstract:'+s],timeout=15)
        if fe or not f or f['returncode']!=0: continue
        port=(f['stdout'].strip().splitlines() or [''])[-1].strip()
        if not port.isdigit(): continue
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=8) as resp: tabs=json.loads(resp.read().decode('utf-8','replace'))
        except Exception: tabs=[]
        run_adb(['-s',serial,'forward','--remove',f'tcp:{port}'],timeout=10)
        label='Chrome' if s=='chrome_devtools_remote' else ('WebView' if s.startswith('webview_devtools_remote') else s.replace('_devtools_remote',''))
        for t in tabs:
            url=t.get('url','')
            if t.get('type')!='page' or not url or url.startswith('devtools://'): continue
            items.append({'timestamp':now,'title':t.get('title',''),'url':url,'browser':label+' (open tab)','visits':'1','risk':'Low','source':'ADB'})
    if not items: return None,'DevTools socket found but it reported no open pages.'
    return items,None

# ---- application history: real foreground events from Android usage stats ----
UA_FG={'ACTIVITY_RESUMED','MOVE_TO_FOREGROUND'}; UA_BG={'ACTIVITY_PAUSED','ACTIVITY_STOPPED','MOVE_TO_BACKGROUND'}
def _ua_time(q,ms):
    if ms: return datetime.fromtimestamp(int(ms)/(1000 if len(ms)>=13 else 1))
    return datetime.strptime(q.split('.')[0],'%Y-%m-%d %H:%M:%S')
def parse_usage_events(out):
    pat=re.compile(r'time=(?:"([^"]+)"|(\d{10,13}))\s+type=(\w+)\s+package=(\S+)')
    evs=[]
    for line in out.splitlines():
        m=pat.search(line)
        if not m: continue
        try: dt=_ua_time(m.group(1),m.group(2))
        except Exception: continue
        evs.append((dt,m.group(3),m.group(4)))
    evs.sort(key=lambda x:x[0])
    rows=[]; start={}; pend={}
    def mk(pkg,dt,event,dur): return {'timestamp':dt.strftime('%Y-%m-%d %H:%M:%S'),'app_name':pkg.split('.')[-1].capitalize(),'package':pkg,'event':event,'duration':dur,'risk':'Low','source':'ADB'}
    def flush(pkg):
        s,e=pend.pop(pkg); rows.append(mk(pkg,s,'Foreground session',fmt_dur(int((e-s).total_seconds()))))
    for dt,typ,pkg in evs:
        if pkg in ('android','com.android.systemui'): continue
        if typ in UA_FG:
            if pkg in pend:
                if (dt-pend[pkg][1]).total_seconds()<=3: start[pkg]=pend.pop(pkg)[0]
                else: flush(pkg)
            if pkg not in start: start[pkg]=dt
        elif typ in UA_BG:
            if pkg in start: pend[pkg]=(start.pop(pkg),dt)
            elif pkg in pend: pend[pkg]=(pend[pkg][0],max(pend[pkg][1],dt))
    for pkg in list(pend): flush(pkg)
    for pkg,s in start.items(): rows.append(mk(pkg,s,'Opened (still in foreground)','—'))
    return rows
def parse_usage_packages(out):
    pat=re.compile(r'package=(\S+)\s.*?lastTimeUsed=(?:"([^"]+)"|(\d{10,13}))')
    best={}
    for line in out.splitlines():
        m=pat.search(line)
        if not m: continue
        try: dt=_ua_time(m.group(2),m.group(3))
        except Exception: continue
        if m.group(1) not in best or dt>best[m.group(1)]: best[m.group(1)]=dt
    return [{'timestamp':dt.strftime('%Y-%m-%d %H:%M:%S'),'app_name':p.split('.')[-1].capitalize(),'package':p,'event':'Last used','duration':'—','risk':'Low','source':'ADB'} for p,dt in best.items() if p not in ('android','com.android.systemui')]
def usage_events(serial):
    r,e=run_adb(['-s',serial,'shell','dumpsys','usagestats'],timeout=90)
    if e: return None,e
    rows=parse_usage_events(r['stdout']) or parse_usage_packages(r['stdout'])
    if not rows: return None,'"dumpsys usagestats" returned no usable data on this phone.'
    rows.sort(key=lambda x:x['timestamp'],reverse=True)
    return rows[:5000],None

@app.route('/api/import-browser-db',methods=['POST'])
def import_browser_db():
    f=request.files.get('file')
    if not f: return jsonify(error='Choose a browser history database (Chrome "History" or Firefox "places.sqlite")'),400
    browser=(request.form.get('browser') or 'Unknown').strip() or 'Unknown'
    p=DATA/Path(f.filename).name; f.save(p)
    items,err=parse_browser_db(p,browser=browser,source='DB import')
    if err: return jsonify(error=err),400
    c=load_case(); c['browser_history']+=items; save_case(c)
    return jsonify(status='imported',rows=len(items),sha256=sha256(p))

def acquire_module(kind,serial):
 now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'); items=[]; note=''
 if kind=='calls':
  rows,err=content_query(serial,'content://call_log/calls','number:date:duration:type:name')
  if err: return False,err,0
  for r in rows:
   nm=r.get('name','')
   items.append({'timestamp':fmt_ts(r.get('date')),'contact':r.get('number','')+(f' ({nm})' if nm else ''),'channel':'CALL','direction':CALL_TYPES.get(r.get('type'),'Unknown'),'duration':fmt_dur(r.get('duration')),'risk':'Low','source':'ADB'})
 elif kind=='messages':
  rows,err=content_query(serial,'content://sms','address:date:type:body')
  if err: return False,err,0
  for r in rows:
   items.append({'timestamp':fmt_ts(r.get('date')),'contact':r.get('address',''),'channel':'SMS','direction':SMS_TYPES.get(r.get('type'),'Unknown'),'duration':'—','body':r.get('body',''),'risk':'Low','source':'ADB'})
 elif kind=='browser':
  notes=[]; rows,err=None,'No browser provider tried'
  for uri in ('content://com.android.chrome.browser/history','content://browser/bookmarks'):
   rows,err=content_query(serial,uri,'title:url:date:visits')
   if rows is not None: break
  for r in (rows or []):
   items.append({'timestamp':fmt_ts(r.get('date')),'title':r.get('title',''),'url':r.get('url',''),'browser':'Android Browser','visits':r.get('visits','1') or '1','risk':'Low','source':'ADB'})
  if rows: notes.append(f'{len(rows)} from ADB provider')
  titems,terr=devtools_tabs(serial)          # live, no root
  if titems is not None: items+=titems; notes.append(f'{len(titems)} live open tabs')
  ritems,rerr=pull_browser_dbs(serial)       # stored, needs root
  if ritems is not None: items+=ritems; notes.append(f'{len(ritems)} from stored history databases')
  if not items and rows is None:
   return False,'Legacy provider: '+(err or 'n/a')+' | Live tabs: '+(terr or 'n/a')+' | Stored databases: '+(rerr or 'n/a')+' | For stored history on a non-rooted phone, copy the browser History / places.sqlite file from an authorized backup or image and use "Import browser database", or import a CSV.',0
  note=' ('+'; '.join(notes)+')' if notes else ''
 else:
  r,e=run_adb(['-s',serial,'shell','pm','list','packages','-3'],timeout=30)
  if e: return False,e,0
  if r['returncode']!=0: return False,r['stderr'].strip() or 'pm list packages failed',0
  ev,uerr=usage_events(serial)
  used={x['package'] for x in ev} if ev else set()
  if ev: items+=ev; note=f' ({len(ev)} real app-usage events from Android usage stats)'
  else: note=' (usage stats unavailable: '+(uerr or 'n/a')+' - showing installed apps only)'
  for line in r['stdout'].splitlines():
   if line.startswith('package:'):
    pkg=line[8:].strip()
    if pkg in used: continue
    items.append({'timestamp':'' if ev else now,'app_name':pkg.split('.')[-1].capitalize(),'package':pkg,'event':'Installed user app','duration':'—','risk':'Low','source':'ADB'})
 c=load_case(); g=GROUPS[kind]
 c[g]=[x for x in c[g] if x.get('source')!='ADB']+items
 log=c.setdefault('acquisition',[])
 log.append({'time':now,'module':kind,'device':serial,'records':len(items),'sha256':hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()})
 c['acquisition']=log[-100:]; save_case(c)
 return True,f'Acquired {len(items)} record(s) from device {serial} at {now}.'+note,len(items)

@app.route('/api/acquire/<kind>',methods=['POST'])
def api_acquire(kind):
 if kind not in GROUPS: return jsonify(error='Unsupported module'),400
 serial,err=ready_serial()
 if err: return jsonify(acquired=False,message=err)
 ok,msg,n=acquire_module(kind,serial)
 return jsonify(acquired=ok,message=msg if ok else 'Acquisition not possible: '+msg+' Showing imported data only.',rows=n,serial=serial)

# ---- targeted extraction ----
def norm_digits(s): return re.sub(r'\D','',s or '')
def row_matches(x,q):
 q=q.strip()
 if re.fullmatch(r'[\d\s+\-()]+',q) and len(norm_digits(q))>=7:
  return norm_digits(x.get('contact',''))[-10:]==norm_digits(q)[-10:] or q.lower() in json.dumps(x).lower()
 return q.lower() in json.dumps(x,ensure_ascii=False).lower()
def target_stats(module,rows):
 ts=sorted(x.get('timestamp','') for x in rows if x.get('timestamp'))
 s={'count':len(rows),'first_seen':ts[0] if ts else '—','last_seen':ts[-1] if ts else '—'}
 if module in ('calls','messages'): s['by_direction']=dict(Counter(x.get('direction') or 'Unknown' for x in rows))
 if module=='calls': s['total_duration']=fmt_dur(sum(dur_secs(x.get('duration')) for x in rows))
 if module=='browser': s['top_domains']=dict(Counter(urlparse(x.get('url','')).netloc or 'n/a' for x in rows).most_common(5))
 if module=='apps': s['distinct_apps']=len({x.get('package') for x in rows})
 return s
def target_rows(c,module,q):
 rows=[x for x in c[GROUPS[module]] if row_matches(x,q)]
 return sorted(rows,key=lambda x:x.get('timestamp',''),reverse=True)

@app.route('/api/target')
def api_target():
 module=request.args.get('module',''); q=request.args.get('q','').strip()
 if module not in GROUPS: return jsonify(error='Unsupported module'),400
 if not q: return jsonify(error='Enter a target number or keyword'),400
 rows=target_rows(load_case(),module,q)
 return jsonify(module=module,query=q,stats=target_stats(module,rows),rows=rows)

# ---- AFT report ----
REPORT=DATA/'AFT_Report.html'
CFG={'calls':(['timestamp','contact','direction','duration','source','risk'],['Timestamp','Contact','Direction','Duration','Source','Risk'],'Call Logs'),
 'messages':(['timestamp','contact','direction','body','source','risk'],['Timestamp','Contact','Direction','Message','Source','Risk'],'Messages / SMS'),
 'browser':(['timestamp','title','url','browser','visits','source','risk'],['Timestamp','Title','URL','Browser','Visits','Source','Risk'],'Browser History'),
 'apps':(['timestamp','app_name','package','event','duration','source','risk'],['Timestamp','Application','Package','Event','Duration','Source','Risk'],'Application History')}
def build_report(examiner,target,attempts,serial):
 e=_html.escape; c=load_case(); now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
 def tbl(rows,m):
  keys,labels,_=CFG[m]
  if not rows: return '<p><i>No records.</i></p>'
  rows=sorted(rows,key=lambda x:x.get('timestamp',''),reverse=True)
  return '<table><thead><tr>'+''.join(f'<th>{l}</th>' for l in labels)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+e(str(x.get(k) or ('Imported/Sample' if k=='source' else '')))+'</td>' for k in keys)+'</tr>' for x in rows)+'</tbody></table>'
 dev=''
 if serial:
  props={'Manufacturer':'ro.product.manufacturer','Model':'ro.product.model','Android version':'ro.build.version.release','SDK level':'ro.build.version.sdk'}
  dev='<table>'+''.join(f'<tr><th>{k}</th><td>{e(((run_adb(["-s",serial,"shell","getprop",v])[0] or {}).get("stdout","") or "Unavailable").strip())}</td></tr>' for k,v in props.items())+f'<tr><th>Serial</th><td>{e(serial)}</td></tr></table>'
 else: dev='<p><i>No device connected at report time. Report uses previously acquired/imported data.</i></p>'
 att=''.join(f'<tr><td>{e(CFG[m][2])}</td><td>{"Acquired" if ok else "Not acquired"}</td><td>{e(msg)}</td></tr>' for m,(ok,msg) in attempts.items()) or '<tr><td colspan=3>No live acquisition attempted.</td></tr>'
 log=''.join(f'<tr><td>{e(a["time"])}</td><td>{e(a["module"])}</td><td>{e(a["device"])}</td><td>{a["records"]}</td><td style="font-size:10px">{e(a["sha256"])}</td></tr>' for a in c.get('acquisition',[])[-20:]) or '<tr><td colspan=5>No device acquisitions recorded.</td></tr>'
 summ=''.join(f'<tr><td>{CFG[m][2]}</td><td>{len(c[g])}</td><td>{sum(1 for x in c[g] if x.get("risk")=="High")}</td></tr>' for m,g in GROUPS.items())
 tgt=''
 if target:
  tgt=f'<h2>4. Target Analysis — {e(target)}</h2>'
  for m in GROUPS:
   rows=target_rows(c,m,target); s=target_stats(m,rows)
   extra=' · '.join(f'{k}: {e(str(v))}' for k,v in s.items() if k not in('count','first_seen','last_seen'))
   tgt+=f'<h3>{CFG[m][2]}</h3><p>Matches: <b>{s["count"]}</b> · First seen: {e(s["first_seen"])} · Last seen: {e(s["last_seen"])}'+(' · '+extra if extra else '')+'</p>'+tbl(rows,m)
 n=5 if target else 4
 body=''.join(f'<h2>{n+i}. {CFG[m][2]} (all records)</h2>'+tbl(c[g],m) for i,(m,g) in enumerate(GROUPS.items()))
 chash=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()
 css='body{font:13px Segoe UI,Arial;margin:30px;color:#111}h1{color:#0b5a78}h2{border-bottom:2px solid #0b5a78;padding-bottom:3px;margin-top:28px}table{border-collapse:collapse;width:100%;margin:8px 0}th,td{border:1px solid #bbb;padding:5px 7px;text-align:left;vertical-align:top;font-size:12px;overflow-wrap:anywhere}th{background:#e8f1f5}@media print{h2{page-break-after:avoid}}'
 return f'''<!doctype html><html><head><meta charset="utf-8"><title>AFT Report - {e(c["case_id"])}</title><style>{css}</style></head><body>
<h1>AFT Report</h1><table><tr><th>Case ID</th><td>{e(c["case_id"])}</td><th>Generated</th><td>{now}</td></tr><tr><th>Examiner</th><td>{e(examiner or "Not specified")}</td><th>Target</th><td>{e(target or "None")}</td></tr></table>
<h2>1. Device Information</h2>{dev}<h2>2. Acquisition Results (this run)</h2><table><tr><th>Module</th><th>Status</th><th>Details</th></tr>{att}</table>
<h2>3. Evidence Summary</h2><table><tr><th>Module</th><th>Records</th><th>High-risk</th></tr>{summ}</table>
{tgt}{body}
<h2>Acquisition Log &amp; Integrity</h2><table><tr><th>Time</th><th>Module</th><th>Device</th><th>Records</th><th>SHA-256 of acquired set</th></tr>{log}</table>
<p><b>Case data SHA-256 at report time:</b> {chash}</p>
<p style="font-size:11px;color:#555">Data marked ADB was read from the device using read-only ADB queries. Other rows were imported from CSV or are sample data. Use only on devices you own or are authorized to examine.</p></body></html>'''

@app.route('/api/report',methods=['POST'])
def api_report():
 b=request.get_json(silent=True) or {}
 serial,_=ready_serial(); attempts={}
 if serial:
  for m in GROUPS:
   ok,msg,_n=acquire_module(m,serial); attempts[m]=(ok,msg)
 REPORT.write_text(build_report(b.get('examiner','').strip(),b.get('target','').strip(),attempts,serial),encoding='utf-8')
 return jsonify(status='generated',name='AFT_Report.html',url='/report/AFT',download='/report/AFT?download=1',sha256=sha256(REPORT),live_acquisition=bool(serial))
@app.route('/report/AFT')
def view_report():
 if not REPORT.exists(): return 'Generate the AFT report first.',404
 return send_file(REPORT,mimetype='text/html',as_attachment=bool(request.args.get('download')),download_name='AFT_Report.html')

@app.route('/api/export')
def export_case(): return jsonify(load_case())
if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=False)
