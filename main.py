#/usr/bin/env python
# -*- encoding: utf8 -*-
# author: binux<17175297.hk@gmail.com>

import os
import tornado
import logging
from time import time
from tornado import web
from tornado.ioloop import IOLoop
from tornado.options import define, options

define("debug", default=True, help="debug mode")
define("port", default=8880, help="the port tornado listen to")
define("username", help="xunlei vip login name")
define("password", help="xunlei vip password")
define("ga_account", default="", help="account of google analytics")
define("check_interval", default=60*60, help="the interval of checking login status")
define("cross_userscript", default="http://userscripts.org/scripts/show/117745",
        help="the web url of cross cookie userscirpt")
define("cross_userscript_local", default="/static/cross-cookie.userscript.js",
        help="the local path of cross cookie userscirpt")
define("cross_cookie_url", default="http://vip.xunlei.com/js/vip_baidu.js",
        help="the url to insert to")
define("cookie_str", default="gdriveid=%s; domain=.vip.xunlei.com",
        help="the cookie insert to cross path")
define("finished_task_check_interval", default=60*60,
        help="the interval of getting the task list")
define("downloading_task_check_interval", default=5*60,
        help="the interval of getting the downloading task list")
define("task_list_limit", default=10000,
        help="the max limit of get task list each time")
define("database_echo", default=False,
        help="sqlalchemy database engine echo switch")
define("database_engine", default="sqlite:///task_files.db",
        help="the database connect string for sqlalchemy")

class Application(web.Application):
    def __init__(self):
        from handlers import handlers, ui_modules
        from libs.util import ui_methods
        from libs.db_task_manager import DBTaskManager
        settings = dict(
            debug=options.debug,
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),

            ui_modules=ui_modules,
            ui_methods=ui_methods,
        )
        super(Application, self).__init__(handlers, **settings)

        self.task_manager = DBTaskManager(
                    username = options.username,
                    password = options.password
                )
        if not self.task_manager.islogin:
            raise Exception, "xunlei login error"
        logging.info("load finished!")

def main():
    tornado.options.parse_command_line()

    application = Application()
    application.listen(options.port)
    IOLoop.instance().start()

if __name__ == "__main__":
    main()
