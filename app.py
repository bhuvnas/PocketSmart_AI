"""PocketSmart AI: FastAPI web app with SQLite users and recommendation history."""
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from starlette.middleware.sessions import SessionMiddleware
import hashlib
import hmac

def generate_password_hash(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"

def check_password_hash(encoded, password):
    try:
        method, iterations, salt, expected = encoded.split("$")
        if method != "pbkdf2_sha256": return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False
from services.planner import make_plan
import io

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DATA = Path(os.getenv('POCKETSMART_DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'pocketsmart.sqlite3'
app = FastAPI(title='PocketSmart AI', version='1.0.0')
app.add_middleware(SessionMiddleware, secret_key=os.getenv('SECRET_KEY') or 'development-only-secret-change-me', same_site='lax', https_only=False)
app.mount('/static', StaticFiles(directory=str(ROOT/'static')), name='static')
templates = Jinja2Templates(directory=str(ROOT/'templates'))

@contextmanager
def db():
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, kind TEXT NOT NULL, inputs TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id))')
init_db()


def user(request):
    uid = request.session.get('uid')
    if not isinstance(uid, int):
        return None
    with db() as c:
        row = c.execute('SELECT id,username,email FROM users WHERE id=?', (uid,)).fetchone()
    return dict(row) if row else None


def page(request, name, **ctx):
    return templates.TemplateResponse(request=request, name=name, context={"user": user(request), **ctx})


def require_user(request):
    u = user(request)
    if not u:
        raise HTTPException(401, 'Please log in to generate or view recommendations.')
    return u

@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'PocketSmart AI'}

@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return page(request, 'index.html')

@app.get('/register', response_class=HTMLResponse)
def register_form(request: Request):
    return page(request, 'register.html')

@app.post('/register')
def register(request: Request, username: str=Form(...), email: str=Form(...), password: str=Form(...)):
    username, email = username.strip(), email.strip().lower()
    if len(username)<3 or len(username)>50 or '@' not in email or len(email)>254 or len(password)<8:
        return page(request,'register.html', error='Use a username of 3–50 characters, valid email, and password of at least 8 characters.')
    try:
        with db() as c:
            cursor = c.execute('INSERT INTO users(username,email,password_hash) VALUES(?,?,?)', (username,email,generate_password_hash(password)))
            uid=cursor.lastrowid
    except sqlite3.IntegrityError:
        return page(request, 'register.html',error='Username or email already exists.')
    request.session.clear()
    request.session['uid'] = uid
    return RedirectResponse('/dashboard', status_code=303)

@app.get('/login',response_class=HTMLResponse)
def login_form(request: Request):
    return page(request,'login.html')

@app.post('/login')
def login(request: Request, username: str=Form(...), password: str=Form(...)):
    with db() as c:
        row = c.execute('SELECT id,password_hash FROM users WHERE username=? OR email=?', (username.strip(),username.strip().lower())).fetchone()
    if not row or not check_password_hash(row['password_hash'], password):
        return page(request,'login.html',error='Incorrect username/email or password.')
    request.session.clear()
    request.session['uid']=row['id']
    return RedirectResponse('/dashboard',status_code=303)

@app.post('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login',status_code=303)

@app.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request):
    if not user(request):return RedirectResponse('/login',status_code=303)
    with db() as c:
        rows=c.execute('SELECT id,kind,created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT 5',(user(request)['id'],)).fetchall()
    return page(request,'dashboard.html',recent=[dict(r) for r in rows])

@app.get('/{kind}-planner', response_class=HTMLResponse)
def planner_page(request: Request, kind: str):
    if kind not in ('home','party','jewelry'):raise HTTPException(404)
    if not user(request):return RedirectResponse('/login',status_code=303)
    return page(request,'planner.html',kind=kind)

