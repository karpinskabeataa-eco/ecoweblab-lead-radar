#!/usr/bin/env python3
"""Public manufacturer prospect screening. Evidence, not purchase intent."""
import csv, html, ipaddress, json, os, re, socket, time
import urllib.parse as U
import urllib.request as R
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / 'output'
QUERIES = [
    'producent "produkujemy w Polsce" "o nas" -site:bankier.pl -site:money.pl',
    'producent "nasza fabryka" "w Polsce" -site:bankier.pl -site:wnp.pl',
    'producent własny zakład produkcyjny w Polsce',
    'manufacturer production plant Poland company',
    'producent obróbka CNC zakład Polska',
    'producent opakowań tworzyw Polska fabryka',
    'producent mebli Polska własna produkcja',
    'producent maszyny przemysłowe Polska',
    'producent nowa hala rozbudowa zakładu inwestycja Polska',
    'manufacturer Poland new production line expansion',
]
EXCLUDE = {'factories.pl','panoramafirm.pl','pkt.pl','aleo.com','oferteo.pl','europages.pl','europages.com',
           'kompass.com','firmy.net','biznesfinder.pl','facebook.com','linkedin.com','youtube.com',
           'bing.com','google.com','wikipedia.org','reddit.com','olx.pl','allegro.pl','pracuj.pl',
           'bankier.pl','money.pl','wnp.pl','pap.pl','businessinsider.com.pl','pulshr.pl',
           'forsal.pl','pb.pl','rp.pl','parkiet.com','portalspozywczy.pl'}
MANUFACTURING = r'produkuj\w*|producent\w*|produkcj\w*|wytwarz\w*|manufactur\w*|production|factory'
PLANT_POLAND = r'(?:zakład\w*|fabryk\w*|produkcj\w*|produkuj\w*|wytwarz\w*).{0,120}(?:w polsce|polsk\w*)|(?:polsk\w*).{0,80}(?:producent\w*|produkcj\w*|fabryk\w*)|(?:plant|factory|manufactur\w*|production).{0,100}(?:in poland|polish)|polish.{0,80}(?:manufacturer|factory|production)'
DIRECTORY = r'katalog (?:firm|producentów)|baza (?:firm|producentów)|lista producentów|directory of (?:companies|manufacturers)|business directory|dodaj (?:swoją )?firmę|add your company'
GROWTH = r'now\w* (?:hal\w*|lini\w* produkcyjn\w*|zakład\w*)|rozbudow\w* (?:zakład\w*|fabryk\w*|hal\w*)|zwiększ\w* moc\w* produkcyjn\w*|new (?:plant|factory|production line)|capacity expansion|factory expansion'
UA = 'EcoWebLabRadar/2.0 (public website screening; ecoweblab.com)'

# Evidence must describe the site's own business, on a company identity page.
# A news article mentioning a third-party factory is never such evidence.
IDENTITY_PATH = r'/(?:o[-_]nas|o-firmie|o-spolce|firma|about(?:-us)?|about/company|company|unternehmen|produkcja|production|manufacturing)(?:/|$|[?#])'
EDITORIAL = r'portal (?:finansowy|informacyjny|gospodarczy|branżowy)|serwis (?:informacyjny|finansowy)|redakcj[aię]|wydawc[ayą]|news portal|news publisher'
OWN_PRODUCTION = (
    r'\b(?:jesteśmy|jestesmy)\s+(?:(?:polskim|polską|polska|doświadczonym|czołowym|wiodącym|rodzinnym)\s+){0,3}(?:producentem|firmą produkcyjną|firma produkcyjna)\b'
    r'|\b(?:nasz[aeąy]|własna|własną|wlasna)\s+(?:produkcj\w*|fabryk\w*|zakład\w* produkcyjn\w*)'
    r'|\b(?:produkujemy|wytwarzamy)\b'
    r'|\bwe (?:are (?:a |an )?(?:(?:polish|leading|family-owned)\s+){0,2}manufacturer|manufacture|produce)\b'
    r'|\bour (?:own )?(?:factory|production (?:plant|facility|site))\b'
)
OWN_POLAND = (
    r'\b(?:produkujemy|wytwarzamy)\b[^.!?\n]{0,100}\bw Polsce\b'
    r'|\b(?:nasz[aeąy]|własna|własną|wlasna)\s+(?:produkcj\w*|fabryk\w*|zakład\w* produkcyjn\w*)[^.!?\n]{0,100}\b(?:w Polsce|na terenie Polski)\b'
    r'|\b(?:produkcj\w*|fabryk\w*|zakład\w* produkcyjn\w*)[^.!?\n]{0,70}\b(?:w Polsce|na terenie Polski)\b[^.!?\n]{0,50}\b(?:nasz\w*|włas\w*)\b'
    r'|\b(?:we (?:manufacture|produce)|our (?:own )?(?:factory|production (?:plant|facility|site)))[^.!?\n]{0,100}\bin Poland\b'
)

