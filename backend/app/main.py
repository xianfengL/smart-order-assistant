import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from .config import settings
from . import db
from .auth import current_user, issue_token
from .rag import PolicyStore
from .graph import make_graph

logger = logging.getLogger(__name__)
login_attempts = defaultdict(deque)
active_conversations = set()


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(db.initialize)
    store = await asyncio.to_thread(PolicyStore)
    await asyncio.to_thread(store.index)
    async with AsyncSqliteSaver.from_conn_string(str(settings.data_dir / 'checkpoints.db')) as saver:
        await saver.setup()
        app.state.graph = make_graph(store, saver)
        yield
    db.engine.dispose()


app = FastAPI(title='智能订单 AI 客服助手', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(','),
                   allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def owned_conversation(session, cid, user):
    conversation = session.get(db.Conversation, cid)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(404, '会话不存在')
    return conversation


@app.get('/api/health')
def health():
    return {'status': 'ok', 'mode': 'demo' if settings.demo_mode else 'live'}


@app.post('/api/auth/login')
def login(body: LoginBody, request: Request):
    now = time.monotonic()
    ip = request.client.host if request.client else 'unknown'
    # Prune old keys as well as timestamps to keep the limiter bounded.
    for key in list(login_attempts):
        while login_attempts[key] and now - login_attempts[key][0] > 60:
            login_attempts[key].popleft()
        if not login_attempts[key]:
            del login_attempts[key]
    attempts = login_attempts[ip]
    if len(attempts) >= 10:
        raise HTTPException(429, '尝试过于频繁，请一分钟后重试')
    attempts.append(now)
    with db.SessionLocal() as session:
        user = session.scalar(select(db.User).where(db.User.username == body.username))
        if not user or not db.password_hash.verify(body.password, user.password_hash):
            raise HTTPException(401, '用户名或密码错误')
        return {'access_token': issue_token(user), 'token_type': 'bearer',
                'user': {'username': user.username, 'role': user.role}}


@app.get('/api/auth/me')
def me(user=Depends(current_user)):
    return {'username': user.username, 'role': user.role}


@app.get('/api/conversations')
def conversations(user=Depends(current_user)):
    with db.SessionLocal() as session:
        rows = session.scalars(select(db.Conversation).where(db.Conversation.user_id == user.id)
                               .order_by(db.Conversation.created_at.desc()).limit(200)).all()
        return [{'id': row.id, 'title': row.title, 'created_at': row.created_at.isoformat()} for row in rows]


@app.post('/api/conversations', status_code=201)
def new_conversation(user=Depends(current_user)):
    with db.SessionLocal() as session:
        conversation = db.Conversation(id=str(uuid4()), user_id=user.id)
        session.add(conversation)
        session.commit()
        return {'id': conversation.id, 'title': conversation.title}


@app.get('/api/conversations/{cid}/messages')
def messages(cid: str, user=Depends(current_user)):
    with db.SessionLocal() as session:
        owned_conversation(session, cid, user)
        rows = session.scalars(select(db.Message).where(db.Message.conversation_id == cid).order_by(db.Message.id)).all()
        return [{'role': row.role, 'content': row.content, **row.payload} for row in rows]


def sse(event, data):
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n'


@app.post('/api/conversations/{cid}/chat')
async def chat(cid: str, body: ChatBody, user=Depends(current_user)):
    question = body.message.strip()
    if not question:
        raise HTTPException(422, '请输入消息')
    with db.SessionLocal() as session:
        conversation = owned_conversation(session, cid, user)
        if cid in active_conversations:
            raise HTTPException(409, '该会话正在生成回答')
        if len(active_conversations) >= 20:
            raise HTTPException(429, '服务繁忙，请稍后再试')
        active_conversations.add(cid)
        try:
            recent = session.scalars(select(db.Message).where(db.Message.conversation_id == cid)
                                     .order_by(db.Message.id.desc()).limit(10)).all()
            history = '\n'.join(f'{row.role}: {row.content[:1200]}' for row in reversed(recent))
            if conversation.title == '新对话':
                conversation.title = question[:32]
            session.add(db.Message(conversation_id=cid, role='user', content=question))
            session.commit()
        except Exception:
            active_conversations.discard(cid)
            raise

    async def events():
        state = {'question': question, 'history': history, 'user_id': user.id, 'user_role': user.role,
                 'rows': [], 'sources': [], 'chart': {}, 'sql': '', 'answer': '', 'intent': 'general', 'kind': 'bar'}
        try:
            yield sse('status', {'node': 'start', 'text': '正在理解你的问题'})
            async with asyncio.timeout(180):
                async for mode, chunk in app.state.graph.astream(state, config={'configurable': {'thread_id': f'{user.id}:{cid}'}}, stream_mode=['updates', 'custom']):
                    if mode == 'custom':
                        yield sse(chunk['event'], {'text': chunk['text']})
                    else:
                        for node, changes in chunk.items():
                            state.update(changes)
                            yield sse('status', {'node': node, 'intent': state['intent']})
                            if node == 'order':
                                yield sse('data', {'rows': state['rows'], 'sql': state['sql']})
                            elif node == 'policy':
                                yield sse('sources', {'sources': state['sources']})
                            elif node == 'chart':
                                yield sse('chart', {'chart': state['chart']})
            payload = {key: state[key] for key in ['rows', 'sql', 'sources', 'chart', 'intent']}
            with db.SessionLocal() as session:
                session.add(db.Message(conversation_id=cid, role='assistant', content=state['answer'], payload=payload))
                session.commit()
            yield sse('done', {'title': question[:32]})
        except Exception:
            logger.exception('Chat failed for conversation %s', cid)
            yield sse('error', {'text': '本次请求未完成，请重试或换一种表达。可检查服务日志及模型配置。'})
        finally:
            active_conversations.discard(cid)

    return StreamingResponse(events(), media_type='text/event-stream', headers={
        'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
