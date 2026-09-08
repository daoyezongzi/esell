"""Offline output checks; no network, credentials, dependencies or market verdicts."""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

STATES = {'EXCLUDED_EXISTING_OR_USER', 'REJECTED_CONFIRMED', 'QUEUED_INCOMPLETE', 'REVIEW_READY', 'QUALIFIED_SCREENING'}
SEARCH_STATES = {'NOT_SEARCHED', 'SEARCHED_NO_MATCH_IN_SCOPE', 'MATCH_PENDING', 'MATCH_CONFIRMED', 'ACCESS_UNAVAILABLE'}
CHECK_STATES = {'PASS', 'FAIL_OBSERVED', 'UNKNOWN', 'NOT_APPLICABLE'}
CAUSES = {'ACCESS_UNAVAILABLE', 'NOT_PUBLIC', 'INPUT_NOT_PROVIDED', 'CONFLICT', 'BUDGET_NOT_RUN', 'USER_SKIPPED'}

def strings(value, minimum=0):
    return isinstance(value,list) and len(value)>=minimum and all(isinstance(s,str) and s.strip() for s in value)

def validate(data):
    errors=[]
    if not isinstance(data,dict) or data.get('schema_version')!=1 or not isinstance(data.get('candidates'),list):
        return ['Expected schema_version=1 and candidates array']
    seen=set()
    for i,c in enumerate(data['candidates']):
        prefix=f'candidate[{i}]'
        def require(ok, message):
            if not ok: errors.append(prefix+': '+message)
        if not isinstance(c,dict):
            require(False,'must be an object'); continue
        for key in ('id','part_number','product','identity','reason'):
            require(isinstance(c.get(key),str) and bool(c[key].strip()),key+' is required')
        identifier=c.get('id')
        if isinstance(identifier,str):
            require(identifier not in seen,'duplicate id'); seen.add(identifier)
        require(c.get('status') in STATES,'unknown status')
        require(isinstance(c.get('evidence'),list),'evidence must be an array')
        checks=c.get('checks',{})
        if not isinstance(checks,dict): checks={}
        for key in ('identity','history','price','competition','demand','supplier'):
            require(checks.get(key) in CHECK_STATES,'invalid or absent check '+key)
        missing=c.get('missing')
        require(isinstance(missing,list),'missing must be an array')
        for gap in missing if isinstance(missing,list) else []:
            if not isinstance(gap,dict): require(False,'gap must be an object'); continue
            require(gap.get('cause') in CAUSES,'invalid gap cause')
            require(gap.get('owner') in {'assistant','human'},'invalid gap owner')
            require(bool(gap.get('field')) and bool(gap.get('needed')),'gap needs field and needed evidence')
            if c.get('status')=='REVIEW_READY':
                require(gap.get('owner')=='human' and gap.get('cause')!='BUDGET_NOT_RUN','REVIEW_READY cannot hide unfinished assistant work')
        accepted_exceptions=set()
        exceptions=c.get('exceptions',[])
        require(isinstance(exceptions,list),'exceptions must be an array')
        for ex in exceptions if isinstance(exceptions,list) else []:
            valid=(isinstance(ex,dict) and ex.get('check')=='demand' and ex.get('accepted_by_user') is True and bool(ex.get('basis')) and bool(ex.get('acceptance_record')))
            require(valid,'demand exception needs evidence and explicit user acceptance record')
            if valid: accepted_exceptions.add(ex['check'])
        if c.get('status')=='QUALIFIED_SCREENING':
            require(all(v in {'PASS','NOT_APPLICABLE'} or k in accepted_exceptions for k,v in checks.items()),'qualified candidate has an unresolved/failed gate')
            require(missing==[],'qualified candidate cannot retain gating gaps')
        s=c.get('search_1688')
        if not isinstance(s,dict): require(False,'search_1688 package is required'); continue
        require(s.get('status') in SEARCH_STATES,'invalid 1688 status')
        for key,minimum in [('part_number_terms',1),('chinese_terms',2),('physical_checks',2),('do_not_confuse',1),('searched_queries',0),('supplier_urls',0),('unconfirmed_aliases',0)]:
            require(strings(s.get(key),minimum),'invalid or missing '+key)
        aliases=s.get('confirmed_alias_terms')
        require(isinstance(aliases,list),'confirmed_alias_terms must be an array')
        for alias in aliases if isinstance(aliases,list) else []:
            require(isinstance(alias,dict) and bool(alias.get('term')) and bool(alias.get('basis')) and alias.get('confirmation_level') in {'manufacturer','dealer'},'confirmed alias needs term, supporting basis and confirmation level')
        image=s.get('image_search')
        require(isinstance(image,dict) and bool(image.get('instructions')),'image search instructions required even when exact image unavailable')
        if isinstance(image,dict) and image.get('reference_url') is not None:
            require(isinstance(image['reference_url'],str) and urlparse(image['reference_url']).scheme in {'http','https'},'invalid image source URL')
        if s.get('status')=='NOT_SEARCHED':
            require(s.get('searched_queries')==[] and s.get('supplier_urls')==[] and s.get('match_evidence') is None,'NOT_SEARCHED cannot claim executed queries or supplier matches')
        if s.get('status')=='MATCH_CONFIRMED':
            require(strings(s.get('searched_queries'),1),'confirmed match requires actual queries')
            require(strings(s.get('supplier_urls'),1) and bool(s.get('match_evidence')),'confirmed match requires supplier URL and physical evidence')
        if checks.get('supplier')=='PASS':
            require(s.get('status')=='MATCH_CONFIRMED','supplier PASS requires actual confirmed match')
    return errors

def main():
    if len(sys.argv)!=2:
        print('Usage: python validate_candidates.py <candidates.json>'); return 2
    try:
        data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        errors=validate(data)
    except (OSError,ValueError,TypeError) as exc:
        print('Invalid input: '+str(exc)); return 2
    if errors:
        print('\n'.join(errors)); return 1
    print(f"Valid output structure: {len(data['candidates'])} candidates. Market truth not verified.")
    return 0

if __name__=='__main__':
    raise SystemExit(main())
