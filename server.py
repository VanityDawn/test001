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
        proto = self.request.headers.get("X-Forwarded-Proto") or getattr(self.request, "protocol", "http")
        ws_scheme = "wss" if str(proto).lower() == "https" else "ws"
        current = f"{ws_scheme}://{self.request.host}/ws"
        servers = []
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                servers = list(data.get("servers") or [])
            except Exception:
                servers = []
        if not servers:
            servers = [current]
        else:
            cleaned = []
            for s in servers:
                try:
                    u = str(s or "").strip()
                except Exception:
                    u = ""
                if not u:
                    continue
                if "localhost" in u or "127.0.0.1" in u:
                    continue
                cleaned.append(u)
            if current not in cleaned:
                cleaned.insert(0, current)
            servers = cleaned
        out = {"servers": servers}
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(tornado.escape.json_encode(out))

class UsersHandler(tornado.web.RequestHandler):
    def get(self):
        users = [{"nick": n, "online": True} for n in nicknames.values() if n]
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(tornado.escape.json_encode({"list": users}))

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
        return None
    if txt.startswith("@电影"):
        return None
    if txt.startswith("@天气"):
        return None
    if txt.startswith("@新闻"):
        return None
    if txt.startswith("@小视频"):
        return "小视频功能接口预留，当前仅占位响应"
    return None

def broadcast_users():
    users = [{"nick": n, "online": True} for n in nicknames.values() if n]
    msg = {"type": "users", "list": users}
    for c in list(clients):
        try:
            c.write_message(tornado.escape.json_encode(msg))
        except Exception:
            pass

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
            broadcast_users()
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
            if text.strip().startswith("@音乐一下"):
                tornado.ioloop.IOLoop.current().spawn_callback(handle_music_request, nick)
            if text.strip().startswith("@天气"):
                city = extract_city(text)
                tornado.ioloop.IOLoop.current().spawn_callback(handle_weather_request, nick, city)
            if text.strip().startswith("@新闻"):
                tornado.ioloop.IOLoop.current().spawn_callback(handle_news_request, nick)

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
        broadcast_users()

def make_app():
    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
        "xheaders": True,
    }
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
        (r"/chat", ChatPageHandler),
        (r"/config", ConfigHandler),
        (r"/users", UsersHandler),
        (r"/ai/test", AITestHandler),
        (r"/ai/sse", AIStreamHandler),
        (r"/ws", ChatWebSocket),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": settings["static_path"]}),
    ], **settings)

async def handle_music_request(nick: str):
    url = "https://v2.xxapi.cn/api/randomkuwo"
    client = tornado.httpclient.AsyncHTTPClient()
    try:
        req = tornado.httpclient.HTTPRequest(url, method="GET", headers={"User-Agent": "xiaoxiaoapi/1.0.0"}, request_timeout=30)
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            return
        js = json.loads(resp.body.decode("utf-8", errors="ignore"))
        d = js.get("data") or {}
        name = (d.get("name") or "").strip()
        singer = (d.get("singer") or "").strip()
        image = (d.get("image") or "").strip()
        src = (d.get("url") or "").strip()
        for v in ("`", "\"", "'"):
            image = image.strip(v)
            src = src.strip(v)
        if not src:
            return
        msg = {"type": "music", "nick": nick, "name": name, "singer": singer, "image": image, "url": src}
        for c in list(clients):
            try:
                c.write_message(tornado.escape.json_encode(msg))
            except Exception:
                pass
    except Exception:
        pass

def extract_city(txt: str) -> str:
    s = txt.strip()
    b = s.find("[")
    if b != -1:
        e = s.find("]", b + 1)
        if e != -1:
            return s[b + 1:e].strip()
    return s.replace("@天气", "").strip()

async def handle_weather_request(nick: str, city: str):
    key = os.environ.get("WEATHER_API_KEY", "c2db36150a17a5f9")
    base = "https://v2.xxapi.cn/api/weather"
    if not city:
        return
    q = f"{base}?city={tornado.escape.url_escape(city)}&key={tornado.escape.url_escape(key)}"
    client = tornado.httpclient.AsyncHTTPClient()
    try:
        req = tornado.httpclient.HTTPRequest(q, method="GET", headers={"User-Agent": "xiaoxiaoapi/1.0.0"}, request_timeout=30)
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            return
        js = json.loads(resp.body.decode("utf-8", errors="ignore"))
        if js.get("code") != 200:
            return
        d = js.get("data") or {}
        city_name = (d.get("city") or city).strip()
        items = d.get("data") or []
        days = []
        for it in items:
            days.append({
                "date": (it.get("date") or "").strip(),
                "temperature": (it.get("temperature") or "").strip(),
                "weather": (it.get("weather") or "").strip(),
                "wind": (it.get("wind") or "").strip(),
                "air_quality": (it.get("air_quality") or "").strip(),
            })
        msg = {"type": "weather", "nick": nick, "city": city_name, "days": days}
        for c in list(clients):
            try:
                c.write_message(tornado.escape.json_encode(msg))
            except Exception:
                pass
    except Exception:
        pass

async def handle_news_request(nick: str):
    url = "https://v2.xxapi.cn/api/weibohot"
    client = tornado.httpclient.AsyncHTTPClient()
    try:
        req = tornado.httpclient.HTTPRequest(url, method="GET", headers={"User-Agent": "xiaoxiaoapi/1.0.0"}, request_timeout=30)
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            return
        js = json.loads(resp.body.decode("utf-8", errors="ignore"))
        if js.get("code") != 200:
            return
        arr = js.get("data") or []
        if not arr:
            return
        it = arr[0]
        title = (it.get("title") or "").strip()
        hot = (it.get("hot") or "").strip()
        link = (it.get("url") or "").strip()
        for v in ("`", "\"", "'"):
            link = link.strip(v)
        msg = {"type": "news", "nick": nick, "title": title, "hot": hot, "url": link}
        for c in list(clients):
            try:
                c.write_message(tornado.escape.json_encode(msg))
            except Exception:
                pass
    except Exception:
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8888"))
    app = make_app()
    app.listen(port)
    tornado.ioloop.IOLoop.current().start()

