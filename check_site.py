#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
矢作SCサイト 納品前チェック（コーチ写真の取り違え・消えた機能などを、毎回、機械的に確認する）

使い方（HTMLのあるフォルダで）:
  python3 check_site.py index.html ryusei-event.html          # 文字だけのチェック（すぐ終わる）
  python3 check_site.py index.html ryusei-event.html --github # 画像・ファイルがGitHubに実在するかも確認
  python3 check_site.py index.html ryusei-event.html --browser # ブラウザでの動作チェックも（Playwrightが必要）
"""
import re, sys, subprocess, urllib.request

CORRECT = {  # コーチ写真の正しい対応（絶対に変えない）
 'coach_kouno.jpg':'河野 浩二','coach_kusaka.jpg':'日下 研一','coach_hayasaka.jpg':'早坂 浩明',
 'coach_morohoshi.jpg':'諸星 達也','coach_kashiwagi_t.jpg':'柏木 誉史','coach_seto.jpg':'瀬戸 俊明',
 'coach_takahashi.jpg':'高橋 富康','coach_shimoda.jpg':'下田 翔也','coach_isozaki.jpg':'磯﨑 幸二',
 'coach_ueda.jpg':'植田 健','coach_kinoe.jpg':'甲 淳一','coach_tokunaga.jpg':'徳永 哲和',
 'coach_kashiwagi_tomo.jpg':'柏木 知之'}
RAW='https://raw.githubusercontent.com/shunsuke5468/yahagi-sc/main/'
NG=[]
def chk(label, ok, extra=''):
    print('  %s %s %s' % ('✔' if ok else '✘', label, extra))
    if not ok: NG.append(label)

def static_checks(path):
    w=open(path,encoding='utf-8').read(); is_index = path.endswith('index.html')
    print('■', path, '(%d bytes)' % len(w.encode()))
    tags=['div','section','button','ol','ul','dl','svg','script','picture','figure','style','noscript','a','p','h1','h2','h3','header','footer','main']
    bad=[t for t in tags if len(re.findall(r'<%s[\s>]'%t,w))!=w.count('</%s>'%t)]
    chk('タグの開き・閉じが合っている', not bad, str(bad) if bad else '')
    chk('<script>が連続していない', w.count('<script>\n<script>')==0)
    chk('noindex（サンプル用の指定）が残っていない', 'noindex' not in w)
    chk('GA4(G-R1KP9SBKM1)・LINEリンク(lin.ee/nX8Ezjx5)がある', 'G-R1KP9SBKM1' in w and 'lin.ee/nX8Ezjx5' in w)
    if is_index:
        pairs=re.findall(r'src="images/(coach_[^"]+)"\s+alt="([^"]+)"', w)
        ng=[f'{f}→{a}' for f,a in pairs if CORRECT.get(f)!=a]
        chk('コーチ写真13名の src と alt が、正しい対応表どおり', not ng and len(pairs)==13, ('不一致: %s' % ng) if ng else '（13/13）')
        chk('コーチカードが19枚', len(re.findall(r'<div class="coach-card"',w))==19)
        chk('湘南の猛進ロゴ（shonan_mousin・id=shonanLogo）が残っている', 'shonan_mousin' in w and 'id="shonanLogo"' in w)
        m=re.search(r'\.float-cta\{[^}]*\}',w)
        chk('追従ボタン(.float-cta)が position:fixed', bool(m) and 'position:fixed' in m.group())
        chk('団員数「70名」が3か所（更新時は全部そろえる）', w.count('70名')==3, '（今: %d か所）' % w.count('70名'))
        ids=set(re.findall(r'\bid="([^"]+)"',w))
        anchors=set(re.findall(r'href="#([^"]+)"',w)); missing=sorted(a for a in anchors if a not in ids)
        chk('ページ内リンク(#...)の飛び先がすべてある', not missing, str(missing) if missing else '')
        first_close=w.index('</style>'); chk('メインのstyleより前に <noscript> が無い（CSSは最初の</style>の前に足す）', w.find('<noscript><style>')==-1 or w.index('<noscript><style>')>first_close)
        chk('講演会は別ページ(ryusei-event.html)へのリンクがある', 'href="ryusei-event.html"' in w)
    else:
        chk('見出し(h1)が1つ', w.count('<h1')==1)
        chk('写真8枚＋拡大表示の部品がある', w.count('event-gallery')>=1 and 'lightboxOverlay' in w)
    n=len(re.findall(r'drop-shadow',w)); print('  ・参考: filter:drop-shadow が %d か所（動く要素に使うとiPhoneで四角い板が出ることがある。増やさない）' % n)
    return w

def github_checks(path,w):
    refs=set(re.findall(r'(?:src|href|srcset)="((?:images/[^"#?]+)|apple-touch-icon\.png)"',w))
    refs|=set(re.findall(r"url\(['\"]?(images/[^'\")]+)",w))      # CSSの中で指定している画像も確認
    refs=sorted(refs); print('  GitHubに実在するか（%d件）:' % len(refs)); ng=[]; warn=[]
    def code(r):
        try: return urllib.request.urlopen(urllib.request.Request(RAW+r,method='HEAD'),timeout=15).status
        except Exception as e: return getattr(e,'code',0)
    for r in refs:
        if code(r)==200: continue
        stem,ext=r.rsplit('.',1)
        if ext.lower() in ('jpg','jpeg','png') and code(stem+'.webp')==200: warn.append(r)   # WebPがあれば、予備の画像が無くても問題なし
        else: ng.append(r)
    chk('すべて存在する', not ng, ('未アップロードの疑い: %s' % ng) if ng else '')
    if warn: print('  ・注意: 予備のJPG/PNGが無い（WebPはある＝問題なし）: %s' % warn)

def browser_checks(paths):
    from playwright.sync_api import sync_playwright
    import os
    with sync_playwright() as p:
        b=p.chromium.launch()
        for path in paths:
            print('■ ブラウザ確認:', path); url='file://'+os.path.abspath(path)
            for W,H,mob in [(390,844,True),(768,1024,False),(1440,900,False)]:
                ctx=b.new_context(viewport={'width':W,'height':H},is_mobile=mob,has_touch=mob); pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
                pg.goto(url); pg.evaluate("localStorage.setItem('yahagiHeroMovieSeen',String(Date.now()))"); pg.reload(); pg.wait_for_timeout(5000)
                chk('%dpx: 横にはみ出さない・JSエラーなし' % W, pg.evaluate("document.documentElement.scrollWidth")<=W and not errs, str(errs) if errs else '')
                if path.endswith('index.html') and W==1440:
                    for wid,pre,keys in [('safetyTabs','bc-s-tab-',['heat','body','aed','food','community','promise']),('coachTabs','bc-c-tab-',['staff','u8','u10','u12']),('courseTabs','bc-k-tab-',['kids','u8','u10','u12'])]:
                        pg.evaluate("document.getElementById('%s').scrollIntoView({block:'center'})"%wid); pg.wait_for_timeout(400); ok=True
                        for k in keys:
                            pg.click('#'+pre+k); pg.wait_for_timeout(300)
                            ok&=pg.evaluate("document.querySelector('#%s%s').classList.contains('active')"%(pre,k))
                        chk('タブ切替 %s' % wid, ok)
                if path.endswith('ryusei-event.html') and W==1440:
                    pg.evaluate("document.querySelector('.event-gallery').scrollIntoView({block:'center'})"); pg.wait_for_timeout(400)
                    pg.click('.event-gallery figure:nth-child(2)'); pg.wait_for_timeout(500)
                    chk('写真の拡大表示（2/8）', pg.evaluate("document.getElementById('lightboxCount').textContent")=='2 / 8')
                ctx.close()
        b.close()

if __name__=='__main__':
    args=[a for a in sys.argv[1:] if not a.startswith('--')]; flags=[a for a in sys.argv[1:] if a.startswith('--')]
    if not args: print(__doc__); sys.exit(1)
    for a in args:
        w=static_checks(a)
        if '--github' in flags: github_checks(a,w)
    if '--browser' in flags: browser_checks(args)
    print('\n結果:', '全項目OK' if not NG else '★未達 %d 件: %s' % (len(NG),NG)); sys.exit(1 if NG else 0)
