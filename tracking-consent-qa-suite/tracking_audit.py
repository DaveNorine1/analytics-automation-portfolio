"""
tracking & consent qa suite
runs a headless browser through a site, records every network request,
and checks that analytics and ad tags respect the visitor's consent choice.

usage:
  python tracking_audit.py                      #runs against the bundled demo site
  python tracking_audit.py --base-url https://example.com --pages / /quiz
"""
import argparse, json, threading, functools, datetime, html, re
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
#tag families to watch. extend per client (meta, tiktok, linkedin, etc.)
TAGS = {
    "GA4 / Google tag": re.compile(r"(googletagmanager\.com|google-analytics\.com)"),
    "Ad pixels": re.compile(r"(doubleclick\.net|facebook\.com/tr|connect\.facebook\.net)"),
}
#consent manager selectors: demo site first, then common cmps (onetrust, cookiebot). override per client
BANNER = "#cb, #onetrust-banner-sdk, #CybotCookiebotDialog"
ACCEPT = "#accept, #onetrust-accept-btn-handler, #CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"
DECLINE = "#decline, #onetrust-reject-all-handler, #CybotCookiebotDialogBodyButtonDecline"
#stub for the google tag so the demo runs offline; real-site runs let requests through
GTAG_STUB = """
document.cookie='_ga=GA1.1.'+Math.floor(Math.random()*1e9)+'; path=/';
fetch('https://www.google-analytics.com/g/collect?v=2&tid=G-DEMO123&en=page_view&dl='+encodeURIComponent(location.href),{mode:'no-cors'});
"""

