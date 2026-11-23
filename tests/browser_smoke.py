"""Exercise museum exploration offline at the actual project subpath."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, shutil, tempfile, threading
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

def main():
    screenshots=ROOT/'browser-checks'; screenshots.mkdir(exist_ok=True)
    fixture=json.loads((ROOT/'web/data/collection.json').read_text())
    expected=len(fixture['records'])
    with tempfile.TemporaryDirectory() as temp:
        shutil.copytree(ROOT/'dist',Path(temp)/'arttimeline')
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=temp))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':960})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.route('**/assets/tool-metrics.js',lambda route:route.fulfill(status=200,body=''))
                page.goto(f'http://127.0.0.1:{server.server_port}/arttimeline/')
                page.wait_for_function(f"document.querySelectorAll('.art-card').length === {expected}")
                assert f'{expected} works' in page.locator('#result-count').inner_text()
                page.locator('#filter-text').fill('cypresses')
                assert page.locator('.art-card').count()==1
                page.locator('.card-buttons button').first.click()
                assert page.locator('#detail').is_visible()
                assert 'Wheat Field with Cypresses' in page.locator('#detail-body').inner_text()
                page.locator('#close-detail').click()
                page.locator('.card-buttons button').nth(1).click()
                page.locator('#filter-text').fill('')
                page.locator('.card-buttons button').nth(3).click()
                assert page.locator('#compare-grid .compare-item').count()==2
                with page.expect_download() as download:
                    page.locator('#export-json').click()
                assert download.value.suggested_filename=='art-timeline-comparison.json'
                page.locator('#provider').select_option('aic')
                assert page.locator('.art-card').count()==sum(r['provider']=='aic' for r in fixture['records'])
                page.locator('#reset').click()
                # Arbitrary live query route proves no preset-only lookup; unsafe titles render as text.
                page.route('**/public/collection/v1.1/search?*',lambda route:route.fulfill(json={'total':1,'objectIDs':[999999]}))
                page.route('**/public/collection/v1/objects/999999',lambda route:route.fulfill(json={'objectID':999999,'title':'<img src=x onerror=alert(1)>','artistDisplayName':'Fixture artist','objectBeginDate':1801,'objectEndDate':1802,'isPublicDomain':False}))
                page.locator('#search-provider').select_option('met')
                page.locator('#query').fill('an arbitrary new subject')
                page.locator('#search-submit').click()
                page.wait_for_function("document.querySelector('#result-count').textContent === '1 works'")
                assert page.locator('.art-card h3').inner_text()=='<img src=x onerror=alert(1)>'
                assert page.locator('.art-card img').count()==0
                page.locator('#reset').click()
                page.route('**/api/v1/artworks/search?*',lambda route:route.abort())
                page.locator('#search-provider').select_option('aic')
                page.locator('#query').fill('ocean & sky')
                page.locator('#search-submit').click()
                page.wait_for_function("document.querySelector('#status').textContent.includes('Could not reach')")
                assert page.locator('.art-card').count()==expected
                assert page.locator('#status a').get_attribute('href')=='https://www.artic.edu/collection?q=ocean+%26+sky'
                page.locator('#reset').click()
                page.screenshot(path=str(screenshots/'desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(screenshots/'mobile.png'),full_page=True)
                assert not errors,errors
                browser.close()
        finally: server.shutdown()
    print('Browser checks passed: baseline, filters, details, comparison, export, arbitrary search, safe text and mobile layout')
if __name__=='__main__':main()