def identity_page(url):
    path=U.urlsplit(url).path.lower()
    return path in ('','/') or bool(re.search(IDENTITY_PATH,path,re.I))

def editorial_page(page):
    types=page.get('schema_types',[])
    if isinstance(types,str): types=[types]
    return any(str(x).rsplit('/',1)[-1] in ('NewsMediaOrganization','Newspaper') for x in types) or bool(re.search(EDITORIAL,page.get('title','')+' '+page.get('description','')+' '+page.get('text','')[:6000],re.I))

@lru_cache(maxsize=2048)
def public_host(host):
    try:
        ips = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return bool(ips) and all(ipaddress.ip_address(x[4][0]).is_global for x in ips)
    except (OSError, ValueError):
        return False

def safe_url(url):
    try:
        p = U.urlsplit(url)
        return p.scheme in ('https','http') and p.port in (None,80,443) and not p.username and not p.password and bool(p.hostname) and public_host(p.hostname)
    except ValueError:
        return False

def domain(url):
    return (U.urlsplit(url).hostname or '').lower().removeprefix('www.')

def blocked(host):
    return any(host == x or host.endswith('.'+x) for x in EXCLUDE)

def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', s))).strip()

def excerpt(pattern, text):
    m = re.search(pattern, text, re.I)
    return text[max(0,m.start()-60):m.end()+100] if m else ''

