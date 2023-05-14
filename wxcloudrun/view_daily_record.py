from flask import request
from marshmallow import Schema, fields
from marshmallow.validate import Length
from marshmallow.validate import Range 
from marshmallow.validate import OneOf 
from sqlalchemy.engine import Engine
from sqlalchemy import select
from sqlalchemy import desc
from sqlalchemy import asc
from sqlalchemy import func
from webargs.flaskparser import use_kwargs
from sqlalchemy import and_

from run import app
from wxcloudrun import db
from wxcloudrun.tables import wish as wish_table
from wxcloudrun.response import make_succ_response


class NewWish(Schema):
  wish = fields.String(required=True,
                       validate=[Length(min=1, max=128)])


@app.route('/api/wooden_fish/wish', methods=['POST'])
@use_kwargs(NewWish)
def new_wish(wish: str):
  engine: Engine = db.engine
  table = wish_table.table
  openid = request.headers.get('X-WX-OPENID')

  with engine.begin() as conn:
    conn.execute(
        table.insert().values(
            openid=openid,
            wish=wish,
        )
    )
    res = conn.execute(
        select(table.c.id)
        .order_by(desc(table.c.create_time))
        .limit(1)
    ).fetchall()
  return make_succ_response({'id': res[0][0]})


class WishList(Schema):
  mode = fields.String(load_default='list',
                       validate=[OneOf(('list', 'last'))])
  last_id = fields.Integer(load_default=0, 
                           validate=[Range(min=0)])
  page_num = fields.Integer(load_default=5, 
                            validate=[Range(min=1, max=20)])
  fulfill = fields.Boolean(load_default=False)


WISH_FIELDS = ('id', 'create_time', 'update_time', 'last_time', 
               'count', 'fulfill', 'wish')


@app.route('/api/wooden_fish/wish_list', 
           methods=['POST'])
@use_kwargs(WishList)
def wish_list(mode: str, last_id: int, page_num: int, fulfill: bool):
  engine: Engine = db.engine
  table = wish_table.table
  openid = request.headers.get('X-WX-OPENID')

  sql = select(table.c.id,
               func.unix_timestamp(table.c.create_time).label('create_time'),
               func.unix_timestamp(table.c.update_time).label('update_time'),
               func.unix_timestamp(table.c.last_time).label('last_time'),
               table.c.count,
               table.c.fulfill,
               table.c.wish)
  if mode == 'list':
    sql = (
        sql
        .where(and_(table.c.fulfill.is_(fulfill),
                    table.c.openid == openid,
                    table.c.id > last_id))
        .order_by(asc(table.c.id))
        .limit(page_num)
    )
  elif mode == 'last':
    sql = (
        sql
        .where(and_(table.c.fulfill.is_(fulfill),
                    table.c.openid == openid))
        .order_by(desc(table.c.last_time))
        .limit(page_num)
    )
  res = engine.execute(sql).fetchall()
  result = {i: list() for i in WISH_FIELDS}
  for i in res:
    for idx, k in enumerate(WISH_FIELDS):
      result[k].append(i[idx])
  return make_succ_response(result)


class WishUpdate(Schema):
  wish_id = fields.Integer(required=True, validate=[Range(min=0)])
  fulfill = fields.Boolean(load_default=None)
  count = fields.Integer(load_default=1, 
                         validate=[Range(min=0, max=10)])
  wish = fields.String(load_default=None,
                       validate=[Length(min=1, max=128)])


@app.route('/api/wooden_fish/wish_update',
           methods=['POST'])
@use_kwargs(WishUpdate)
def wish_update(wish_id: int, fulfill: bool, count: int, wish: str):
  engine: Engine = db.engine
  table = wish_table.table
  openid = request.headers.get('X-WX-OPENID')

  values = dict(
    count=table.c.count + count
  )
  if fulfill is not None:
    values['fulfill'] = fulfill
  if wish is not None:
    values['wish'] = wish
  
  engine.execute(
      table.update().values(**values).where(table.c.id == wish_id, 
                                            table.c.openid == openid)
  )
  return make_succ_response({'result': True})
