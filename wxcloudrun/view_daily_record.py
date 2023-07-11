from datetime import datetime, timedelta
from functools import lru_cache
from uuid import uuid4

from flask import request
from marshmallow import Schema, fields
from marshmallow.validate import Length, OneOf, Range
from sqlalchemy import and_, asc, desc, func, select, text
from sqlalchemy.engine import Engine
from webargs.flaskparser import use_kwargs

from run import app
from wxcloudrun import db
from wxcloudrun.response import make_err_response, make_succ_response
from wxcloudrun.tables import share_knock as share_knock_table
from wxcloudrun.tables import wish as wish_table
from wxcloudrun.tables import wish_share as wish_share_table

WISH_SHARE_PREFIX = 'SH'


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
            wish=wish
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
               'count', 'knock', 'fulfill', 'wish', 'share_count')


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
               table.c.wish, 
               table.c.share_count)
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


class WishShareStats(Schema):
  wish_id = fields.Integer(required=True, validate=[Range(min=0)])


@app.route('/api/wooden_fish/wish_share_stats',
           methods=['POST'])
@use_kwargs(WishShareStats)
def wish_stats(wish_id: int):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})
  engine: Engine = db.engine
  table = wish_table.table
  helper_table = share_knock_table.table

  sql = select(
      table.c.helper_total,
      table.c.share_count_total,
      table.c.share_knock_total,
      table.c.helper,
      table.c.share_count,
      table.c.share_knock
  ).where(and_(table.c.id == wish_id,
               table.c.openid == openid))
  res = engine.execute(sql).fetchall()
  if not res:
    return make_err_response({'msg': 'wish not found'})
  res = dict(zip(('helper_total',
                  'share_count_total',
                  'share_knock_total',
                  'helper',
                  'share_count',
                  'share_knock'),
                 res[0]))

  last_week_sql = select(
      func.count(helper_table.c.id).label('last_week_helper'),
      func.sum(helper_table.c.count).label('last_week_count'),
      func.sum(helper_table.c.knock).label('last_week_knock')
  ).where(and_(helper_table.c.wish_id == wish_id,
               helper_table.c.create_time >= (datetime.now() - timedelta(days=7)).timestamp()))
  helper_res = engine.execute(last_week_sql).fetchall()
  helper_res = dict(zip(('last_week_helper',
                         'last_week_count',
                         'last_week_knock'),
                        helper_res[0]))
  res.update(helper_res)
  return make_succ_response(res)


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
  gather_shared = fields.Boolean(load_default=False)


@app.route('/api/wooden_fish/wish_update',
           methods=['POST'])
@use_kwargs(WishUpdate)
def wish_update(wish_id: int, fulfill: bool, count: int, wish: str, knock: int,
                clear_record: bool, gather_shared: bool):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})
  engine: Engine = db.engine
  table = wish_table.table

  values = dict(last_time=text('CURRENT_TIMESTAMP'))
  if clear_record:
    values['count'] = 0
    values['knock'] = 0
  elif gather_shared:
    values.update(
      # add to total
      count=table.c.count + table.c.share_count,
      knock=table.c.knock + table.c.share_knock,
      # add to helper total
      helper_total=table.c.helper_total + table.c.helper,
      share_count_total=table.c.share_count_total + table.c.share_count,
      share_knock_total=table.c.share_knock_total + table.c.share_knock,
      # remove
      helper=0, 
      share_count=0, 
      share_knock=0
    )
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

  sql = select(origin_table.c.wish).where(and_(origin_table.c.id == wish_id,
                                               origin_table.c.openid == openid))
  res = engine.execute(sql).fetchall()
  if not res:
    return make_err_response({'msg': 'wish not found'})
  share_id = WISH_SHARE_PREFIX + uuid4().hex[:16]

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


class WishShareUpdate(Schema):
  share_id = fields.String(required=True)
  count = fields.Integer(load_default=1,
                         validate=[Range(min=0, max=100)])
  knock = fields.Integer(load_default=None,
                         validate=[Range(min=0, max=10000)])


@lru_cache(maxsize=64)
def get_wish_id_from_share_id(share_id):
  table = wish_share_table.table
  engine: Engine = db.engine
  res = engine.execute(
      select(table.c.wish_id).where(table.c.share_id == share_id).limit(1)
  ).fetchall()
  if not res:
    return
  return res[0][0]


@app.route('/api/wooden_fish/wish_share_update',
           methods=['POST'])
@use_kwargs(WishShareUpdate)
def wish_share_update(share_id: str, count: int, knock: int):
  openid = request.headers.get('X-WX-OPENID')
  if openid is None:
    return make_err_response({'msg': 'not login'})

  wish_id = get_wish_id_from_share_id(share_id)
  if wish_id is None:
    return make_err_response({'msg': 'wish not found'})
  engine: Engine = db.engine
  table = wish_table.table
  insert_table = share_knock_table.table

  insert_val = {'wish_id': wish_id, 'openid': openid}
  values = {}
  if count:
    insert_val['count'] = count
    values['helper'] = table.c.helper + 1
    values['share_count'] = table.c.share_count + count
  if knock:
    insert_val['knock'] = knock
    values['share_knock'] = table.c.share_knock + knock
  if values:
    engine.execute(
        table.update().values(**values).where(table.c.id == wish_id)
    )
  engine.execute(
      insert_table.insert().values(**insert_val)
  )
  return make_succ_response({'result': True})
