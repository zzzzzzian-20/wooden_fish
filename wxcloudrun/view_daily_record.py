from flask import request
from marshmallow import Schema, fields
from marshmallow.validate import Length
from sqlalchemy.engine import Engine
from sqlalchemy import select
from sqlalchemy import desc
from webargs.flaskparser import use_kwargs

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
