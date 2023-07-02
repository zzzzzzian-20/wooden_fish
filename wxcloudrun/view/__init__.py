from flask.views import View
from flask import request
from sqlalchemy.engine import Engine
from wxcloudrun import db


class BasicView(View):
  @property
  def headers(self):
    return request.headers
  
  @property
  def openid(self) -> str:
    return self.headers.get('X-WX-OPENID')
  
  @property
  def appid(self) -> str:
    return self.headers.get('X-WX-APPID')

  @property
  def dbe(self) -> Engine:
    return db.engine
