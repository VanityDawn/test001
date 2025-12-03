;(function(){
  function qs(s){return document.querySelector(s)}
  function qsa(s){return Array.prototype.slice.call(document.querySelectorAll(s))}
  function on(el, ev, fn){el.addEventListener(ev, fn)}
  function append(parent, el){parent.appendChild(el)}
  function makeRow(cls){var r=document.createElement('div'); r.className='row '+cls; return r}
  function makeBubble(txt){var b=document.createElement('div'); b.className='bubble'; b.textContent=txt; return b}
  function makeMeta(txt){var m=document.createElement('div'); m.className='meta'; m.textContent=txt; return m}
  function pushSystem(t){var el=document.createElement('div'); el.className='system'; el.textContent=t; append(qs('#messages'), el); scrollBottom()}
  function pushMsg(nick, txt, mine){var row=makeRow(mine?'me':'other'); var bubble=makeBubble(txt); var meta=makeMeta(nick); append(row, meta); append(row, bubble); append(qs('#messages'), row); scrollBottom()}
  function pushBot(txt){var row=makeRow('bot'); var bubble=makeBubble(txt); append(row, bubble); append(qs('#messages'), row); scrollBottom()}
  function pushBotStreaming(){var row=makeRow('bot'); var bubble=makeBubble(''); append(row, bubble); append(qs('#messages'), row); scrollBottom(); return bubble}
  function scrollBottom(){var m=qs('#messages'); m.scrollTop=m.scrollHeight}
  function getNick(){return sessionStorage.getItem('nick')||''}
  function getServer(){return sessionStorage.getItem('server')||''}
  function ensureLogin(){var n=getNick(); var s=getServer(); if(!n||!s){location.href='/login'} return {nick:n, server:s}}
  var MOVIE_PARSE='https://jx.m3u8.tv/jiexi/?url='
  function parseMovie(text){var m=text.match(/@电影\s*\[(.+?)\]/); if(!m){return null} var url=m[1].trim(); url=url.replace(/^`+|`+$/g,'').replace(/^"+|"+$/g,'').replace(/^'+|'+$/g,''); if(url.endsWith(']')){url=url.slice(0,-1)} if(!/^https?:/i.test(url)){return null} return url}
  function pushMovie(nick, url, mine){var row=makeRow(mine?'me':'other'); var meta=makeMeta(nick); var bubble=document.createElement('div'); bubble.className='bubble'; var iframe=document.createElement('iframe'); iframe.width=400; iframe.height=400; iframe.src=MOVIE_PARSE+encodeURIComponent(url); iframe.setAttribute('frameborder','0'); iframe.setAttribute('allowfullscreen','true'); bubble.appendChild(iframe); append(row, meta); append(row, bubble); append(qs('#messages'), row); scrollBottom()}
  function connect(){var cfg=ensureLogin(); var ws=new WebSocket(cfg.server); ws.onopen=function(){ws.send(JSON.stringify({type:'join', nick:cfg.nick}))}; ws.onmessage=function(e){try{var data=JSON.parse(e.data)}catch(err){return} if(data.type==='system'){pushSystem(data.text)} else if(data.type==='chat'){var mine=data.nick===cfg.nick; pushMsg(data.nick, data.text, mine); var u=parseMovie(data.text); if(u){pushMovie(data.nick,u,mine)}} else if(data.type==='bot'){pushBot(data.text)}}; ws.onclose=function(){pushSystem('连接已关闭')}; return ws}
  function send(ws){var v=qs('#msgInput').value.trim(); if(!v){return} ws.send(JSON.stringify({type:'chat', text:v})); if(v.indexOf('@成小理')===0){var prompt=v.replace('@成小理','').trim(); var bubble=pushBotStreaming(); var es=new EventSource('/ai/sse?q='+encodeURIComponent(prompt)); es.addEventListener('chunk',function(e){bubble.textContent+=e.data; scrollBottom()}); es.addEventListener('done',function(){es.close()}); es.addEventListener('error',function(){try{es.close()}catch(_){} fetch('/ai/test?q='+encodeURIComponent(prompt)).then(function(r){return r.json()}).then(function(js){if(js&&js.ok){bubble.textContent=js.text}else{bubble.textContent='AI错误: '+(js&&(js.body||js.error)||'未知错误')} scrollBottom()}).catch(function(){bubble.textContent='AI服务错误或未配置'; scrollBottom()})})} qs('#msgInput').value=''}
  function buildEmoji(){var panel=qs('#emojiPanel'); var list='😀 😃 😄 😁 😆 😅 😂 🙂 😉 😊 😇 🙃 😍 😘 😜 🤗 🤔 🤨 😐 😑 😶 🙄 😏 😣 😥 😮 🤐 😯 😪 😫 🥱 😴 🤒 🤕 🤢 🤮 🤧 🥵 🥶 😵 🤯 🤠 😎 🥸 🤓 🧐 😕 😟 🙁 ☹️ 😮‍💨 😤 😢 😭 😦 😧 😨 😱 😰 😳 🥺 🤤 🤩 🥰 💘 💖 💗 💙 💚 💛 💜 🧡 🤍 🤎 ❤️'.split(' '); list.forEach(function(e){var i=document.createElement('div'); i.className='emoji-item'; i.textContent=e; on(i,'click',function(){qs('#msgInput').value+=e; qs('#msgInput').focus()}); append(panel,i)})}
  function toggleEmoji(){var p=qs('#emojiPanel'); if(p.classList.contains('hidden')){p.classList.remove('hidden')}else{p.classList.add('hidden')}}
  var ws=connect()
  on(qs('#sendBtn'),'click',function(){send(ws)})
  on(qs('#msgInput'),'keydown',function(e){if(e.key==='Enter'){e.preventDefault(); send(ws)}})
  on(qs('#emojiBtn'),'click',function(){toggleEmoji()})
  on(qs('#historyBtn'),'click',function(){alert('历史记录功能正在建设中')})
  on(qs('#exitBtn'),'click',function(){try{ws.close()}catch(e){} location.href='/login'})
  buildEmoji()
})();
