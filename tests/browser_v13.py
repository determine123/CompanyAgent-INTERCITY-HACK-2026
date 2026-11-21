"""Chromium UI regression through the real in-process FastAPI backend.

No external host access or secrets required. Browser loopback HTTP is blocked in
this environment; the bridge forwards fetch calls to FastAPI TestClient.
"""
from __future__ import annotations
import os,tempfile,sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='companyagent-v13-browser-') as runtime:
    os.environ['COMPANYAGENT_RUNTIME_DIR']=runtime
    os.environ['COMPANYAGENT_ADMIN_PASSWORD']='Chromium-verified-test-password-ONLY'
    os.environ['COMPANYAGENT_AUTO_SYNC']='false'
    os.environ.pop('B1X_API_KEY',None)
    from fastapi.testclient import TestClient
    from server import app
    with TestClient(app) as client, sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1400,'height':900})
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        def backend_request(url, method, body, headers):
            resp=client.request(method,url,content=body,headers=headers)
            try: data=resp.json()
            except Exception: data={'detail':resp.text}
            return {'status':resp.status_code,'body':data}
        page.expose_function('__backendRequest',backend_request)
        html=(ROOT/'enterprise_web/index.html').read_text(encoding='utf-8')
        html=html.replace('<link rel="stylesheet" href="/enterprise/styles.css">','').replace('<script src="/enterprise/app.js"></script>','')
        page.set_content(html,wait_until='domcontentloaded')
        page.add_style_tag(content=(ROOT/'enterprise_web/styles.css').read_text(encoding='utf-8'))
        page.evaluate("""() => { window.fetch = async (url, init={}) => {
           const r=await window.__backendRequest(url, init.method||'GET', init.body||null, init.headers||{});
           return new Response(JSON.stringify(r.body),{status:r.status,headers:{'Content-Type':'application/json'}});
        };} """)
        page.add_script_tag(content=(ROOT/'enterprise_web/app.js').read_text(encoding='utf-8'))
        page.locator('#loginUser').fill('admin')
        page.locator('#loginPassword').fill('Chromium-verified-test-password-ONLY')
        page.locator('#loginForm button[type=submit]').click()
        page.locator('#loginCover').wait_for(state='hidden',timeout=10000)
        page.locator('button.nav[data-page=client]').click()
        assert page.locator('#page-client').is_visible()
        page.locator('#clientBrand').fill('合成测试品牌')
        page.locator('#clientBudget').select_option('200')
        page.locator('#clientCoverage').uncheck() # synthetic coverage evidence may be absent
        page.locator('#clientGenerate').click()
        page.locator('#clientProposal:not(.hidden)').wait_for(timeout=10000)
        assert '合成测试品牌' in page.locator('#clientTitle').inner_text()
        assert '/ 200 万' in page.locator('#clientSpent').inner_text()
        assert page.locator('#clientRunState').inner_text().startswith('Run #')
        runid=int(page.locator('#clientRunState').inner_text().split('#')[1].split()[0])
        output=ROOT/'docs'/'verification_v13'
        output.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(output/'client-proposal-desktop.png'),full_page=True)
        page.locator('#changeType').select_option('vehicle_reassignment')
        page.locator('#changeNote').fill('车辆进保需替代车线，重新安排制作单、施工队并通知客户')
        page.locator('#changeAnalyze').click()
        page.locator('#changeResult:not(.hidden)').wait_for(timeout=10000)
        assert '车线绑定' in page.locator('#changeAffected').inner_text()
        assert '施工计划' in page.locator('#changeAffected').inner_text()
        assert page.locator('#changeSteps .change-step').count()==6
        assert '待人工确认' in page.locator('#changeSteps').inner_text()
        assert '不构成正式变更承诺' in page.locator('#changeNotice').inner_text()
        page.screenshot(path=str(output/'client-change-impact-desktop.png'),full_page=True)
        # Verify the same persisted run exposes a server-generated standalone HTML.
        download=client.get(f'/enterprise/api/runs/{runid}/proposal.html')
        assert download.status_code==200,download.text[:200]
        assert '<html' in download.text.lower() and '合成测试品牌' in download.text
        page.locator('#clientBudget').select_option('100')
        page.locator('#clientGenerate').click()
        page.wait_for_function("document.getElementById('clientSpent').textContent.includes('/ 100 万')",timeout=10000)
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(output/'client-proposal-mobile.png'),full_page=True)
        assert page.locator('#clientGenerate').is_visible()
        assert not errors,errors
        browser.close()
        print('PASS Chromium: client brief, 200→100 budget execution, 6-step change impact, HTML endpoint, mobile, zero JS errors')
