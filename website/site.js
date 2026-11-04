const platform=/Android/i.test(navigator.userAgent)?'android':/Windows/i.test(navigator.userAgent)?'windows':null;
if(platform){const link=document.querySelector(`[data-platform="${platform}"]`);link?.classList.add('recommended');if(link){const meta=link.querySelector('small');meta.textContent+=' · 适合当前设备';}}
