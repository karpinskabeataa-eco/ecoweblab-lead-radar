#!/usr/bin/env python3
"""EcoWebLab Radar: conservative screening of public B2B websites, without paid API."""
import csv, ipaddress, os, socket, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / 'output'
OUT.mkdir(exist_ok=True)
QUERIES = [
    ('Producenci', 'site:.pl producent maszyn przemysłowych'),
    ('CNC', 'site:.pl obróbka CNC producent'),
    ('Dystrybutorzy', 'site:.pl dystrybutor automatyki przemysłowej'),
    ('Techniczne B2B', 'site:.pl producent elementów metalowych'),
    ('Architekci', 'site:.pl pracownia architektoniczna projekty'),
]
EXCLUDE = {'bing.com', 'google.com', 'google.pl', 'youtube.com', 'linkedin.com', 'facebook.com', 'instagram.com', 'wikipedia.org', 'panoramafirm.pl', 'pkt.pl', 'aleo.com', 'oferteo.pl', 'olx.pl', 'pracuj.pl', 'gov.pl', 'news.google.com', 'wp.pl', 'onet.pl', 'interia.pl', 'money.pl', 'forbes.pl', 'bankier.pl', 'europa.eu', 'tiktok.com'}
CATEGORY_TERMS = {
    'Producenci': ('maszyn', 'produkcj'),
    'CNC': ('cnc', 'obróbk', 'obrobk'),
    'Dystrybutorzy': ('automatyk', 'dystrybu'),
    'Techniczne B2B': ('metalow', 'metalurg'),
    'Architekci': ('architekt',),
}

def relevant_result(domain, category, title, description):
    snippet = (title + ' ' + description).casefold()
    return domain.endswith('.pl') and any(term in snippet for term in CATEGORY_TERMS[category])

UA = 'EcoWebLabRadar/1.0 (public homepage quality screening; ecoweblab.com)'

class Signals(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''; self.in_title = False; self.description = False
        self.viewport = False; self.h1 = 0; self.images = 0; self.no_alt = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag == 'h1': self.h1 += 1
        if tag == 'img':
            self.images += 1
            if not a.get('alt', '').strip(): self.no_alt += 1
        if tag == 'meta':
            if a.get('name', '').lower() == 'description' and a.get('content'): self.description = True
            if a.get('name', '').lower() == 'viewport': self.viewport = True
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
    def handle_data(self, data):
        if self.in_title: self.title += data

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def public_url(url):
    p = urllib.parse.urlparse(url)
    if p.scheme != 'https' or not p.hostname or p.port not in (None, 443):
        raise ValueError('Public HTTPS homepage only')
    host = p.hostname.lower().rstrip('.')
    if host in EXCLUDE or any(host.endswith('.' + blocked) for blocked in EXCLUDE):
        raise ValueError('Directory or social domain')
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(record[4][0]).is_global for record in addresses):
        raise ValueError('Private or non-public host')
    return host.removeprefix('www.')

def download(url, limit=350000):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=10) as response:
        body = response.read(limit + 1)
        if len(body) > limit: raise ValueError('Response too large')
        return body, response.headers

def discover():
    found = {}; errors = []
    for category, query in QUERIES:
        rss = 'https://www.bing.com/search?format=rss&cc=pl&setlang=pl&mkt=pl-PL&q=' + urllib.parse.quote(query)
        try:
            xml, _ = download(rss, 1000000)
            accepted = 0
            for item in ET.fromstring(xml).findall('.//item')[:20]:
                original = (item.findtext('link') or '').strip()
                try: domain = public_url(original)
                except Exception: continue
                if not relevant_result(domain, category, item.findtext('title') or '', item.findtext('description') or ''):
                    continue
                accepted += 1
                if domain not in found:
                    found[domain] = {'domain':domain, 'url':'https://'+urllib.parse.urlparse(original).hostname+'/', 'category':category, 'source':original}
            if not accepted:
                errors.append(category + ': brak wyników spełniających filtr polskiej domeny i branży; nie dodano przypadkowych stron')
        except Exception as ex:
            errors.append(category + ': ' + str(ex)[:140])
    return list(found.values()), errors

