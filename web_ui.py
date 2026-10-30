"""
HTML/CSS/JS templates for web interface
Edit design here without touching server code
"""

def get_css(theme="dark"):
    """Returns CSS styles for specified theme"""
    if theme == "light":
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f7; min-height: 100vh; color: #1d1d1f; overflow-x: hidden; }
        .container { position: relative; z-index: 1; max-width: 800px; margin: 0 auto; padding: 60px 20px; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { color: #1d1d1f; font-size: 48px; font-weight: 300; margin-bottom: 12px; }
        .header p { color: rgba(0,0,0,0.5); font-size: 14px; margin-bottom: 20px; }
        .theme-toggle { position: fixed; top: 20px; right: 20px; width: 50px; height: 50px; border-radius: 50%; background: #fff; border: 1px solid #d2d2d7; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .upload-btn { display: inline-block; padding: 12px 24px; background: rgba(0, 122, 255, 0.1); border: 1px solid #007aff; border-radius: 25px; color: #007aff; cursor: pointer; font-size: 15px; transition: 0.3s; }
        .upload-btn:hover { background: #007aff; color: #fff; }
        .file-list { list-style: none; background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .file-item { padding: 20px; border-bottom: 1px solid #d2d2d7; display: flex; justify-content: space-between; align-items: center; }
        .file-item:last-child { border-bottom: none; }
        .file-link { color: #1d1d1f; text-decoration: none; font-size: 18px; display: block; margin-bottom: 6px; }
        .file-link:hover { color: #007aff; }
        .file-meta { color: rgba(0,0,0,0.5); font-size: 13px; }
        .download-btn { width: 40px; height: 40px; border-radius: 50%; background: rgba(0, 122, 255, 0.1); border: 1px solid #007aff; display: flex; align-items: center; justify-content: center; text-decoration: none; color: #007aff; transition: 0.3s; }
        .download-btn:hover { background: #007aff; color: #fff; }
        .checkbox { width: 20px; height: 20px; cursor: pointer; margin-right: 12px; }
        """
    else:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #000; min-height: 100vh; color: #e0e0e0; overflow-x: hidden; }
        #starfield { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; }
        .star { position: absolute; background: white; border-radius: 50%; animation: twinkle 3s infinite; }
        @keyframes twinkle { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
        .container { position: relative; z-index: 1; max-width: 800px; margin: 0 auto; padding: 60px 20px; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { color: #fff; font-size: 48px; font-weight: 300; margin-bottom: 12px; text-shadow: 0 0 40px rgba(102, 126, 234, 0.5); }
        .header p { color: rgba(255,255,255,0.5); font-size: 14px; margin-bottom: 20px; }
        .theme-toggle { position: fixed; top: 20px; right: 20px; width: 50px; height: 50px; border-radius: 50%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 24px; color: #fff; }
        .upload-btn { display: inline-block; padding: 12px 24px; background: rgba(102, 126, 234, 0.25); border: 1px solid #667eea; border-radius: 25px; color: #fff; cursor: pointer; font-size: 15px; transition: 0.3s; }
        .upload-btn:hover { background: #667eea; }
        .file-list { list-style: none; }
        .file-item { padding: 20px 0; border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; justify-content: space-between; align-items: center; }
        .file-link { color: #fff; text-decoration: none; font-size: 18px; display: block; margin-bottom: 6px; }
        .file-link:hover { color: #667eea; }
        .file-meta { color: rgba(255,255,255,0.4); font-size: 13px; }
        .download-btn { width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; justify-content: center; text-decoration: none; color: #fff; transition: 0.3s; }
        .download-btn:hover { background: #667eea; }
        .checkbox { width: 20px; height: 20px; cursor: pointer; margin-right: 12px; }
        """

def get_star_script():
    """JavaScript for star animation"""
    return """
    const sf = document.getElementById("starfield");
    if (sf) {
        for(let i=0;i<150;i++){
            const s=document.createElement("div");
            s.className="star";
            s.style.left=Math.random()*100+"%";
            s.style.top=Math.random()*100+"%";
            s.style.width=s.style.height=Math.random()*3+"px";
            s.style.animationDelay=Math.random()*3+"s";
            sf.appendChild(s);
        }
    }
    """

def get_upload_script():
    """JavaScript for file upload"""
    return """
    async function uploadFiles(files){
        const st=document.getElementById("status");
        for(let i=0;i<files.length;i++){
            st.innerText="Uploading "+files[i].name+" ("+(i+1)+"/"+files.length+")...";
            await fetch("?upload="+encodeURIComponent(files[i].name),{method:"POST",body:files[i]});
        }
        location.reload();
    }
    """

def get_theme_script():
    """JavaScript for theme toggle"""
    return """
    function toggleTheme(){
        const url = new URL(window.location);
        const current = url.searchParams.get('theme') || 'dark';
        url.searchParams.set('theme', current === 'dark' ? 'light' : 'dark');
        window.location.href = url.toString();
    }
    """