def serve_demo():
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=str(HERE / "demo_site"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"

class Session:
    """one browser context = one visitor. records requests by tag family."""
    def __init__(self, browser, offline):
        self.ctx = browser.new_context()
        self.requests = []
        self.ctx.on("request", lambda r: self.requests.append(r.url))
        if offline:
            self.ctx.route(re.compile(r"googletagmanager\.com/gtag/js.*"),
                           lambda route: route.fulfill(status=200, content_type="application/javascript", body=GTAG_STUB))
            self.ctx.route(re.compile(r"(google-analytics\.com|doubleclick\.net|facebook\.com)"),
                           lambda route: route.fulfill(status=204, body=""))
        self.page = self.ctx.new_page()
    def hits(self, family):
        return [u for u in self.requests if TAGS[family].search(u)]
    def cookies(self, prefix):
        return [c["name"] for c in self.ctx.cookies() if c["name"].startswith(prefix)]
    def close(self):
        self.ctx.close()

def result(check, status, detail, evidence=None):
    return {"check": check, "status": status, "detail": detail, "evidence": evidence or []}

def run(base, pages, offline):
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chrome, args=["--no-sandbox"]) if args.chrome else p.chromium.launch()

        #visitor 1: declines
        s = Session(browser, offline)
        s.page.goto(base + pages[0]); s.page.wait_for_timeout(400)
        shown = s.page.locator(BANNER).count() > 0
        out.append(result("Consent banner appears on first visit", "pass" if shown else "fail",
                          "Banner rendered before any choice was made." if shown else "No consent banner found."))
        pre = list(s.requests)
        ga_pre = [u for u in pre if TAGS["GA4 / Google tag"].search(u)]
        out.append(result("No analytics before a choice is made", "pass" if not ga_pre else "fail",
                          f"{len(ga_pre)} Google tag requests before the visitor chose.", ga_pre[:3]))
        if shown:
            s.page.locator(DECLINE).first.click(); s.page.wait_for_timeout(300)
        for path in pages[1:]:
            s.page.goto(base + path); s.page.wait_for_timeout(300)
        ga = s.hits("GA4 / Google tag"); ads = s.hits("Ad pixels"); gc = s.cookies("_ga")
        out.append(result("Decline blocks GA4", "pass" if not ga else "fail",
                          f"{len(ga)} Google tag requests after decline across {len(pages)} pages.", ga[:3]))
        out.append(result("Decline blocks ad pixels", "pass" if not ads else "fail",
                          f"{len(ads)} ad request(s) fired even though the visitor declined." if ads else "No ad requests after decline.",
                          [u.split("?")[0][:90] for u in ads[:3]]))
        out.append(result("No analytics cookies after decline", "pass" if not gc else "fail",
                          f"Found: {', '.join(gc)}" if gc else "No _ga cookies set."))
        s.page.goto(base + pages[0]); s.page.wait_for_timeout(300)
        again = s.page.locator(BANNER).first.is_visible() if s.page.locator(BANNER).count() else False
        out.append(result("Consent choice persists across pages", "fail" if again else "pass",
                          "Banner reappeared after the choice." if again else "Banner did not reappear."))
        s.close()

        #visitor 2: accepts
        s = Session(browser, offline)
        s.page.goto(base + pages[0]); s.page.wait_for_timeout(300)
        if s.page.locator(ACCEPT).count(): s.page.locator(ACCEPT).first.click()
        s.page.wait_for_timeout(500)
        collects = [u for u in s.hits("GA4 / Google tag") if "/g/collect" in u]
        pv = [parse_qs(urlparse(u).query).get("en", [""])[0] for u in collects]
        out.append(result("Accept loads GA4 and sends page_view", "pass" if "page_view" in pv else "fail",
                          f"{len(collects)} GA4 hits after accept; events: {', '.join(pv) or 'none'}.", collects[:2]))
        s.close()

        #visitor 3: quiz conversion + utm preservation
        if args.quiz:
            #capture datalayer pushes in sessionstorage so they survive the redirect
            s = Session(browser, offline)
            s.ctx.add_init_script("window.__pushes=[];window.dataLayer=window.dataLayer||[];const _p=window.dataLayer.push.bind(window.dataLayer);window.dataLayer.push=function(o){window.__pushes.push(o);sessionStorage.setItem('__dl',JSON.stringify(window.__pushes));return _p(o)};")
            s.page.goto(base + args.quiz + "?utm_source=newsletter&utm_campaign=fall_launch"); s.page.wait_for_timeout(300)
            if s.page.locator(ACCEPT).count(): s.page.locator(ACCEPT).first.click()
            s.page.select_option("#trip", "backpacking"); s.page.click("#submit")
            s.page.wait_for_url(re.compile(r".*thanks.*"), timeout=5000)
            pushes = json.loads(s.page.evaluate("sessionStorage.getItem('__dl')") or "[]")
            ev = next((x for x in pushes if x.get("event") == "quiz_submit"), None)
            need = ["quiz_path", "quiz_destination"]
            ok = ev is not None and all(ev.get(k) for k in need)
            out.append(result("Quiz submit pushes a complete dataLayer event", "pass" if ok else "fail",
                              f"quiz_submit with {', '.join(f'{k}={ev.get(k)}' for k in need)}." if ev else "No quiz_submit event found.",
                              [json.dumps(ev)] if ev else []))
            q = parse_qs(urlparse(s.page.url).query)
            kept = [k for k in ("utm_source", "utm_campaign") if k in q]
            out.append(result("UTM parameters survive the form redirect", "pass" if len(kept) == 2 else "fail",
                              f"Landing URL had utm_source and utm_campaign; confirmation URL kept {len(kept)} of 2.",
                              [s.page.url.replace(base, "")]))
            s.close()

        #link and cta crawl
        s = Session(browser, offline)
        broken, js_ctas, seen = [], [], set()
        for path in pages:
            s.page.goto(base + path); s.page.wait_for_timeout(200)
            for href in s.page.eval_on_selector_all("a[href]", "els=>els.map(e=>e.href)"):
                if href in seen or not href.startswith(base): continue
                seen.add(href)
                r = s.ctx.request.get(href)
                if r.status >= 400: broken.append(f"{r.status}  {href.replace(base, '')}  (linked from {path})")
            js_ctas += [f"{path}: '{t}'" for t in s.page.eval_on_selector_all(
                ".cta:not([href]), [role=button]:not(button):not([href])", "els=>els.map(e=>e.textContent.trim())")]
        out.append(result("Internal links resolve", "pass" if not broken else "fail",
                          f"{len(seen)} unique internal links checked, {len(broken)} broken.", broken))
        out.append(result("CTAs are real links or tracked buttons", "warn" if js_ctas else "pass",
                          f"{len(js_ctas)} CTA(s) work only through JavaScript click handlers. Crawlers and link checkers can't see them, so confirm each one fires a tracked event."
                          if js_ctas else "All CTAs are standard links.", js_ctas))
        s.close()
        browser.close()
    return out

