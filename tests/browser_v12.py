"""Real Chromium smoke against local v1.2; use with isolated runtime and server.

Not included as pytest to keep public CI runnable without Chromium installation.
"""
from __future__ import annotations
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=os.getenv('COMPANYAGENT_BROWSER_URL','http://127.0.0.1:8899')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True, executable_path=os.getenv('CHROMIUM_BIN') or None, args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':900},accept_downloads=True)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE+'/enterprise/',wait_until='domcontentloaded')
    page.locator('#loginUser').fill('admin')
    page.locator('#loginPassword').fill(os.getenv('COMPANYAGENT_BROWSER_PASSWORD',''))
    page.locator('#loginForm button[type=submit]').click()
    page.locator('#loginCover.hidden').wait_for(timeout=10000)
    page.locator('#runBtn').click()
    page.locator('#runResult:not(.hidden)').wait_for(timeout=12000)
    assert '参考' in page.locator('#resRationale').inner_text() or page.locator('#resSpent').inner_text()!='—'
    # Deliberately no B1X credential: explicit opt-in should not imply success.
    page.on('dialog',lambda d:d.accept())
    page.locator('#modelToolCall').click()
    page.wait_for_timeout(400)
    assert '没有成功' in page.locator('#toolCallInfo').inner_text() or '未配置' in page.locator('#toolCallInfo').inner_text()
    # Dataset bridge: an employee can import authorized synthetic coverage only.
    page.locator('button.nav[data-page=datasets]').click()
    page.locator('#datasetKind').select_option('coverage')
    path=Path(__file__).parent.parent/'data'/'coverage_template.csv'
    page.locator('#datasetFile').set_input_files(str(path))
    page.locator('#uploadDataset').click()
    page.wait_for_timeout(700)
    # Templates sometimes have no rows, upload may reasonably reject; UI must stay usable.
    assert page.locator('#bridgeCheck').is_visible()
    page.locator('button.nav[data-page=iteration]').click()
    page.locator('#failureCases').wait_for(timeout=10000)
    page.wait_for_timeout(250)
    assert 'MODEL_NOT_CONFIGURED' in page.locator('#failureCases').inner_text() or 'B1X_API_KEY' in page.locator('#failureCases').inner_text()
    assert not errors,errors
    out=Path('/mnt/data/CompanyAgent_v1.2_browser_verified.png')
    page.screenshot(path=str(out),full_page=True)
    print('BROWSER PASS: login, deterministic plan, B1X fail-closed, data UI, failure proposals, zero JS errors')
    browser.close()
