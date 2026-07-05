function acceptCookies(){
    document.cookie="cookies_accepted=true;max-age=31536000;path=/";
    var banner=document.getElementById("cookie-banner");
    if(banner)banner.style.display="none";
}
(function(){
    if(document.cookie.indexOf("cookies_accepted=true")===-1){
        var b=document.createElement("div");
        b.id="cookie-banner";
        b.style.cssText="display:none;position:fixed;bottom:0;left:0;right:0;background:#0B1121;color:rgba(255,255,255,0.85);padding:16px 24px;z-index:9999;border-top:1px solid rgba(255,255,255,0.08);font-size:0.88rem;line-height:1.6;box-shadow:0 -4px 12px rgba(0,0,0,0.15)";
        b.innerHTML='<div style="max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap"><span style="flex:1;min-width:280px">We use cookies to personalize content and ads, to analyze traffic, and to serve personalized ads via Google AdSense. By continuing, you consent to our use of cookies. <a href="/privacy/" style="color:#93c5fd;text-decoration:underline" target="_blank" rel="noopener">Privacy Policy</a></span><div style="display:flex;gap:10px;flex-shrink:0"><button onclick="acceptCookies()" style="padding:8px 20px;background:#2563EB;color:#fff;border:none;border-radius:6px;font-size:0.85rem;font-weight:600;cursor:pointer">Accept</button></div></div>';
        document.body.appendChild(b);
        b.style.display="block";
    }
})();
