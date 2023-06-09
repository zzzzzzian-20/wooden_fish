from sqlalchemy import Table
from sqlalchemy import MetaData
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import TIMESTAMP
from sqlalchemy import String
from sqlalchemy import text
from sqlalchemy import Boolean


table = Table(
    'wish',
    MetaData(),
    Column('id', Integer, primary_key=True, index=True),
    Column('create_time', 
           TIMESTAMP(),
           server_default=text('CURRENT_TIMESTAMP'),
           nullable=False),
    Column('update_time', 
           TIMESTAMP(),
           server_default=text('CURRENT_TIMESTAMP'),
           server_onupdate=text('CURRENT_TIMESTAMP'),
           nullable=False),
    Column('last_time', 
           TIMESTAMP(), 
           server_default=text('CURRENT_TIMESTAMP'),
           nullable=False),
    Column('openid', String, nullable=True),
    Column('count', Integer, nullable=True),
    Column('knock', Integer, nullable=True),
    Column('fulfill', Boolean, nullable=True),
    Column('wish', String, nullable=True),
    Column('helper_total', Integer, nullable=True),
    Column('share_count_total', Integer, nullable=True),
    Column('share_knock_total', Integer, nullable=True),
    Column('helper', Integer, index=True, nullable=True),
    Column('share_count', Integer, nullable=True),
    Column('share_knock', Integer, nullable=True)
)
