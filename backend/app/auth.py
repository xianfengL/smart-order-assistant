from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings
from . import db

bearer = HTTPBearer()


def issue_token(user):
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_minutes)},
                      settings.jwt_secret, algorithm='HS256')


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=['HS256'], options={'require': ['exp', 'sub']})
        uid = int(payload['sub'])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, '登录已失效，请重新登录')
    with db.SessionLocal() as session:
        user = session.get(db.User, uid)
        if not user:
            raise HTTPException(401, '用户不存在')
        return user
