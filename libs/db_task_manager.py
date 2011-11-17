# -*- encoding: utf-8 -*-
# author: binux<17175297.hk@gmail.com>

import logging
import re
import db
from time import time
from libs.lixian_api import LiXianAPI
from libs.util import determin_url_type
from tornado.options import options

ui_re = re.compile(r"ui=\d+")
ti_re = re.compile(r"ti=\d+")
def fix_lixian_url(url, uid, tid):
    url = ui_re.sub("ui=%d" % uid, url)
    url = ti_re.sub("ti=%d" % tid, url)
    return url

def sqlalchemy_rollback(func):
    def wrap(self, *args, **kwargs):
        if db.engine.name == "sqlite":
            self.session = db.Session(weak_identity_map=False)
        try:
            return func(self, *args, **kwargs)
        except db.SQLAlchemyError, e:
            logging.error(e)
            self.session.rollback()
            raise
        if db.engine.name == "sqlite":
            self.session.close()
    return wrap

class DBTaskManager(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self._last_check_login = 0
        self._last_update_task = 0
        self._last_update_downloading_task = 0

        self.session = db.Session(weak_identity_map=False)

        self._xunlei = LiXianAPI()
        self.last_task_id = 0
        self.islogin = self._xunlei.login(self.username, self.password)
        self._last_check_login = time()

    @property
    def xunlei(self):
        if self._last_check_login + options.check_interval < time():
            if not self._xunlei.check_login():
                self._xunlei.logout()
                self.islogin = self._xunlei.login(self.username, self.password)
            self._last_check_login = time()
        return self._xunlei

    @property
    def gdriveid(self):
        return self._xunlei.gdriveid

    @property
    def uid(self):
        return self._xunlei.uid

    def _update_task_list(self, limit=10, st=0, ignore=False):
        tasks = self.xunlei.get_task_list(limit, st)
        for task in tasks[::-1]:
            self.last_task_id = task['task_id']
            db_task_status = self.session.query(db.Task.status).filter(
                    db.Task.id == task['task_id']).first()
            if db_task_status == "finished":
                continue

            db_task = db.Task()
            db_task.id = task['task_id']
            db_task.create_uid = self.uid
            db_task.cid = task['cid']
            db_task.url = task['url']
            db_task.lixian_url = task['lixian_url']
            db_task.taskname = task['taskname']
            db_task.task_type = task['task_type']
            db_task.status = task['status']
            db_task.process = task['process']
            db_task.size = task['size']
            db_task.format = task['format']

            self.session.merge(db_task)
            self._update_file_list(db_task)

        self.session.commit()

    def _update_file_list(self, task):
        if task.task_type == "normal":
            tmp_file = dict(
                    task_id = task.task_id,
                    url = task.url,
                    lixian_url = task.lixian_url,
                    title = task.taskname,
                    status = task.status,
                    dirtitle = task.taskname,
                    process = task.process,
                    size = task.size,
                    format = task.format
                    )
            files = [tmp_file, ]
        elif task.task_type in ("bt", "magnet"):
            files = self.xunlei.get_bt_list(task.id, task.cid)

        for file in files:
            db_file = db.File()
            db_file.id = file['task_id']
            db_file.task_id = task.id
            db_file.cid = file['cid']
            db_file.url = file['url']
            db_file.lixian_url = file['lixian_url']
            db_file.title = file['title']
            db_file.dirtitle = file['dirtitle']
            db_file.status = file['status']
            db_file.process = file['process']
            db_file.size = file['size']
            db_file.format = file['format']

            self.session.merge(db_file)

    @sqlalchemy_rollback
    def get_task(self, task_id):
        return self.session.query(db.Task).get(task_id)
    
    @sqlalchemy_rollback
    def get_task_list(self, start_task_id=0, limit=30):
        self.update()
        query = self.session.query(db.Task)
        if start_task_id:
            create_time = self.session.query(db.Task.createtime).filter(db.Task.id == start_task_id)
            if not create_time:
                return []
            query = query.filter(db.Task.createtime < create_time)
        query = query.order_by(db.desc(db.Task.createtime)).limit(limit)
        return query.all()
    
    @sqlalchemy_rollback
    def get_file_list(self, task_id):
        task = self.get_task(task_id)
        if not task: return []

        #fix lixian url
        if task.create_uid != self.uid:
            if not self.last_task_id:
                raise Exception, "add a task and refresh task list first!"
            for file in task.files:
                file.lixian_url = fix_lixian_url(
                        file.lixian_url, self.uid, self.last_task_id)

        return task.files

    @sqlalchemy_rollback
    def add_task(self, url):
        task_id = self.session.query(db.Task.id).filter(db.Task.url == url).first()
        if task_id:
            return task_id

        url_type = determin_url_type(url)
        if url_type in ("bt", "magnet"):
            result = self.xunlei.add_bt_task(url)
        elif url_type in ("normal", "ed2k", "thunder"):
            result = self.xunlei.add_task(url)
        else:
            result = self.xunlei.add_batch_task([url, ])

        if result:
            self._update_task_list(5)
            return True
        return False

    def update(self):
        if self._last_update_task + options.finished_task_check_interval < time():
            self._last_update_task = time()
            self._update_task_list(options.task_list_limit)
        if self._last_update_downloading_task + \
                options.downloading_task_check_interval < time():
            self._last_update_downloading_task = time()
            self._update_task_list(options.task_list_limit, "downloading")