@app.post('/generate-{kind}')
async def generate(request: Request, kind: str):
    if kind not in ('home','party','jewelry'):raise HTTPException(404)
    u=require_user(request)
    form=await request.form()
    try:
        budget=float(form.get('budget',0))
        if not 100 <= budget <= 100000000:
            raise ValueError('Budget must be between ₹100 and ₹10 crore.')
        data={'budget':budget}
        if kind=='home':
            data.update({'room':str(form.get('room','living room'))[:80], 'style':str(form.get('style','modern'))[:80], 'requirements':str(form.get('requirements',''))[:500]})
            for k in ['lights','fans','furniture','dining_tables']:
                n=int(form.get(k,0))
                if not 0 <= n <= 100:raise ValueError('Item quantities must be from 0 to 100.')
                data[k]=n
        elif kind=='party':
            guests=int(form.get('guests',0))
            if not 1 <= guests <= 10000:raise ValueError('Guests must be between 1 and 10,000.')
            data.update({'guests':guests,'event_type':str(form.get('event_type','birthday'))[:80],
                         'venue':str(form.get('venue',''))[:100],'requirements':str(form.get('requirements',''))[:500]})
        else:
            data.update({'occasion':str(form.get('occasion','wedding'))[:80], 'style':str(form.get('style','traditional'))[:80],
                         'outfit_color':str(form.get('outfit_color',''))[:80], 'requirements':str(form.get('requirements',''))[:500]})
    except (ValueError,TypeError) as exc:
        raise HTTPException(422,str(exc)) from exc
    image_bytes=None
    mime=None
    if kind=='jewelry':
        upload=form.get('image')
        if upload is not None and hasattr(upload, 'read') and getattr(upload, 'filename', ''):
            mime=upload.content_type
            if mime not in ('image/png','image/jpeg','image/webp'):
                raise HTTPException(422,'Upload a PNG, JPG or WEBP image.')
            image_bytes=await upload.read(5*1024*1024+1)
            if len(image_bytes)>5*1024*1024:raise HTTPException(413,'Image limit is 5 MB.')
            try:
                im=Image.open(io.BytesIO(image_bytes))
                im.verify()
            except (UnidentifiedImageError,OSError):
                raise HTTPException(422,'Not a valid image.')
            data['outfit_image_uploaded']=True
    result=make_plan(kind,data,image_bytes,mime)
    with db() as c:
        cursor=c.execute('INSERT INTO history (user_id,kind,inputs,result) VALUES (?,?,?,?)',
                         (u['id'],kind,json.dumps(data),json.dumps(result)))
        hist_id=cursor.lastrowid
    if 'application/json' in request.headers.get('accept',''):
        return JSONResponse({'id':hist_id,**result})
    return RedirectResponse(f'/recommendations-details/{hist_id}',status_code=303)

@app.get('/history', response_class=HTMLResponse)
def history(request: Request):
    u=user(request)
    if not u:return RedirectResponse('/login',status_code=303)
    with db() as c:
        rows=c.execute('SELECT id,kind,inputs,result,created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT 100',(u['id'],)).fetchall()
    return page(request,'history.html',records=[dict(r) for r in rows])

@app.get('/recommendations-details/{item_id}', response_class=HTMLResponse)
def details(request: Request,item_id:int):
    u=user(request)
    if not u:return RedirectResponse('/login',status_code=303)
    with db() as c:
        row=c.execute('SELECT * FROM history WHERE id=? AND user_id=?',(item_id,u['id'])).fetchone()
    if not row:raise HTTPException(404,'Recommendation not found.')
    return page(request,'details.html',plan=json.loads(row['result']),kind=row['kind'],inputs=json.loads(row['inputs']),created_at=row['created_at'])

@app.get('/session-info')
def session_info(request: Request):
    u=user(request)
    return {'authenticated':bool(u),'user':u}

@app.get('/session-data')
def session_data(request: Request):
    u=require_user(request)
    with db() as c:
        count=c.execute('SELECT count(*) FROM history WHERE user_id=?',(u['id'],)).fetchone()[0]
    return {'user':u,'recommendation_count':count}

@app.get('/recommendations-details')
def recommendation_details_api(request: Request, id: Optional[int]=None):
    u=require_user(request)
    if id is None:raise HTTPException(422,'Supply ?id=<recommendation-id>')
    with db() as c:
        row=c.execute('SELECT kind,inputs,result,created_at FROM history WHERE id=? AND user_id=?',(id,u['id'])).fetchone()
    if not row:raise HTTPException(404)
    return {'kind':row['kind'],'inputs':json.loads(row['inputs']),'result':json.loads(row['result']),'created_at':row['created_at']}

@app.get('/startup')
def startup_status():
    return {'status':'ready','gemini_configured':bool(os.getenv('GEMINI_API_KEY'))}

if __name__=='__main__':
    import uvicorn
    uvicorn.run('app:app',host='127.0.0.1',port=8000,reload=False)
