;(function(){
  function qs(s){return document.querySelector(s)}
  function text(el, t){el.textContent=t}
  function on(el, ev, fn){el.addEventListener(ev, fn)}
  function fetchConfig(){return fetch('/config').then(function(r){return r.json()})}
  function fillServers(list){var sel=qs('#server'); sel.innerHTML=''; list.forEach(function(u){var o=document.createElement('option'); o.value=u; o.innerHTML=u; sel.appendChild(o)})}
  function init(){fetchConfig().then(function(cfg){var list=(cfg.servers||[]).filter(function(u){return u&&u.indexOf('localhost')===-1&&u.indexOf('127.0.0.1')===-1}); var scheme=(location.protocol==='https:'?'wss':'ws'); var current=scheme+'://'+location.host+'/ws'; if(list.indexOf(current)===-1){list.unshift(current)} fillServers(list)})}
  function login(){var nick=qs('#nick').value.trim(); var pwd=qs('#pwd').value.trim(); var server=qs('#server').value.trim(); var msg=qs('#loginMsg'); if(!nick){text(msg,'请输入昵称');return} if(pwd!=='123456'){text(msg,'密码错误');return} if(!server){text(msg,'请选择服务器');return} sessionStorage.setItem('nick',nick); sessionStorage.setItem('server',server); location.href='/chat'}
  init()
  on(qs('#loginBtn'),'click',function(e){e.preventDefault(); login()})
})();
