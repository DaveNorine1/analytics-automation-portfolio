//minimal consent manager: stores choice in a first-party cookie and gates analytics
(function(){
  const get=()=>document.cookie.split('; ').find(c=>c.startsWith('consent='))?.split('=')[1];
  function loadAnalytics(){
    const s=document.createElement('script');s.src='https://www.googletagmanager.com/gtag/js?id=G-DEMO123';s.async=true;document.head.appendChild(s);
  }
  window.dataLayer=window.dataLayer||[];
  function decide(v){document.cookie='consent='+v+'; path=/; max-age=31536000';document.getElementById('cb')?.remove();if(v==='granted')loadAnalytics();}
  window.addEventListener('DOMContentLoaded',()=>{
    const c=get();
    if(c==='granted'){loadAnalytics();return}
    if(c==='denied')return;
    const b=document.createElement('div');b.id='cb';b.setAttribute('role','dialog');b.setAttribute('aria-label','Cookie consent');
    b.innerHTML='<p>We use cookies to measure site performance.</p><button id="accept">Accept all</button> <button id="decline">Decline</button>';
    document.body.appendChild(b);
    document.getElementById('accept').onclick=()=>decide('granted');
    document.getElementById('decline').onclick=()=>decide('denied');
  });
})();
