from sqlalchemy import Table
from sqlalchemy import MetaData
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import TIMESTAMP
from sqlalchemy import String
from sqlalchemy import text


table = Table(
    'share_knock',
    MetaData(),
    Column('id', Integer, primary_key=True, index=True),
    Column('wish_id', Integer, index=True),
    Column('create_time',
           TIMESTAMP,
           server_default=text('CURRENT_TIMESTAMP'),
           index=True,
           nullable=False),
    Column('openid', String, nullable=False),
    Column('count', Integer, nullable=True),
    Column('knock', Integer, nullable=True)
)
