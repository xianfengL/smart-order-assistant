from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pwdlib import PasswordHash
from .config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='customer')


class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    product: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Conversation(Base):
    __tablename__ = 'conversations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    title: Mapped[str] = mapped_column(String(100), default='新对话')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id'), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


engine = None
SessionLocal = None
password_hash = PasswordHash.recommended()


def initialize():
    global engine, SessionLocal
    settings.prepare()
    kwargs = {'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}
    engine = create_engine(settings.database_url, connect_args=kwargs, pool_pre_ping=True)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if not session.query(User).first():
            session.add_all([
                User(id=1, username='admin', role='admin', password_hash=password_hash.hash(settings.admin_password)),
                User(id=2, username='demo', role='customer', password_hash=password_hash.hash(settings.customer_password)),
                User(id=3, username='alice', role='customer', password_hash=password_hash.hash(settings.customer_password)),
            ])
            session.commit()
        if settings.demo_mode and not session.query(Order).first():
            products = [('无线耳机', '数码', 299), ('机械键盘', '数码', 459), ('运动鞋', '服饰', 369),
                        ('保温杯', '家居', 129), ('护肤套装', '美妆', 599), ('桌面灯', '家居', 189)]
            for i in range(1, 73):
                name, category, price = products[(i - 1) % len(products)]
                session.add(Order(id=i, order_no=f'SO202501{i:04d}', customer_id=3 if i % 3 == 0 else 2,
                                  product=name, category=category, amount=price * (1 + i % 2),
                                  status=['已完成', '已发货', '待支付', '退款中'][i % 4],
                                  created_at=datetime(2025, 1, 1) + timedelta(days=i % 59)))
            session.commit()
