from sqlalchemy import Table
from sqlalchemy import MetaData
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import TIMESTAMP
from sqlalchemy import String
from sqlalchemy import text
from sqlalchemy import Boolean


table = Table(
    'wish_share',
    MetaData(),
    Column('id', Integer, primary_key=True, index=True),
    Column('share_id', String, unique=True, index=True),
    Column('wish_id',
           Integer,
           index=True,
           nullable=False),
    Column('create_time',
           TIMESTAMP(),
           server_default=text('CURRENT_TIMESTAMP'),
           nullable=False),
    Column('share_content', Boolean, nullable=False),
    Column('count', Integer, nullable=True),
    Column('knock', Integer, index=True, nullable=True),
    Column('wish', String, nullable=True)
)
