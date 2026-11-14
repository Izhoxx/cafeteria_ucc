(function(){
var d=document,r=d.documentElement;
function cur(){var t=r.getAttribute('data-theme');return t||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}
var tb=d.querySelector('[data-theme-toggle]');
if(tb)tb.addEventListener('click',function(){var n=cur()==='dark'?'light':'dark';r.setAttribute('data-theme',n);try{localStorage.setItem('ucc-theme',n)}catch(e){}});
d.querySelectorAll('.toast').forEach(function(t,i){var x=t.querySelector('.toast-x');
 function close(){t.classList.add('out');setTimeout(function(){t.remove()},260)}
 if(x)x.addEventListener('click',close);setTimeout(close,5000+i*700)});
var inp=d.querySelector('[data-filter]');
if(inp){var box=d.querySelector(inp.getAttribute('data-filter')),chips=d.querySelectorAll('[data-chip]'),empty=d.querySelector('[data-empty]'),only=false;
 function run(){var q=inp.value.trim().toLowerCase(),n=0;
  box.querySelectorAll('[data-name]').forEach(function(el){var ok=el.dataset.name.indexOf(q)>-1&&(!only||el.dataset.avail==='1');el.hidden=!ok;if(ok)n++});
  if(empty)empty.hidden=n>0}
 inp.addEventListener('input',run);
 chips.forEach(function(c){c.addEventListener('click',function(){chips.forEach(function(x){x.classList.remove('on')});c.classList.add('on');only=c.dataset.chip==='avail';run()})})}
var pay=d.querySelectorAll('[data-pay]');
if(pay.length){var lab=d.getElementById('dato-label'),dat=d.getElementById('dato'),wrap=d.getElementById('pay-data');
 var cfg={Nequi:['Número de celular','300 000 0000',1],Daviplata:['Número de celular','300 000 0000',1],PSE:['',' ',0],Tarjeta:['Número de tarjeta','1234 5678 9012 3456',1]};
 function upd(){var v=d.querySelector('[data-pay]:checked').value,c=cfg[v];wrap.hidden=!c[2];lab.textContent=c[0];dat.placeholder=c[1];dat.required=!!c[2]}
 pay.forEach(function(p){p.addEventListener('change',upd)});upd()}
d.querySelectorAll('[data-fill]').forEach(function(b){b.addEventListener('click',function(){d.getElementById('username').value=b.dataset.u;d.getElementById('password').value=b.dataset.p;d.getElementById('password').focus()})});
var fi=d.querySelector('input[type=file][data-preview]');
if(fi)fi.addEventListener('change',function(){var f=fi.files[0],pv=d.getElementById('preview');if(!f||!pv)return;var rd=new FileReader();rd.onload=function(){pv.style.backgroundImage='url('+rd.result+')';pv.classList.add('has')};rd.readAsDataURL(f)});
})();
