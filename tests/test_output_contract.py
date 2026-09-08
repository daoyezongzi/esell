"""Regression scenarios from the selection and supplier-handoff workflow."""
import importlib.util
import copy
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/esell-sourcing'
spec=importlib.util.spec_from_file_location('candidate_validator',SKILL/'scripts/validate_candidates.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class OutputContractTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((SKILL/'assets/example-candidates.json').read_text(encoding='utf-8'))

    def amazon_candidate(self, sellers=10):
        c=self.data['candidates'][0]
        c['amazon_gate']={
            'status':'PASS' if sellers<=10 else 'FAIL', 'seller_limit':10,
            'coverage':'COMPLETE','delivery_zip':'10001',
            'queries':[{'query':'SYNTHETIC-PART','source_url':'https://www.amazon.com/s?k=SYNTHETIC-PART','observed_at':'2026-09-08','coverage':'COMPLETE'}],
            'offers':[{'seller_id':f'SELLER{i}','asin':'SYNTHETIC1','url':'https://www.amazon.com/dp/SYNTHETIC1','observed_at':'2026-09-08','match':'EXACT','availability':'ACTIVE','price_state':'NORMAL','item_price_usd':80.0,'shipping_usd':0,'evidence':'Synthetic test fixture: exact physical part, active offer and normal quote.'} for i in range(sellers)]
        }
        c['checks']['competition']='PASS' if sellers<=10 else 'FAIL_OBSERVED'
        if sellers>10:
            c['status']='REJECTED_CONFIRMED'
        return c

    def review_candidate(self):
        c=self.amazon_candidate()
        c['status']='REVIEW_READY'
        for key in ('identity','history','price'):
            c['checks'][key]='PASS'
        c['missing']=[g for g in c['missing'] if g['owner']=='human']
        return c

    def assert_invalid(self):
        self.assertTrue(module.validate(self.data))

    def test_historical_examples_with_unknown_markets_are_allowed(self):
        self.assertEqual(module.validate(self.data),[])

    def test_each_product_needs_its_own_search_package(self):
        del self.data['candidates'][1]['search_1688']
        self.assertTrue(module.validate(self.data))

    def test_unsearched_plan_cannot_claim_supplier_found(self):
        self.data['candidates'][0]['search_1688']['supplier_urls']=['https://detail.1688.com/offer/123.html']
        self.assertTrue(module.validate(self.data))

    def test_search_suggestion_cannot_be_actual_executed_query(self):
        self.data['candidates'][0]['search_1688']['searched_queries']=['A17-13787-002']
        self.assertTrue(module.validate(self.data))

    def test_confirmed_alias_requires_basis(self):
        del self.data['candidates'][0]['search_1688']['confirmed_alias_terms'][0]['basis']
        self.assertTrue(module.validate(self.data))

    def test_budget_not_run_stays_in_assistant_queue(self):
        self.data['candidates'][0]['status']='REVIEW_READY'
        self.assertTrue(module.validate(self.data))

    def test_qualified_cannot_contain_unknown_gates(self):
        self.data['candidates'][0]['status']='QUALIFIED_SCREENING'
        self.assertTrue(module.validate(self.data))

    def test_supplier_pass_requires_confirmed_physical_match(self):
        self.data['candidates'][0]['checks']['supplier']='PASS'
        self.assertTrue(module.validate(self.data))

    def test_final_human_gaps_can_be_review_ready(self):
        self.review_candidate()
        # Evidence still needs real review; structural checks allow explicitly assigned human gaps.
        self.assertEqual(module.validate(self.data),[])

    def test_missing_history_input_is_not_a_platform_outage(self):
        self.data['candidates'][0]['missing'].append({'field':'history','cause':'INPUT_NOT_PROVIDED','owner':'human','needed':'用户历史清单'})
        self.assertEqual(module.validate(self.data),[])

    def test_explicit_demand_exception_preserves_unknown_annual_gate(self):
        c=self.amazon_candidate()
        c['status']='QUALIFIED_SCREENING'
        c['checks']={k:'PASS' for k in c['checks']}
        c['checks']['demand']='UNKNOWN'
        c['checks']['supplier']='NOT_APPLICABLE'
        c['missing']=[]
        c['exceptions']=[{'check':'demand','accepted_by_user':True,'basis':'Synthetic fixture: original OEM identity and dated cumulative sales evidence','acceptance_record':'Synthetic fixture: explicit user acceptance, not a real product verdict'}]
        self.assertEqual(module.validate(self.data),[])
        c['exceptions'][0]['accepted_by_user']=False
        self.assertTrue(module.validate(self.data))

    def test_legacy_schema_is_not_v2_verified(self):
        self.data['schema_version']=1
        self.assert_invalid()

    def test_amazon_gate_is_required_on_every_candidate(self):
        del self.data['candidates'][1]['amazon_gate']
        self.assert_invalid()

    def test_ten_active_normal_exact_seller_accounts_pass(self):
        self.amazon_candidate(10)
        self.assertEqual(module.validate(self.data),[])

    def test_eleven_seller_accounts_fail_even_with_partial_coverage(self):
        c=self.amazon_candidate(11)
        c['amazon_gate']['coverage']='PARTIAL'
        c['amazon_gate']['queries'][0]['coverage']='PARTIAL'
        self.assertEqual(module.validate(self.data),[])
        c['amazon_gate']['status']='PASS'
        self.assert_invalid()

    def test_same_seller_across_asins_is_counted_once(self):
        c=self.amazon_candidate(10)
        row=copy.deepcopy(c['amazon_gate']['offers'][0])
        row['asin']='SYNTHETIC2'
        c['amazon_gate']['offers'].append(row)
        self.assertEqual(module.validate(self.data),[])

    def test_multiple_sellers_on_one_asin_are_distinct(self):
        c=self.amazon_candidate(11)
        result=module.validate_amazon_gate(c['amazon_gate'],lambda ok,message: self.assertTrue(ok,message))
        self.assertEqual(result,{'status':'FAIL','lower':11,'upper':11})

    def test_common_company_does_not_merge_seller_accounts(self):
        c=self.amazon_candidate(11)
        for row in c['amazon_gate']['offers']:
            row['company']='ONE SHARED COMPANY'
        self.assertEqual(module.validate(self.data),[])

    def test_incomplete_coverage_cannot_pass(self):
        for level in ('PARTIAL','UNAVAILABLE'):
            with self.subTest(level=level):
                c=self.amazon_candidate()
                c['amazon_gate']['coverage']=level
                self.assert_invalid()
                c['amazon_gate']['status']='UNVERIFIED'
                c['checks']['competition']='UNKNOWN'
                self.assertEqual(module.validate(self.data),[])

    def test_partial_query_prevents_pass_even_if_overall_claim_is_complete(self):
        c=self.amazon_candidate()
        c['amazon_gate']['queries'][0]['coverage']='PARTIAL'
        self.assert_invalid()

    def test_empty_or_suggested_queries_cannot_pass(self):
        for queries in ([],['SYNTHETIC-PART'],[{'query':'SYNTHETIC-PART'}]):
            with self.subTest(queries=queries):
                self.amazon_candidate()['amazon_gate']['queries']=queries
                self.assert_invalid()

    def test_empty_offers_cannot_pass(self):
        self.amazon_candidate()['amazon_gate']['offers']=[]
        self.assert_invalid()

    def test_no_quote_or_unknown_identity_inventory_or_price_cannot_pass(self):
        for key,value in [('item_price_usd',None),('item_price_usd',0),('price_state','UNKNOWN'),('match','UNKNOWN'),('availability','UNKNOWN')]:
            with self.subTest(key=key,value=value):
                c=self.amazon_candidate()
                c['amazon_gate']['offers'][0][key]=value
                self.assert_invalid()
                c['amazon_gate']['status']='UNVERIFIED'
                c['checks']['competition']='UNKNOWN'
                self.assertEqual(module.validate(self.data),[])

    def test_unknown_extra_offer_prevents_pass_even_for_known_seller(self):
        c=self.amazon_candidate()
        row=copy.deepcopy(c['amazon_gate']['offers'][0])
        row['availability']='UNKNOWN'
        c['amazon_gate']['offers'].append(row)
        self.assert_invalid()

    def test_low_normal_price_counts_as_competition(self):
        c=self.amazon_candidate(11)
        c['amazon_gate']['offers'][-1]['item_price_usd']=0.01
        self.assertEqual(module.validate(self.data),[])

    def test_abnormal_exclusion_needs_reason_and_inactive_other_are_excluded(self):
        for field,value in [('price_state','ABNORMAL'),('availability','INACTIVE'),('match','OTHER')]:
            with self.subTest(field=field):
                c=self.amazon_candidate(11)
                c['status']='QUEUED_INCOMPLETE'
                c['amazon_gate']['status']='PASS'
                c['checks']['competition']='PASS'
                row=c['amazon_gate']['offers'][-1]
                row[field]=value
                if value=='ABNORMAL':
                    self.assert_invalid()
                    row['exclusion_reason']='Synthetic evidence: offer price is a refundable deposit only.'
                self.assertEqual(module.validate(self.data),[])

    def test_seller_limit_defaults_to_ten_and_cannot_be_raised(self):
        c=self.amazon_candidate()
        del c['amazon_gate']['seller_limit']
        self.assertEqual(module.validate(self.data),[])
        for value in (11,True,10.0,'10',None,0,[]):
            with self.subTest(value=value):
                c['amazon_gate']['seller_limit']=value
                self.assert_invalid()

    def test_pass_requires_10001_delivery_zip(self):
        for zipcode in (None,'90210',10001):
            with self.subTest(zipcode=zipcode):
                self.amazon_candidate()['amazon_gate']['delivery_zip']=zipcode
                self.assert_invalid()

    def test_check_competition_must_agree_with_gate(self):
        self.amazon_candidate()['checks']['competition']='UNKNOWN'
        self.assert_invalid()

    def test_confirmed_failure_cannot_be_queued(self):
        self.amazon_candidate(11)['status']='QUEUED_INCOMPLETE'
        self.assert_invalid()

    def test_report_only_rejection_does_not_invent_verified_offers(self):
        c=self.data['candidates'][0]
        c['status']='REJECTED_CONFIRMED'
        c['evidence'].append({'fact':'Synthetic user report of 23 sellers, no independently observed seller rows.'})
        self.assertEqual(module.validate(self.data),[])

    def test_review_ready_requires_each_main_gate(self):
        for key in ('identity','history','price','competition'):
            with self.subTest(key=key):
                c=self.review_candidate()
                c['checks'][key]='UNKNOWN'
                self.assert_invalid()
        c=self.review_candidate()
        c['amazon_gate']['coverage']='PARTIAL'
        c['amazon_gate']['status']='UNVERIFIED'
        c['checks']['competition']='UNKNOWN'
        self.assert_invalid()

    def test_invalid_offer_types_and_evidence_produce_errors(self):
        for key,value in [('seller_id',''),('asin',None),('url','not-a-url'),('observed_at',''),('evidence',''),('match',[]),('availability',{}),('price_state',[]),('item_price_usd',True),('item_price_usd',float('nan')),('shipping_usd',-1)]:
            with self.subTest(key=key):
                self.amazon_candidate()['amazon_gate']['offers'][0][key]=value
                self.assert_invalid()

    def test_lower_and_upper_bounds_preserve_uncertainty(self):
        c=self.amazon_candidate(10)
        c['amazon_gate']['offers'][0]['availability']='UNKNOWN'
        c['amazon_gate']['status']='UNVERIFIED'
        result=module.validate_amazon_gate(c['amazon_gate'],lambda ok,message: self.assertTrue(ok,message))
        self.assertEqual(result,{'status':'UNVERIFIED','lower':9,'upper':10})

if __name__=='__main__': unittest.main()
