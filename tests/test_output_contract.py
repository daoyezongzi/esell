"""Regression scenarios from the selection and supplier-handoff workflow."""
import importlib.util
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
        c=self.data['candidates'][0]
        c['status']='REVIEW_READY'
        c['missing']=[g for g in c['missing'] if g['owner']=='human']
        # Evidence still needs real review; structural checks allow explicitly assigned human gaps.
        self.assertEqual(module.validate(self.data),[])

    def test_missing_history_input_is_not_a_platform_outage(self):
        self.data['candidates'][0]['missing'].append({'field':'history','cause':'INPUT_NOT_PROVIDED','owner':'human','needed':'用户历史清单'})
        self.assertEqual(module.validate(self.data),[])

    def test_explicit_demand_exception_preserves_unknown_annual_gate(self):
        c=self.data['candidates'][0]
        c['status']='QUALIFIED_SCREENING'
        c['checks']={k:'PASS' for k in c['checks']}
        c['checks']['demand']='UNKNOWN'
        c['checks']['supplier']='NOT_APPLICABLE'
        c['missing']=[]
        c['exceptions']=[{'check':'demand','accepted_by_user':True,'basis':'Synthetic fixture: original OEM identity and dated cumulative sales evidence','acceptance_record':'Synthetic fixture: explicit user acceptance, not a real product verdict'}]
        self.assertEqual(module.validate(self.data),[])
        c['exceptions'][0]['accepted_by_user']=False
        self.assertTrue(module.validate(self.data))

if __name__=='__main__': unittest.main()
