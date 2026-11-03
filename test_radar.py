"""Offline qualification regressions: no browser or third-party requests."""
import unittest
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import radar

def page(text,url='https://example.com/',**extra):
    return dict(text=text,identity_text=text,url=url,title='Firma',**extra)

class QualificationTests(unittest.TestCase):
    def test_bankier_regression(self):
        p=page('Projekt PWR pokazuje, że polskie miasta przyciągają inwestycje z obszaru produkcji. Nasza fabryka w Polsce.',url='https://www.bankier.pl/')
        self.assertFalse(radar.classify([p])[0])

    def test_unknown_news_publisher(self):
        p=page('Nasza fabryka w Polsce. Produkujemy części.',schema_types=['NewsMediaOrganization'])
        self.assertFalse(radar.classify([p])[0])

    def test_editorial_self_description(self):
        self.assertFalse(radar.classify([page('Portal gospodarczy. Nasza fabryka w Polsce. Produkujemy maszyny.')])[0])

    def test_manufacturer_can_have_news_schema(self):
        self.assertTrue(radar.classify([page('Produkujemy maszyny w Polsce.',schema_types=['Organization','NewsArticle'])])[0])

    def test_third_party_investment_article(self):
        p=page('Jesteśmy producentem. Nasza fabryka w Polsce.',url='https://example.com/news/new-factory')
        self.assertFalse(radar.classify([page('Aktualności gospodarcze'),p])[0])

    def test_own_polish_manufacturing(self):
        self.assertTrue(radar.classify([page('Jesteśmy producentem opakowań. Produkujemy w Polsce od 1992 roku.')])[0])

    def test_own_factory(self):
        self.assertTrue(radar.classify([page('Nasza fabryka znajduje się w Polsce. Wytwarzamy komponenty.')])[0])

    def test_english_own_factory(self):
        self.assertTrue(radar.classify([page('We are a manufacturer of components. Our factory is in Poland.')])[0])

    def test_identity_subpage(self):
        self.assertTrue(radar.classify([page('Witamy'),page('Produkujemy meble w Polsce.',url='https://example.com/o-firmie/')])[0])

    def test_about_us_subpage(self):
        self.assertTrue(radar.classify([page('Welcome'),page('We manufacture components in Poland.',url='https://example.com/about-us/')])[0])

    def test_distributor_mentions_manufacturer(self):
        self.assertFalse(radar.classify([page('Jesteśmy dystrybutorem. Nasz dostawca to polski producent. Zakład produkcyjny znajduje się w Polsce.')])[0])

    def test_polish_headquarters_is_not_factory(self):
        self.assertFalse(radar.classify([page('Jesteśmy polskim producentem. Siedziba w Polsce. Nasza fabryka znajduje się w Chinach.')])[0])

    def test_negation(self):
        self.assertFalse(radar.classify([page('Nie produkujemy w Polsce. Jesteśmy dystrybutorem.')])[0])

    def test_foreign_page_cannot_qualify(self):
        self.assertFalse(radar.classify([page('Witamy'),page('Produkujemy w Polsce.',url='https://other.example/o-nas/')])[0])

    def test_article_content_is_not_identity_text(self):
        p=page('Portal. Produkujemy w Polsce.')
        p['identity_text']='Wiadomości z rynku.'
        self.assertFalse(radar.classify([p])[0])

    def test_directory(self):
        self.assertFalse(radar.classify([page('Katalog producentów. Produkujemy w Polsce.')])[0])

    def test_no_pages(self):
        self.assertFalse(radar.classify([])[0])

    def test_no_guessed_location_from_domain(self):
        self.assertFalse(radar.classify([page('Produkujemy meble.',url='https://example.pl/')])[0])

    def test_nonbreaking_space_in_polish_copy(self):
        self.assertTrue(radar.classify([page('Produkujemy w\u00a0Polsce.')])[0])

    def test_excel_preserves_rejected_rows_and_text(self):
        rows=[{'domain':'factory.example','url':'https://factory.example/','status':'kandydat','opportunity_score':25,'findings':'=1+1'},
              {'domain':'bankier.pl','url':'https://bankier.pl/','status':'odrzucony','opportunity_score':0}]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'leady.xlsx'
            radar.write_excel(path,rows,'2026-11-03T00:00:00Z',[],2)
            with zipfile.ZipFile(path) as z:
                self.assertIsNone(z.testzip())
                ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for f in ['xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml']:
                    root=ET.fromstring(z.read(f))
                    self.assertEqual(len(root.findall('s:sheetData/s:row',ns)),2)
                    self.assertEqual(root.findall('.//s:f',ns),[])
                raw=z.read('xl/worksheets/sheet1.xml').decode()
                self.assertIn('=1+1',raw)
                self.assertNotIn('bankier.pl',raw)

    def test_bing_article_and_bankier_excluded(self):
        xml=b'''<rss><channel><item><title>Producent production plant</title><link>https://bankier.pl/story</link></item><item><title>Producent production plant</title><link>https://example.com/news/factory</link></item><item><title>Producent production plant</title><link>https://factory.example/about-us/</link></item></channel></rss>'''
        class Reply:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return xml
        class Opener:
            def open(self,*args,**kwargs): return Reply()
        errors=[]
        with patch.object(radar.R,'build_opener',return_value=Opener()),patch.object(radar,'QUERIES',['production']),patch.object(radar,'ROOT',radar.ROOT/'nonexistent-test-folder'):
            found=radar.discover(errors)
        self.assertEqual([x['domain'] for x in found],['factory.example'])
        self.assertTrue(any('Małe pokrycie' in x for x in errors))

if __name__=='__main__': unittest.main()