def audit(row):
    start = time.monotonic()
    body, headers = download(row['url'])
    if 'text/html' not in headers.get('Content-Type', '').lower():
        raise ValueError('Not HTML')
    parser = Signals(); parser.feed(body.decode('utf-8', 'replace'))
    elapsed = round(time.monotonic() - start, 2)
    issues = []; points = 0
    def add(label, value, evidence):
        nonlocal points
        points += value
        issues.append(f'{label}: {evidence}')
    if not parser.viewport: add('Brak viewport',15,'HTML strony głównej')
    if not parser.title.strip(): add('Brak title',15,'HTML strony głównej')
    if not parser.description: add('Brak meta description',8,'HTML strony głównej')
    if not parser.h1: add('Brak H1',8,'HTML strony głównej')
    if parser.images>=3 and parser.no_alt/parser.images>0.5:
        add('Ponad połowa zdjęć bez alt',8,f'{parser.no_alt} / {parser.images}')
    if elapsed>4: add('Wolna odpowiedź — jeden pomiar',10,f'{elapsed} s')
    if len(body)>300000: add('Duży dokument HTML',6,f'{len(body)} B bez zasobów')
    if not headers.get('Content-Security-Policy'):
        issues.append('Brak CSP (informacyjnie; to nie jest dowód podatności)')
    row.update({'title':parser.title.strip()[:150], 'opportunity_score':min(100,points),
                'quality_score':max(0,100-points), 'seconds':elapsed,
                'findings':'; '.join(issues), 'checked_at':datetime.now(timezone.utc).isoformat(),
                'qualification':'Wstępny screening — wymagana ręczna weryfikacja'})
    return row

def main():
    found, errors = discover()
    # Optional, manually curated public company URLs.
    seed_file = ROOT / 'seeds.csv'
    if seed_file.exists():
        existing = {r['domain'] for r in found}
        with seed_file.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                value = (row.get('url') or row.get('website') or '').strip()
                if not value: continue
                if '://' not in value: value = 'https://' + value
                try: domain = public_url(value)
                except Exception: continue
                if domain not in existing:
                    found.append({'domain':domain, 'url':'https://'+urllib.parse.urlparse(value).hostname+'/',
                                  'category':row.get('industry', 'B2B'), 'source':'seeds.csv'})
                    existing.add(domain)
    results=[]
    for row in found[:max(1,min(int(os.getenv('MAX_AUDITS','25')),60))]:
        try: results.append(audit(row))
        except Exception as ex: errors.append(row['domain'] + ': ' + str(ex)[:140])
        time.sleep(0.5)
    results.sort(key=lambda r:r['opportunity_score'], reverse=True)
    fields=['domain','url','category','title','opportunity_score','quality_score','seconds','findings','source','checked_at','qualification']
    with (OUT / 'leady.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(results)
    report=[
        '# EcoWebLab — raport okazji technicznych', '',
        'Data (UTC): '+datetime.now(timezone.utc).isoformat(),
        f'Znalezione domeny: {len(found)}. Przeanalizowane: {len(results)}.', '',
        '**Uwaga:** to potencjalne okazje, nie potwierdzone leady zakupowe. Screening nie stanowi pełnego audytu bezpieczeństwa ani Lighthouse.', '',
        '| Domena | Branża | Sygnał 0–100 | Zaobserwowane problemy |',
        '|---|---|---:|---|'
    ]
    for row in results[:25]:
        observations=(row['findings'] or 'Brak podstawowych problemów w screeningu').replace('|','/')[:200]
        report.append(f"| [{row['domain']}]({row['url']}) | {row['category']} | {row['opportunity_score']} | {observations} |")
    if errors:
        report += ['', '## Problemy podczas skanowania'] + ['- '+str(e) for e in errors[:30]]
    text='\n'.join(report)+'\n'
    (OUT/'raport.md').write_text(text,encoding='utf-8')
    summary=os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as f: f.write(text)
    print(f'Discovered: {len(found)}, screened: {len(results)}, errors: {len(errors)}')

if __name__=='__main__': main()
