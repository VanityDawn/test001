import os
import json
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.escape
import tornado.template
import tornado.httpclient

clients = set()
nicknames = {}

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.redirect("/login")

class LoginHandler(tornado.web.RequestHandler):
    def get(self):
        loader = tornado.template.Loader(os.path.join(os.path.dirname(__file__), "templates"))
        self.write(loader.load("login.html").generate())

class ChatPageHandler(tornado.web.RequestHandler):
    def get(self):
        loader = tornado.template.Loader(os.path.join(os.path.dirname(__file__), "templates"))
        self.write(loader.load("chat.html").generate())

class ConfigHandler(tornado.web.RequestHandler):
    def get(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"servers": [f"ws://{self.request.host}/ws"]}
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(tornado.escape.json_encode(data))

class AIStreamHandler(tornado.web.RequestHandler):
    async def get(self):
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        q = self.get_argument("q", default="")
        api_key = os.environ.get("SILICONFLOW_API_KEY", "sk-azuhmndftogjstwbmcivaajxrtyxpmolwttbgiknvhgrbwwz")
        model = os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen2.5-7B-Instruct")
        api_url = os.environ.get("SILICONFLOW_API_URL", "https://api.siliconflow.cn/v1/chat/completions")
        if not api_key:
            await self.write("event: error\n")
            await self.write("data: 缺少SILICONFLOW_API_KEY\n\n")
            await self.flush()
            return
        payload = {
            "model": model,
            "stream": True,
            "messages": [
                {"role": "system", "content": "你是成小理，简洁友好地回答"},
                {"role": "user", "content": q},
            ],
        }
        client = tornado.httpclient.AsyncHTTPClient()
        done_sent = False
        buf = ""

        async def write_chunk(delta):
            await self.write("event: chunk\n")
            await self.write("data: " + delta.replace("\n", " ") + "\n\n")
            await self.flush()

        async def write_done():
            nonlocal done_sent
            if not done_sent:
                done_sent = True
                await self.write("event: done\n")
                await self.write("data: 完成\n\n")
                await self.flush()

        def on_chunk(chunk):
            nonlocal buf
            s = chunk.decode("utf-8", errors="ignore")
            buf += s
            while True:
                idx = buf.find("\n")
                if idx == -1:
                    break
                line = buf[:idx].strip()
                buf = buf[idx+1:]
                if not line:
                    continue
                if line.startswith("data:"):
                    js = line[5:].strip()
                    if js == "[DONE]":
                        tornado.ioloop.IOLoop.current().add_callback(write_done)
                        continue
                    try:
                        obj = json.loads(js)
                    except Exception:
                        continue
                    delta = None
                    if obj.get("choices"):
                        ch = obj["choices"][0]
                        if "delta" in ch and ch["delta"].get("content"):
                            delta = ch["delta"]["content"]
                        elif "message" in ch and ch["message"].get("content"):
                            delta = ch["message"]["content"]
                    if delta:
                        tornado.ioloop.IOLoop.current().add_callback(write_chunk, delta)

        try:
            req = tornado.httpclient.HTTPRequest(
                api_url,
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
                body=tornado.escape.json_encode(payload),
                request_timeout=300,
                streaming_callback=on_chunk,
            )
            resp = await client.fetch(req, raise_error=False)
            if resp.code != 200:
                await self.write("event: error\n")
                body = ""
                try:
                    body = resp.body.decode("utf-8", errors="ignore")
                except Exception:
                    body = ""
                await self.write("data: 接口错误 " + str(resp.code) + (" " + body if body else "") + "\n\n")
                await self.flush()
                return
            await write_done()
        except Exception as e:
            await self.write("event: error\n")
            try:
                msg = str(e)
            except Exception:
                msg = "服务异常"
            await self.write("data: " + (msg or "服务异常") + "\n\n")
            await self.flush()

class AITestHandler(tornado.web.RequestHandler):
    async def get(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        q = self.get_argument("q", default="")
        api_key = os.environ.get("SILICONFLOW_API_KEY", "sk-azuhmndftogjstwbmcivaajxrtyxpmolwttbgiknvhgrbwwz")
        model = os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen2.5-7B-Instruct")
        api_url = os.environ.get("SILICONFLOW_API_URL", "https://api.siliconflow.cn/v1/chat/completions")
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": "你是成小理，简洁友好地回答"},
                {"role": "user", "content": q or "你好"},
            ],
        }
        client = tornado.httpclient.AsyncHTTPClient()
        try:
            req = tornado.httpclient.HTTPRequest(
                api_url,
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                body=tornado.escape.json_encode(payload),
                request_timeout=60,
            )
            resp = await client.fetch(req, raise_error=False)
            if resp.code != 200:
                body = resp.body.decode("utf-8", errors="ignore") if resp.body else ""
                self.set_status(500)
                self.finish({"error": resp.code, "body": body})
                return
            js = json.loads(resp.body.decode("utf-8", errors="ignore"))
            out = ""
            try:
                out = js["choices"][0]["message"]["content"]
            except Exception:
                out = json.dumps(js)
            self.finish({"ok": True, "text": out})
        except Exception as e:
            self.set_status(500)
            self.finish({"error": str(e)})

def make_bot_reply(txt):
    if txt.startswith("@成小理"):
        return None
    if txt.startswith("@音乐一下"):
        return "音乐功能接口预留，当前仅占位响应"
    if txt.startswith("@电影"):
        return None
    if txt.startswith("@天气"):
        return "天气功能接口预留，当前仅占位响应"
    if txt.startswith("@新闻"):
        return "新闻功能接口预留，当前仅占位响应"
    if txt.startswith("@小视频"):
        return "小视频功能接口预留，当前仅占位响应"
    return None

class ChatWebSocket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        clients.add(self)

    def on_message(self, message):
        try:
            data = tornado.escape.json_decode(message)
        except Exception:
            return
        t = data.get("type")
        if t == "join":
            nick = data.get("nick", "")
            nicknames[self] = nick
            msg = {"type": "system", "text": f"{nick} 加入了房间"}
            for c in list(clients):
                try:
                    c.write_message(tornado.escape.json_encode(msg))
                except Exception:
                    pass
        elif t == "chat":
            nick = nicknames.get(self, "")
            text = data.get("text", "")
            msg = {"type": "chat", "nick": nick, "text": text}
            for c in list(clients):
                try:
                    c.write_message(tornado.escape.json_encode(msg))
                except Exception:
                    pass
            bot = make_bot_reply(text.strip())
            if bot:
                bot_msg = {"type": "bot", "nick": "聊天室助手", "text": bot}
                for c in list(clients):
                    try:
                        c.write_message(tornado.escape.json_encode(bot_msg))
                    except Exception:
                        pass

    def on_close(self):
        clients.discard(self)
        nick = nicknames.pop(self, None)
        if nick:
            msg = {"type": "system", "text": f"{nick} 离开了房间"}
            for c in list(clients):
                try:
                    c.write_message(tornado.escape.json_encode(msg))
                except Exception:
                    pass

def make_app():
    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
    }
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
        (r"/chat", ChatPageHandler),
        (r"/config", ConfigHandler),
        (r"/ai/test", AITestHandler),
        (r"/ai/sse", AIStreamHandler),
        (r"/ws", ChatWebSocket),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": settings["static_path"]}),
    ], **settings)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8888"))
    app = make_app()
    app.listen(port)
    tornado.ioloop.IOLoop.current().start()

