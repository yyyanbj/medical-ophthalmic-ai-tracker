import unittest
from datetime import date
from tracker.core import classify, norm_doi, norm_title, make_paper, merge_catalog
from tracker.sources.pubmed import parse_efetch
from tracker.sources.arxiv import parse_atom
from tracker.sources.medrxiv import parse_records
from tracker.sources.crossref import parse_work
from tracker.site import build
from tempfile import TemporaryDirectory
from pathlib import Path


class TrackerTests(unittest.TestCase):
    def test_keyword_scope(self):
        self.assertEqual(classify('AI-based OCT segmentation for glaucoma')[0], 'Ophthalmic AI')
        self.assertEqual(classify('Agentic reasoning in clinical care')[0], 'Medical Agent')
        self.assertEqual(classify('Quantum gravity survey')[0], 'out_of_scope')

    def test_doi_and_title(self):
        self.assertEqual(norm_doi('https://doi.org/10.1234/ABC'), '10.1234/abc')
        self.assertEqual(norm_title('A Study: Glaucoma AI'), norm_title('A study - glaucoma, AI'))

    def test_duplicate_cross_source_title(self):
        catalog = {}
        preprint = make_paper(title='Glaucoma Deep Learning from OCT', abstract='Deep learning for glaucoma OCT screening', authors=['A'], url='https://arxiv.org/abs/2601.00001', published='2026-01-01', source='arxiv', source_id='2601.00001', review_status='preprint')
        journal = make_paper(title='Glaucoma Deep Learning from OCT', abstract='Deep learning for glaucoma OCT screening', authors=['A'], url='https://doi.org/10.1000/journal', published='2026-05-01', source='crossref', source_id='10.1000/journal', doi='10.1000/journal', review_status='peer_reviewed')
        first, _ = merge_catalog(catalog, [preprint])
        second, _ = merge_catalog(catalog, [journal])
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(len(catalog), 1)
        item = next(iter(catalog.values()))
        self.assertEqual(item['published'], '2026-01-01')
        self.assertEqual(item['review_status'], 'peer_reviewed')

    def test_pubmed_xml(self):
        xml = '''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>Deep learning in glaucoma imaging</ArticleTitle><Abstract><AbstractText>Deep learning in a clinical ophthalmology study</AbstractText></Abstract><Journal><Title>Eye Journal</Title></Journal><AuthorList><Author><ForeName>A</ForeName><LastName>Bee</LastName></Author></AuthorList><ArticleDate><Year>2026</Year><Month>11</Month><Day>13</Day></ArticleDate></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1234/test</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>'''
        papers = parse_efetch(xml, 'eye_epdat')
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].doi, '10.1234/test')
        self.assertEqual(papers[0].published, '2026-11-13')

    def test_arxiv_atom(self):
        atom = '''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"><opensearch:totalResults>1</opensearch:totalResults><entry><id>http://arxiv.org/abs/2611.11111v1</id><title>Clinical AI agent</title><summary>Clinical AI agent in hospital</summary><published>2026-11-13T12:00:00Z</published><updated>2026-11-14T10:00:00Z</updated><author><name>Test Author</name></author></entry></feed>'''
        p, count = parse_atom(atom, 'medical_models_submitted')
        self.assertEqual(count, 1)
        self.assertEqual(p[0].source_id, '2611.11111')

    def test_medrxiv_page(self):
        payload = {"messages":[{"count":"1"}],"collection":[{"doi":"10.1101/2026.11.13.111","title":"Clinical agent in medicine","abstract":"AI agent used for medical decisions","authors":"A Smith; B Doe","date":"2026-11-13","version":"1"}]}
        p, count = parse_records(payload)
        self.assertEqual(count, 1)
        self.assertEqual(len(p), 1)

    def test_crossref_work(self):
        p = parse_work({"DOI":"10.1000/test","title":["AI for retinal disease"],"author":[{"given":"A","family":"Smith"}],"published-online":{"date-parts":[[2026,11,13]]}},'Eye Journal')
        self.assertEqual(p.published, '2026-11-13')
        self.assertEqual(p.domain, 'Ophthalmic AI')

    def test_site_build(self):
        with TemporaryDirectory() as d:
            site = Path(d)
            build({"date_la":"2026-11-14","run_at_utc":"2026-11-14T08:00:00Z","audits":[{"source":"pubmed","query_id":"test","date_field":"edat","total":2,"fetched":1,"complete":False,"error":"network","next_cursor":1}],"new_papers":[],"catalog_size":0}, site)
            self.assertTrue((site / 'index.html').exists())
            self.assertTrue((site / 'data/latest.json').exists())
            self.assertIn('部分检索', (site / 'index.html').read_text())

if __name__ == '__main__':
    unittest.main()
