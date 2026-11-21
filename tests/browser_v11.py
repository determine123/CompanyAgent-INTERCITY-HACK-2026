"""Chromium UI regression using an in-process FastAPI network bridge.

Cloud Chromium disallows loopback HTTP; intercept app requests and serve the
real FastAPI app via TestClient. No external network, mocked services or keys.
"""
from __future__ import annotations
import os
import tempfile
from pathlib import Path
import sys
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='companyagent-v11-browser-') as runtime:
    os.environ['COMPANYAGENT_RUNTIME_DIR']=runtime
    os.environ['COMPANYAGENT_ADMIN_PASSWORD']='Chromium-local-test-pass-ONLY'
    os.environ['COMPANYAGENT_AUTO_SYNC']='false'
    os.environ.pop('B1X_API_KEY',None)
    from fastapi.testclient import TestClient
    from server import app
    with TestClient(app) as client, sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1365,'height':850})
        errors=[]
        def backend_request(url, method, body, headers):
            response=client.request(method,url,content=body,headers=headers)
            try: output=response.json()
            except Exception: output={'detail':response.text}
            return {'status':response.status_code,'body':output}
        page=context.new_page()
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        page.expose_function('__backendRequest',backend_request)
        html=(ROOT/'enterprise_web/index.html').read_text(encoding='utf-8')
        html=html.replace('<link rel="stylesheet" href="/enterprise/styles.css">','').replace('<script src="/enterprise/app.js"></script>','')
        page.set_content(html,wait_until='domcontentloaded')
        page.add_style_tag(content=(ROOT/'enterprise_web/styles.css').read_text(encoding='utf-8'))
        page.evaluate("""() => {
          window.fetch = async (url, init={}) => {
            const r = await window.__backendRequest(url,init.method||'GET',init.body||null,init.headers||{});
            return new Response(JSON.stringify(r.body),{status:r.status,headers:{'Content-Type':'application/json'}});
          };
          return true;
        }""")
        page.add_script_tag(content=(ROOT/'enterprise_web/app.js').read_text(encoding='utf-8'))
        page.locator('#loginUser').fill('admin')
        page.locator('#loginPassword').fill('Chromium-local-test-pass-ONLY')
        page.locator('#loginForm button[type=submit]').click()
        page.locator('#loginCover').wait_for(state='hidden',timeout=10000)
        page.locator('#taskStrict').uncheck()
        page.locator('#runBtn').click()
        page.wait_for_function("document.getElementById('runState').textContent.includes('已完成')",timeout=15000)
        page.locator('#evaluationInfo').get_by_text('质量评估',exact=False).wait_for(timeout=3000)
        page.locator('#replayRun').click()
        page.locator('#replayInfo').get_by_text('重放通过',exact=False).wait_for(timeout=10000)
        page.locator('#benchmarkAgent').click()
        page.locator('#benchmarkInfo').get_by_text('15/15',exact=False).wait_for(timeout=15000)
        assert not errors,errors
        output=ROOT/'docs'/'verification_v11'
        output.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(output/'enterprise-eval-replay-desktop.png'),full_page=True)
        phone=context.new_page()
        phone.set_viewport_size({'width':390,'height':844})
        phone.set_content(html,wait_until='domcontentloaded')
        phone.add_style_tag(content=(ROOT/'enterprise_web/styles.css').read_text(encoding='utf-8'))
        assert phone.locator('#loginUser').is_visible()
        phone.screenshot(path=str(output/'enterprise-login-mobile.png'))
        browser.close()
        print('PASS Chromium: login, run, evaluation, frozen replay, 15/15 benchmark, mobile, zero JS exceptions')