def write_report(results, base):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    n = {k: sum(r["status"] == k for r in results) for k in ("pass", "fail", "warn")}
    Path(HERE / "reports").mkdir(exist_ok=True)
    (HERE / "reports/report.json").write_text(json.dumps({"site": base, "run_at": stamp, "summary": n, "results": results}, indent=2))
    rows = "".join(
        f"<tr class='{r['status']}'><td><span class='pill {r['status']}'>{r['status'].upper()}</span></td><td><b>{html.escape(r['check'])}</b><br><span class='d'>{html.escape(r['detail'])}</span>"
        + ("".join(f"<code>{html.escape(e)}</code>" for e in r["evidence"]) if r["evidence"] else "") + "</td></tr>" for r in results)
    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Tracking &amp; consent QA report</title><style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#f4f5f2;color:#15181d;margin:0;padding:32px 20px}}
.w{{max-width:920px;margin:0 auto}} h1{{font-size:24px;margin:0 0 4px}} .m{{color:#565c66;margin:0 0 20px}}
.sum{{display:flex;gap:12px;margin-bottom:20px}} .t{{background:#fff;border:1px solid #dfe2dc;border-radius:10px;padding:12px 18px;min-width:120px}}
.t b{{display:block;font-size:26px}} table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #dfe2dc;border-radius:10px;overflow:hidden}}
td{{padding:12px 14px;border-bottom:1px solid #eceee9;vertical-align:top;font-size:14px}} td:first-child{{width:84px}}
.d{{color:#454b55}} code{{display:block;margin-top:6px;font-size:12px;background:#f3f4f1;padding:4px 8px;border-radius:4px;word-break:break-all;color:#333}}
.pill{{font-size:11px;font-weight:700;padding:3px 9px;border-radius:99px}} .pill.pass{{background:#e2f3ea;color:#1d7a4c}}
.pill.fail{{background:#fbe7e4;color:#b3372e}} .pill.warn{{background:#fdf1d8;color:#8a5a00}}
</style></head><body><div class="w"><h1>Tracking &amp; consent QA report</h1><p class="m">{html.escape(base)} · run {stamp} · headless Chromium</p>
<div class="sum"><div class="t"><b style="color:#1d7a4c">{n['pass']}</b>passed</div><div class="t"><b style="color:#b3372e">{n['fail']}</b>failed</div><div class="t"><b style="color:#8a5a00">{n['warn']}</b>warnings</div></div>
<table>{rows}</table></div></body></html>"""
    (HERE / "reports/report.html").write_text(page)
    return n

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url"); ap.add_argument("--pages", nargs="+", default=["/index.html", "/about.html", "/returns.html"])
    ap.add_argument("--quiz", default="/quiz.html"); ap.add_argument("--chrome", help="path to a chrome binary (optional)")
    args = ap.parse_args()
    srv = None
    if args.base_url: base, offline = args.base_url.rstrip("/"), False
    else: srv, base = serve_demo(); offline = True
    res = run(base, args.pages, offline)
    n = write_report(res, "Demo site (bundled)" if srv else base)
    for r in res: print(f"[{r['status'].upper():4}] {r['check']}: {r['detail']}")
    print(f"\n{n['pass']} passed, {n['fail']} failed, {n['warn']} warnings -> reports/report.html")
    if srv: srv.shutdown()