class SafeRedirect(R.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not safe_url(newurl):
            raise ValueError('Unsafe redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def discover(errors):
    found = {}
    opener = R.build_opener(SafeRedirect())
    for query in QUERIES:
        url = 'https://www.bing.com/search?' + U.urlencode({'format':'rss','q':query,'cc':'pl','setlang':'pl','mkt':'pl-PL'})
        try:
            with opener.open(R.Request(url, headers={'User-Agent':UA}), timeout=12) as r:
                data = r.read(1000001)
            if len(data)>1000000: raise ValueError('RSS too large')
            items = ET.fromstring(data).findall('.//item')[:20]
            for item in items:
                link = (item.findtext('link') or '').strip()
                host = domain(link)
                snippet = clean((item.findtext('title') or '')+' '+(item.findtext('description') or ''))
                if not host or blocked(host) or re.search(DIRECTORY,snippet,re.I): continue
                if re.search(r'/(?:wiadomosc|wiadomosci|artykul|articles|news)/',U.urlsplit(link).path,re.I): continue
                # Search snippets only nominate candidates; they never qualify a lead.
                if not re.search(MANUFACTURING,snippet,re.I): continue
                p=U.urlsplit(link)
                if p.scheme not in ('https','http'): continue
                found.setdefault(host, {'domain':host,'url':U.urlunsplit((p.scheme,p.netloc,'/','','')),'source':link})
        except Exception as ex:
            errors.append('Wyszukiwanie '+query+': '+type(ex).__name__)
    seed = ROOT/'seeds.csv'
    if seed.exists():
        with seed.open(encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                url=(r.get('url') or '').strip()
                if '://' not in url: url='https://'+url
                host=domain(url)
                if host and not blocked(host):
                    parsed=U.urlsplit(url)
                    found[host]={'domain':host,'url':U.urlunsplit((parsed.scheme,parsed.netloc,'/','','')),'source':url,'identity_url':url}
    if len(found)<3:
        errors.append('Małe pokrycie wyszukiwania: '+str(len(found))+' różnych domen. Brak wyników nie oznacza braku firm; uzupełnij seeds.csv zweryfikowanymi adresami.')
    return list(found.values())

DOM = """() => ({
 text:document.body?.innerText.slice(0,80000)||'', title:document.title,
 viewport:!!document.querySelector('meta[name="viewport"]'),
 description:document.querySelector('meta[name="description"]')?.content||'',
 schema_types:[...document.querySelectorAll('script[type="application/ld+json"]')].flatMap(x=>{
   try {const types=[]; const walk=o=>{if(!o||typeof o!=='object')return;if(o['@type'])types.push(...[o['@type']].flat());Object.values(o).forEach(v=>Array.isArray(v)?v.forEach(walk):walk(v));};walk(JSON.parse(x.textContent));return types;}catch{return [];}
 }),
 identity_text:(() => {const root=(document.querySelector('main')||document.body)?.cloneNode(true); if(!root)return '';root.querySelectorAll('[itemtype*="NewsArticle"],nav,header,footer,aside,script,style').forEach(x=>x.remove());if(location.pathname==='/')root.querySelectorAll('article').forEach(x=>x.remove());return root.textContent.slice(0,80000);})(),
 h1:[...document.querySelectorAll('h1')].map(x=>x.innerText).join(' '),
 links:[...document.querySelectorAll('a[href]')].map(x=>({url:x.href,label:x.innerText.slice(0,100)})),
 images:document.images.length,
 missingAlt:[...document.images].filter(x=>!x.hasAttribute('alt')).length,
 brokenImages:[...document.images].filter(x=>x.complete && !x.naturalWidth && x.currentSrc).length,
 legacy:document.querySelectorAll('frameset,frame,marquee,object[type="application/x-shockwave-flash"]').length,
 overflow:document.documentElement.scrollWidth>innerWidth+20,
 nav:performance.getEntriesByType('navigation')[0]?.toJSON()||{},
 resources:performance.getEntriesByType('resource').length
})"""

def classify(pages):
    if not pages:
        return False,'Brak stron do weryfikacji','',''
    home_host=domain(pages[0].get('url',''))
    if blocked(home_host):
        return False,'Portal, katalog lub platforma wykluczona z wyszukiwania','',''
    if any(editorial_page(p) for p in pages if identity_page(p.get('url',''))):
        return False,'Portal lub wydawca treści — wzmianka o cudzej fabryce nie potwierdza własnej produkcji','',''
    if any(re.search(DIRECTORY,p.get('title','')+' '+p.get('text','')[:4000],re.I) for p in pages):
        return False, 'Katalog lub agregator', '', ''
    manufacture=''
    for p in pages:
        if domain(p.get('url',''))!=home_host or not identity_page(p.get('url','')): continue
        # Runtime uses main content with article/navigation fragments removed.
        text=re.sub(r'\s+',' ',p.get('identity_text',p.get('text','')))
        text=' '.join(s for s in re.split(r'(?<=[.!?])\s+|\n+',text) if not re.search(r'\b(?:nie produkujemy|nie wytwarzamy|nie jesteśmy producentem|do not (?:produce|manufacture)|not a manufacturer)\b',s,re.I))
        manufacture=manufacture or excerpt(OWN_PRODUCTION,text)
        location=excerpt(OWN_POLAND,text)
        if location and re.search(OWN_PRODUCTION,text,re.I):
            return True,'Własna produkcja w Polsce — deklaracja na stronie firmowej, wymaga weryfikacji',excerpt(OWN_PRODUCTION,text),location
    return False,'Brak deklaracji własnej produkcji w Polsce na stronie głównej lub stronie o firmie; artykuły i domena .pl nie są dowodem',manufacture,''

def audit(browser, row):
    context=browser.new_context(viewport={'width':1365,'height':900},user_agent=UA,service_workers='block',accept_downloads=False)
    def route(req):
        if req.request.method not in ('GET','HEAD') or not safe_url(req.request.url): req.abort()
        else: req.continue_()
    context.route('**/*',route)
    page=context.new_page()
    page.set_default_timeout(5000)
    pages=[]; observations=[]; measurement_errors=[]; measured=[]
    def visit(url):
        if not safe_url(url): raise ValueError('Non-public URL')
        start=time.monotonic()
        response=page.goto(url,wait_until='load',timeout=20000)
        if response and response.status>=400: raise ValueError('HTTP '+str(response.status))
        data=page.evaluate(DOM)
        if re.search(r'verify you are human|checking your browser|access denied|just a moment', data['title']+' '+data['text'][:300],re.I):
            raise ValueError('Access challenge; no audit')
        data['url']=page.url; data['elapsed']=round(time.monotonic()-start,2)
        return data
    try:
        home=visit(row['url']); pages.append(home)
        # Read up to three relevant same-site pages for identity, offer and growth evidence.
        links=[]
        identity=row.get('identity_url')
        if identity and identity!=home['url'] and domain(identity)==domain(home['url']) and identity_page(identity): links.append(identity)
        for term in ('o nas|about|firma|company','produkt|oferta|products|offer','aktualno|news|inwest|rozwoj'):
            candidate=next((x['url'] for x in home['links'] if domain(x['url'])==domain(home['url']) and re.search(term,x['label']+' '+x['url'],re.I) and x['url'] not in links and x['url']!=home['url'] and not re.search(r'\.(pdf|zip|jpg|png)(?:\?|$)',x['url'],re.I)),None)
            if candidate: links.append(candidate)
        for link in links[:3]:
            try: pages.append(visit(link))
            except Exception as ex: measurement_errors.append(link+': '+str(ex).splitlines()[0][:100])
        qualified,reason,manufacture,location=classify(pages)
        row.update(qualification=reason,production_evidence=manufacture,poland_evidence=location,evidence_urls='; '.join(p['url'] for p in pages))
        if not qualified:
            row.update(status='odrzucony',findings=reason,opportunity_score=0)
            return row
        # Repeated homepage loads: actual browser, no throttling, US hosted runner.
        for viewport,label in [({'width':1365,'height':900},'desktop'),({'width':390,'height':844},'mobile')]:
            page.set_viewport_size(viewport)
            cdp=context.new_cdp_session(page)
            cdp.send('Network.enable'); cdp.send('Network.setCacheDisabled',{'cacheDisabled':True})
            transferred=[]; failures=[]; js=[]
            cdp.on('Network.loadingFinished',lambda event:transferred.append(event.get('encodedDataLength',0)))
            def bad_response(resp):
                if resp.status>=400 and domain(resp.url)==domain(home['url']): failures.append(resp.status)
            def page_error(error): js.append(type(error).__name__)
            page.on('response',bad_response); page.on('pageerror',page_error)
            try:
                d=visit(home['url']); n=d['nav']; load=round(n.get('loadEventEnd',0)/1000,2)
                item={'view':label,'load_seconds':load,'ttfb_seconds':round(n.get('responseStart',0)/1000,2),'transferred_bytes':sum(transferred),'http_errors':len(failures),'js_errors':len(js),'overflow':d['overflow'],'broken_images':d['brokenImages']}
                measured.append(item)
                page.screenshot(path=str(OUT/(row['domain']+'-'+label+'.png')),full_page=False,timeout=8000)
            except Exception as ex: measurement_errors.append(label+': '+str(ex).splitlines()[0][:100])
            finally:
                page.remove_listener('response',bad_response); page.remove_listener('pageerror',page_error); cdp.detach()
        def add(message,points): observations.append((message,points))
        if len(measured)==2 and all(x['load_seconds']>4 for x in measured): add('Ładowanie >4 s w obu próbach: '+str([x['load_seconds'] for x in measured]),25)
        if measured and max(x['transferred_bytes'] for x in measured)>3_000_000: add('Ciężka strona: transfer do '+str(round(max(x['transferred_bytes'] for x in measured)/1e6,2))+' MB',20)
        if any(x['view']=='mobile' and x['overflow'] for x in measured): add('Poziome przewijanie przy szerokości 390 px',20)
        if not home['viewport']: add('Brak ustawienia viewport dla urządzeń mobilnych',15)
        if any(x['http_errors'] for x in measured): add('Błędy HTTP zasobów własnej domeny: '+str([x['http_errors'] for x in measured]),15)
        if any(x['js_errors'] for x in measured): add('Wyjątki JavaScript: '+str([x['js_errors'] for x in measured])+' — wpływ wymaga oceny',5)
        if any(x['broken_images'] for x in measured): add('Niewczytane obrazy: '+str([x['broken_images'] for x in measured]),10)
        if home['legacy']: add('Przestarzałe elementy HTML (ramki/marquee/Flash)',15)
        alltext=' '.join(p['text'] for p in pages)
        if len(home['text'].split())<120: add('Mało tekstu na stronie głównej (<120 słów); sprawdź wyjaśnienie oferty',10)
        if not any(re.search('produkt|oferta|products|solutions',x['label'],re.I) for x in home['links']): add('Nie znaleziono wyraźnego odnośnika do produktów/oferty na stronie głównej',10)
        if not any(re.search('kontakt|contact|wycen|zapytan|quote',x['label'],re.I) for x in home['links']): add('Nie znaleziono wyraźnego odnośnika do kontaktu lub zapytania',10)
        if not home['title'] or not home['h1']: add('Brak title lub H1; czytelność głównego komunikatu do oceny',5)
        growth=[]
        for p in pages:
            e=excerpt(GROWTH,p['text'])
            if e: growth.append({'excerpt':e,'url':p['url'],'status':'Sygnał do sprawdzenia daty i skali; nie potwierdza intensywnego rozwoju'})
        score=min(100,sum(points for _,points in observations))
        row.update(status='kandydat' if score>=20 else 'bez silnego sygnału',opportunity_score=score,findings='; '.join(x for x,_ in observations) or 'Brak silnych sygnałów w ograniczonym badaniu',measurements=measured,growth_signals=growth,measurement_errors=measurement_errors,design_review='Ocena estetyki i jasności oferty wymaga analizy zrzutów oraz treści; nie oceniono wieku projektu')
        return row
    finally: context.close()

def cell(value):
    return str(value).replace('|','/').replace('\n',' ')[:1200]

def write_excel(path, results, stamp, errors, discovered):
    """Small dependency-free XLSX. Raw strings are text, never formulas."""
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    fields=['domain','url','status','opportunity_score','findings','qualification','production_evidence','poland_evidence','evidence_urls','source']
    headers=['Domena','Strona','Status','Sygnał problemów (0–100)','Zaobserwowane problemy','Kwalifikacja','Deklaracja produkcji','Deklaracja produkcji w Polsce','Sprawdzone strony','Źródło kandydata']
    candidates=[r for r in results if r['status']=='kandydat']
    rejected=[r for r in results if r['status']!='kandydat']
    sheets=[('Kandydaci',[headers]+[[r.get(k,'') for k in fields] for r in candidates]),
            ('Pozostałe domeny',[headers]+[[r.get(k,'') for k in fields] for r in rejected]),
            ('Przebieg',[['Pole','Wartość'],['Data pomiaru UTC',stamp],['Znalezione domeny',discovered],['Sprawdzone domeny',len(results)],['Kandydaci',len(candidates)],['Ograniczenie','Kandydat nie oznacza zainteresowania zakupem. Ocena wizualna i dowody wymagają weryfikacji.'],['Pomiary','Chromium desktop/mobile, runner USA, bez symulacji CPU i łącza; nie terenowe Core Web Vitals.'],['Źródła','RSS Bing i jawna lista seeds.csv; lista startowa nie jest automatycznie listą leadów.']]+[['Problem źródła',e] for e in errors])]
    def xml(tag,attrs=None): return ET.Element(tag,attrs or {})
    def col(n):
        out=''
        while n: n,r=divmod(n-1,26);out=chr(65+r)+out
        return out
    def encoded(root): return ET.tostring(root,encoding='utf-8',xml_declaration=True)
    types=xml('Types',{'xmlns':'http://schemas.openxmlformats.org/package/2006/content-types'})
    for ext,mime in [('rels','application/vnd.openxmlformats-package.relationships+xml'),('xml','application/xml')]: ET.SubElement(types,'Default',Extension=ext,ContentType=mime)
    ET.SubElement(types,'Override',PartName='/xl/workbook.xml',ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml')
    book=xml('workbook',{'xmlns':ns,'xmlns:r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'})
    listed=ET.SubElement(book,'sheets')
    rels=xml('Relationships',{'xmlns':'http://schemas.openxmlformats.org/package/2006/relationships'})
    rootrels=xml('Relationships',{'xmlns':'http://schemas.openxmlformats.org/package/2006/relationships'})
    ET.SubElement(rootrels,'Relationship',Id='rId1',Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',Target='xl/workbook.xml')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for i,(name,rows) in enumerate(sheets,1):
            ET.SubElement(types,'Override',PartName=f'/xl/worksheets/sheet{i}.xml',ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
            ET.SubElement(listed,'sheet',name=name,sheetId=str(i),attrib={'r:id':f'rId{i}'})
            ET.SubElement(rels,'Relationship',Id=f'rId{i}',Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet',Target=f'worksheets/sheet{i}.xml')
            sheet=xml('worksheet',{'xmlns':ns})
            views=ET.SubElement(sheet,'sheetViews');view=ET.SubElement(views,'sheetView',workbookViewId='0')
            ET.SubElement(view,'pane',ySplit='1',topLeftCell='A2',activePane='bottomLeft',state='frozen')
            cols=ET.SubElement(sheet,'cols')
            for j in range(1,len(rows[0])+1): ET.SubElement(cols,'col',min=str(j),max=str(j),width=str(30 if j<5 else 65),customWidth='1')
            data=ET.SubElement(sheet,'sheetData')
            for rownum,values in enumerate(rows,1):
                row=ET.SubElement(data,'row',r=str(rownum))
                for j,value in enumerate(values,1):
                    address=f'{col(j)}{rownum}'
                    if isinstance(value,(int,float)):
                        c=ET.SubElement(row,'c',r=address);ET.SubElement(c,'v').text=str(value)
                    else:
                        c=ET.SubElement(row,'c',r=address,t='inlineStr')
                        clean_value=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value))[:32767]
                        ET.SubElement(ET.SubElement(c,'is'),'t').text=clean_value
            if len(rows)>1: ET.SubElement(sheet,'autoFilter',ref=f'A1:{col(len(rows[0]))}{len(rows)}')
            z.writestr(f'xl/worksheets/sheet{i}.xml',encoded(sheet))
        z.writestr('[Content_Types].xml',encoded(types));z.writestr('_rels/.rels',encoded(rootrels))
        z.writestr('xl/workbook.xml',encoded(book));z.writestr('xl/_rels/workbook.xml.rels',encoded(rels))

def main():
    OUT.mkdir(exist_ok=True)
    errors=[]; results=[]
    candidates=discover(errors)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for row in candidates[:min(int(os.getenv('MAX_AUDITS','12')),25)]:
            try: results.append(audit(browser,row))
            except Exception as ex:
                results.append(dict(row,status='niezweryfikowany',opportunity_score=0,findings=type(ex).__name__+': '+str(ex).splitlines()[0][:180]))
            time.sleep(0.3)
        browser.close()
    results.sort(key=lambda r:r['opportunity_score'],reverse=True)
    leads=[r for r in results if r['status']=='kandydat']
    stamp=datetime.now(timezone.utc).isoformat()
    write_excel(OUT/'leady.xlsx',results,stamp,errors,len(candidates))
    (OUT/'wyniki.json').write_text(json.dumps({'checked_at':stamp,'discovered':len(candidates),'results':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    fields=['domain','url','status','opportunity_score','findings','production_evidence','poland_evidence','evidence_urls','source']
    with (OUT/'leady.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for r in leads:
            writer.writerow({k:("'"+str(v) if str(v).startswith(('=','+','-','@')) else v) for k,v in r.items()})
    report=['# EcoWebLab — producenci w Polsce', '', 'Data UTC: '+stamp,
            f'Znalezionych kandydatów: {len(candidates)}; sprawdzonych: {len(results)}; z potwierdzeniem tekstowym produkcji w Polsce i sygnałem problemów: {len(leads)}.',
            'Domena nie określa kraju produkcji. Katalogi i niezweryfikowane firmy nie są leadami. To kandydaci, nie potwierdzony zamiar zakupu.',
            'Pomiar Chromium: dwa zimne wczytania (desktop/mobile), bez symulacji wolnego łącza, runner GitHub w USA. Nie są to dane terenowe Core Web Vitals. Brak informacji oznacza brak na sprawdzonych podstronach, nie dowód jej braku w całej witrynie.', '',
            '| Firma | Wynik | Dowody problemów |','|---|---:|---|']
    for r in leads:
        report.append(f"| [{r['domain']}]({r['url']}) | {r['opportunity_score']} | {cell(r['findings'])} |")
        report += ['', 'Dowód produkcji w Polsce: '+cell(r['poland_evidence']), 'Źródła: '+r['evidence_urls'], 'Sygnały rozwoju (niepotwierdzone daty/skala): '+cell(json.dumps(r.get('growth_signals',[]),ensure_ascii=False)), 'Pomiary: '+json.dumps(r.get('measurements',[]),ensure_ascii=False), 'Ograniczenia pomiaru: '+cell(r.get('measurement_errors',[])), '']
    report+=['','## Pozostałe sprawdzone domeny (nie leady)']
    report += ['- '+r['domain']+' — '+r['status']+': '+cell(r['findings']) for r in results if r['status']!='kandydat']
    report+=['','## Problemy źródła']+errors
    report+=['','Excel leady.xlsx zawiera kandydatów, odrzucenia i stan przebiegu. CSV zawiera tylko kandydatów.',
             'Zrzuty desktop/mobile oraz wyniki.json w artefaktach służą do oceny projektu i treści. Sam kod HTML nie potwierdza, że strona jest stara lub źle zaprojektowana.']
    text='\n'.join(report)+'\n'
    (OUT/'raport.md').write_text(text,encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'): Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(text,encoding='utf-8')
    print(f'Discovered: {len(candidates)}, checked: {len(results)}, candidates: {len(leads)}, search errors: {len(errors)}')

if __name__=='__main__': main()
