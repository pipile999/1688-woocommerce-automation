import tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image,ImageDraw
from app.strict_reaudit import canonical,identified_offers,candidate_evidence
from app.strict_reaudit_images import contained,phash,distance
from app.strict_reaudit_apply import protected,description

class StrictReauditTests(unittest.TestCase):
    def test_url_binding_not_query_or_fuzzy_title(self):
        self.assertEqual(canonical('https://detail.1688.com/offer/123456789.html?offerId=999'),'123456789')
        self.assertIsNone(canonical('https://example.org/offer/123456789.html'))
        self.assertEqual(identified_offers({'name':'123456789','attributes':[{'name':'Model','options':['1']}]}),set())

    def test_conflicting_source_and_model_both_exposed(self):
        p={'meta_data':[{'key':'_1688_offer_id','value':'123'},{'key':'_1688_source_url','value':'https://detail.1688.com/offer/456.html'}]}
        self.assertEqual(identified_offers(p),{'123','456'})

    def test_cross_offer_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'123';root.mkdir()
            with self.assertRaises(ValueError):contained(root,'../456/image.webp')

    def test_resize_duplicate_detected(self):
        with tempfile.TemporaryDirectory() as d:
            image=Image.new('RGB',(800,800),'white');ImageDraw.Draw(image).ellipse((100,180,650,680),fill='green')
            a=Path(d)/'a.png';b=Path(d)/'renamed.webp'
            image.save(a);image.resize((600,600)).save(b,quality=90)
            self.assertLessEqual(distance(phash(a),phash(b)),5)

    def test_protected_prices_ids_status(self):
        before={'id':123,'status':'publish','meta_data':[{'key':'_1688_source_url','value':'original'}]}
        variants=[{'id':9,'sku':'rawsku','regular_price':'2.13','meta_data':[{'key':'_1688_spec_id','value':'rawspec'}]}]
        snap=protected(before,variants)
        variants[0]['image']={'id':5}
        self.assertEqual(snap,protected(before,variants))
        variants[0]['regular_price']='2.14'
        self.assertNotEqual(snap,protected(before,variants))

    def test_automatic_view_counter_is_not_business_data(self):
        a={'meta_data':[{'key':'shopengine_product_views_count','value':'1'},{'key':'_1688_offer_id','value':'123'}]}
        b={'meta_data':[{'key':'shopengine_product_views_count','value':'2'},{'key':'_1688_offer_id','value':'123'}]}
        self.assertEqual(protected(a,[]),protected(b,[]))
        b['meta_data'][1]['value']='456'
        self.assertNotEqual(protected(a,[]),protected(b,[]))

    def test_correct_description_is_not_reformatted(self):
        original='<p>Original content</p><img src="https://example.org/full.webp" style="max-width:100%;height:auto;">'
        plan={'description':[1],'records':[]}
        self.assertEqual(description({'description':original},plan,{1:{'src':'https://example.org/full.webp'}}),(original,{}))

    def test_updated_checkpoint_is_immutable(self):
        from app.strict_reaudit_apply import checkpoint
        from app.strict_reaudit import read
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'repair-checkpoint.json'
            with patch('app.strict_reaudit_apply.CHECKPOINT',path):
                checkpoint({'offer_id':'123','product_id':9,'modified':True,'verified_at':'first'})
                checkpoint({'offer_id':'123','product_id':10,'modified':False,'verified_at':'second'})
            self.assertEqual(read(path)['123'],{'offer_id':'123','product_id':9,'status':'UPDATED','timestamp':'first','rest_verified':True})

    def test_empty_generated_asset_cache_equals_absent(self):
        a={'meta_data':[{'key':'_elementor_page_assets','value':[]}]}
        self.assertEqual(protected(a,[]),protected({'meta_data':[]},[]))
        a['meta_data'][0]['value']={'scripts':['changed']}
        self.assertNotEqual(protected(a,[]),protected({'meta_data':[]},[]))

if __name__=='__main__':unittest.main()
