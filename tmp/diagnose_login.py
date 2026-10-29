import asyncio, getpass, json
from app.main import app
from app.database import engine
from sqlalchemy import text
password=getpass.getpass('Password: ')
async def call(path, method='GET', body=None, cookie=None, origin='http://localhost:5173'):
 messages=[]; sent=False; payload=json.dumps(body).encode() if body is not None else b''
 async def receive():
  nonlocal sent
  if not sent: sent=True; return {'type':'http.request','body':payload,'more_body':False}
  return {'type':'http.disconnect'}
 async def send(message): messages.append(message)
 headers=[(b'origin',origin.encode())]
 if body is not None: headers.append((b'content-type',b'application/json'))
 if cookie: headers.append((b'cookie',cookie.encode()))
 await app({'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':method,'scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'','headers':headers,'client':('127.0.0.1',0),'server':('127.0.0.1',8010)},receive,send)
 start=next(m for m in messages if m['type']=='http.response.start'); data=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
 return start['status'], dict(start['headers']), data
with engine.connect() as c:
 row=c.execute(text("select id, role, is_active from users where id=230 and lower(trim(email))='23108179@szabist-isb.pk'" )).mappings().one(); print('database account:', dict(row))
status, headers, body=asyncio.run(call('/api/v1/auth/login','POST',{'email':'23108179@szabist-isb.pk','password':password,'requested_role':'ADMIN'}))
print('login status:',status)
set_cookie=next((v.decode() for k,v in headers.items() if k.lower()==b'set-cookie'),None)
if set_cookie is None: raise SystemExit('no session cookie')
cookie=set_cookie.split(';',1)[0]
for path in ('/api/v1/auth/me','/api/v1/admin/me'):
 st,h,b=asyncio.run(call(path,cookie=cookie)); print(path,'status:',st,'body:',b.decode()[:300])
