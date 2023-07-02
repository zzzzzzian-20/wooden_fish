from flask import request
from uuid import uuid4
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
from sqlalchemy import or_
from sqlalchemy import desc

from run import app
from wxcloudrun import db
from wxcloudrun.tables import wish as wish_table
from wxcloudrun.tables import wish_share as wish_share_table
from wxcloudrun.response import make_succ_response
from wxcloudrun.response import make_err_response


class NewWish(Schema):
  wish = fields.String(required=True,
                       validate=[Length(min=1, max=128)])


@app.route('/api/wooden_fish/wish', methods=['POST'])
@use_kwargs(NewWish)
def new_wish(wish: str):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})
  engine: Engine = db.engine
  table = wish_table.table

  with engine.begin() as conn:
    conn.execute(
        table.insert().values(
            openid=openid,
            wish=wish,
        )
    )
    res = conn.execute(
        select(table.c.id)
        .where(table.c.openid == openid)
        .order_by(desc(table.c.create_time))
        .limit(1)
    ).fetchall()
  return make_succ_response({'id': res[0][0]})


class WishList(Schema):
  mode = fields.String(load_default='list',
                       validate=[OneOf(('list', 'last'))])
  last_id = fields.Integer(load_default=0, 
                           validate=[Range(min=0)])
  page_num = fields.Integer(load_default=10, 
                            validate=[Range(min=1, max=100)])
  fulfill = fields.Boolean(load_default=False)


WISH_FIELDS = ('id', 'create_time', 'update_time', 'last_time', 
               'count', 'knock', 'fulfill', 'wish')


@app.route('/api/wooden_fish/wish_list', 
           methods=['POST'])
@use_kwargs(WishList)
def wish_list(mode: str, last_id: int, page_num: int, fulfill: bool):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})
  engine: Engine = db.engine
  table = wish_table.table

  sql = select(table.c.id,
               func.unix_timestamp(table.c.create_time).label('create_time'),
               func.unix_timestamp(table.c.update_time).label('update_time'),
               func.unix_timestamp(table.c.last_time).label('last_time'),
               table.c.count,
               table.c.knock,
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
                         validate=[Range(min=0, max=100)])
  knock = fields.Integer(load_default=None,
                         validate=[Range(min=0, max=10000)])
  wish = fields.String(load_default=None,
                       validate=[Length(min=1, max=128)])
  clear_record = fields.Boolean(load_default=False)


@app.route('/api/wooden_fish/wish_update',
           methods=['POST'])
@use_kwargs(WishUpdate)
def wish_update(wish_id: int, fulfill: bool, count: int, wish: str, knock: int,
                clear_record: bool):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})
  engine: Engine = db.engine
  table = wish_table.table

  values = dict()
  if clear_record:
    values['count'] = 0
    values['knock'] = 0
  else:
    if count:
      values['count'] = table.c.count + count
    if knock:
      values['knock'] = table.c.knock + knock
  if fulfill is not None:
    values['fulfill'] = fulfill
  if wish is not None:
    values['wish'] = wish

  engine.execute(
      table.update().values(**values).where(table.c.id == wish_id,
                                            table.c.openid == openid)
  )
  return make_succ_response({'result': True})


class WishShare(Schema):
  wish_id = fields.Integer(required=True, validate=[Range(min=0)])
  share_content = fields.Bool(load_default=False)


@app.route('/api/wooden_fish/wish_share_create',
           methods=['POST'])
@use_kwargs(WishShare)
def wish_share_create(wish_id: int, share_content: bool):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})

  engine: Engine = db.engine
  origin_table = wish_table.table
  table = wish_share_table.table

  sql = select(origin_table.c.wish).where(and_(origin_table.c.wish_id == wish_id,
                                               origin_table.c.openid == openid))
  res = engine.execute(sql).fetchall()
  if not res:
    return make_err_response({'msg': 'wish not found'})
  share_id = str(uuid4())

  share_vals = {
      'share_id': share_id,
      'wish_id': wish_id,
      'share_content': share_content
  }
  if share_content:
    wish = res[0][0]
    share_vals['wish'] = wish

  engine.execute(
      table.insert().values(**share_vals)
  )
  return make_succ_response({'share_id': share_id})


class WishShareEnter(Schema):
  share_id = fields.String(required=True)


@app.route('/api/wooden_fish/wish_share_enter',
           methods=['POST'])
@use_kwargs(WishShareEnter)
def wish_share_enter(share_id: str):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})

  engine: Engine = db.engine
  table = wish_share_table.table

  sql = (select(table.c.wish,
                table.c.share_content)
         .where(table.c.share_id == share_id))

  res = engine.execute(sql).fetchall()
  if not res:
    return make_err_response({'msg': 'wish not found'})
  return make_succ_response({'wish': res[0][0],
                             'share_content': res[0][1]})


class WishUpdate(Schema):
  share_id = fields.String(required=True)
  count = fields.Integer(load_default=1,
                         validate=[Range(min=0, max=100)])
  knock = fields.Integer(load_default=None,
                         validate=[Range(min=0, max=10000)])


@app.route('/api/wooden_fish/wish_share_update',
           methods=['POST'])
@use_kwargs(WishShareEnter)
def wish_share_update(share_id: str, count: int, knock: int):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})

  engine: Engine = db.engine
  table = wish_share_table.table

  values = {}
  if count:
    values['count'] = table.c.count + count
  if knock:
    values['knock'] = table.c.knock + knock
  if values:
    engine.execute(
        table.update().values(**values).where(table.c.share_id == share_id)
    )
  return make_succ_response({'result': True})


class WishShareList(Schema):
  wish_id = fields.Integer(required=True)
  page_num = fields.Integer(load_default=10, 
                            validate=[Range(min=1, max=100)])


@app.route('/api/wooden_fish/wish_share_list',
           methods=['POST'])
@use_kwargs(WishShareList)
def wish_share_list(wish_id: str, page_num):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})

  engine: Engine = db.engine
  table = wish_share_table.table
  origin_table = wish_table.table
  
  j = table.join(origin_table, onclause=table.c.wish_id == origin_table.c.id)
  sql = (select(table.c.share_id, table.c.count, table.c.knock)
         .select_from(j)
         .where(and_(origin_table.c.wish_id == wish_id,
                     origin_table.c.openid == openid,
                     or_(table.c.count > 0,
                         table.c.knock > 0)))
         .order_by(desc(table.c.id))
         .limit(page_num))

  res = engine.execute(sql).fetchall()
  fields = ('share_id', 'count', 'knock')
  result = {i: list() for i in fields}
  for i in res:
    for idx, k in enumerate(fields):
      result[k].append(i[idx])

  return make_succ_response({'result': result})


class WishShareClear(Schema):
  wish_id = fields.Integer(required=True)


@app.route('/api/wooden_fish/wish_share_clear',
           methods=['POST'])
@use_kwargs(WishShareClear)
def wish_share_clear(wish_id: str):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})

  engine: Engine = db.engine
  table = wish_share_table.table

  engine.execute(
      table.update().values(count=0, knock=0).where(table.c.wish_id == wish_id)
  )
  return make_succ_response({'result': True})
