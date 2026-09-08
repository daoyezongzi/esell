"""Offline output checks; no network, credentials, dependencies or market verdicts."""
import json
import math
import sys
from pathlib import Path
from urllib.parse import urlparse

STATES = {'EXCLUDED_EXISTING_OR_USER', 'REJECTED_CONFIRMED', 'QUEUED_INCOMPLETE', 'REVIEW_READY', 'QUALIFIED_SCREENING'}
SEARCH_STATES = {'NOT_SEARCHED', 'SEARCHED_NO_MATCH_IN_SCOPE', 'MATCH_PENDING', 'MATCH_CONFIRMED', 'ACCESS_UNAVAILABLE'}
CHECK_STATES = {'PASS', 'FAIL_OBSERVED', 'UNKNOWN', 'NOT_APPLICABLE'}
CAUSES = {'ACCESS_UNAVAILABLE', 'NOT_PUBLIC', 'INPUT_NOT_PROVIDED', 'CONFLICT', 'BUDGET_NOT_RUN', 'USER_SKIPPED'}

def strings(value, minimum=0):
    return isinstance(value,list) and len(value)>=minimum and all(isinstance(s,str) and s.strip() for s in value)


def nonempty(value):
    return isinstance(value,str) and bool(value.strip())


def number(value):
    return type(value) in (int,float) and math.isfinite(value)


def choice(value, allowed):
    return isinstance(value,str) and value in allowed


def web_url(value):
    if not nonempty(value):
        return False
    try:
        parsed=urlparse(value)
        return parsed.scheme in {'http','https'} and bool(parsed.netloc)
    except ValueError:
        return False


def validate_amazon_gate(gate, require):
    """Check recorded evidence and derive bounds, without verifying market truth."""
    if not isinstance(gate,dict):
        require(False,'amazon_gate object is required')
        return {'status':'UNVERIFIED','lower':0,'upper':0}
    status=gate.get('status')
    coverage=gate.get('coverage')
    limit=gate.get('seller_limit',10)
    require(choice(status,{'PASS','FAIL','UNVERIFIED'}),'invalid amazon_gate status')
    valid_limit=type(limit) is int and 1<=limit<=10
    require(valid_limit,'amazon_gate seller_limit must be an integer from 1 to 10 (default 10)')
    require(choice(coverage,{'COMPLETE','PARTIAL','UNAVAILABLE'}),'invalid amazon_gate coverage')
    require('delivery_zip' in gate and (gate['delivery_zip'] is None or nonempty(gate['delivery_zip'])),'amazon_gate delivery_zip must be a string or null')
    queries=gate.get('queries')
    offers=gate.get('offers')
    require(isinstance(queries,list),'amazon_gate queries must be an array of actual searches')
    require(isinstance(offers,list),'amazon_gate offers must be an array of actual seller rows')
    complete_queries=isinstance(queries,list) and bool(queries)
    for query in queries if isinstance(queries,list) else []:
        valid=(isinstance(query,dict) and nonempty(query.get('query')) and web_url(query.get('source_url')) and nonempty(query.get('observed_at')) and choice(query.get('coverage'),{'COMPLETE','PARTIAL'}))
        require(valid,'amazon_gate query needs query, source_url, observed_at and coverage')
        complete_queries=complete_queries and valid and query.get('coverage')=='COMPLETE'
    lower=set()
    upper=set()
    unresolved=False
    for row in offers if isinstance(offers,list) else []:
        if not isinstance(row,dict):
            require(False,'amazon_gate offer must be an object')
            unresolved=True
            continue
        identity_ok=nonempty(row.get('seller_id')) and nonempty(row.get('asin'))
        require(identity_ok,'amazon_gate offer needs nonempty seller_id and asin')
        require(web_url(row.get('url')) and nonempty(row.get('observed_at')) and nonempty(row.get('evidence')),'amazon_gate offer needs url, observed_at and evidence')
        require(choice(row.get('match'),{'EXACT','OTHER','UNKNOWN'}),'invalid offer match')
        require(choice(row.get('availability'),{'ACTIVE','INACTIVE','UNKNOWN'}),'invalid offer availability')
        require(choice(row.get('price_state'),{'NORMAL','ABNORMAL','UNKNOWN'}),'invalid offer price_state')
        for field in ('item_price_usd','shipping_usd'):
            require(field in row and (row[field] is None or (number(row[field]) and row[field]>=0)),field+' must be a finite nonnegative number or null')
        if row.get('price_state')=='ABNORMAL':
            require(nonempty(row.get('exclusion_reason')),'ABNORMAL offer requires an evidence-based exclusion_reason; low price alone is not an exclusion')
        excluded=row.get('match')=='OTHER' or row.get('availability')=='INACTIVE' or row.get('price_state')=='ABNORMAL'
        confirmed=(identity_ok and row.get('match')=='EXACT' and row.get('availability')=='ACTIVE' and row.get('price_state')=='NORMAL' and number(row.get('item_price_usd')) and row['item_price_usd']>0)
        if not excluded:
            if nonempty(row.get('seller_id')):
                upper.add(row['seller_id'])
            unresolved=unresolved or not confirmed
        if confirmed:
            lower.add(row['seller_id'])
    computed='UNVERIFIED'
    if valid_limit and choice(coverage,{'COMPLETE','PARTIAL'}) and len(lower)>limit:
        computed='FAIL'
    elif (valid_limit and coverage=='COMPLETE' and complete_queries and gate.get('delivery_zip')=='10001' and isinstance(offers,list) and not unresolved and 0<len(lower)<=limit):
        computed='PASS'
    require(status==computed,f'amazon_gate status must be {computed} from recorded evidence (seller lower={len(lower)}, upper={len(upper)})')
    return {'status':computed,'lower':len(lower),'upper':len(upper)}


def validate(data):
    errors=[]
    if not isinstance(data,dict) or type(data.get('schema_version')) is not int or data.get('schema_version')!=2 or not isinstance(data.get('candidates'),list):
        return ['Expected schema_version=2 and candidates array; legacy schema 1 is not verified']
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
        require(choice(c.get('status'),STATES),'unknown status')
        require(isinstance(c.get('evidence'),list),'evidence must be an array')
        checks=c.get('checks',{})
        if not isinstance(checks,dict): checks={}
        for key in ('identity','history','price','competition','demand','supplier'):
            require(choice(checks.get(key),CHECK_STATES),'invalid or absent check '+key)
        gate=validate_amazon_gate(c.get('amazon_gate'),require)
        require(checks.get('competition')=={'PASS':'PASS','FAIL':'FAIL_OBSERVED','UNVERIFIED':'UNKNOWN'}[gate['status']],'checks.competition must agree with amazon_gate')
        if c.get('status')=='QUEUED_INCOMPLETE':
            require(gate['status']!='FAIL','confirmed Amazon failure must be REJECTED_CONFIRMED, not queued')
        if choice(c.get('status'),{'REVIEW_READY','QUALIFIED_SCREENING'}):
            require(gate['status']=='PASS','recommendation requires amazon_gate PASS')
            require(all(checks.get(key)=='PASS' for key in ('identity','history','price')),'recommendation requires identity, history and price PASS')
        missing=c.get('missing')
        require(isinstance(missing,list),'missing must be an array')
        for gap in missing if isinstance(missing,list) else []:
            if not isinstance(gap,dict): require(False,'gap must be an object'); continue
            require(choice(gap.get('cause'),CAUSES),'invalid gap cause')
            require(choice(gap.get('owner'),{'assistant','human'}),'invalid gap owner')
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
            require(all(choice(v,{'PASS','NOT_APPLICABLE'}) or k in accepted_exceptions for k,v in checks.items()),'qualified candidate has an unresolved/failed gate')
            require(missing==[],'qualified candidate cannot retain gating gaps')
        s=c.get('search_1688')
        if not isinstance(s,dict): require(False,'search_1688 package is required'); continue
        require(choice(s.get('status'),SEARCH_STATES),'invalid 1688 status')
        for key,minimum in [('part_number_terms',1),('chinese_terms',2),('physical_checks',2),('do_not_confuse',1),('searched_queries',0),('supplier_urls',0),('unconfirmed_aliases',0)]:
            require(strings(s.get(key),minimum),'invalid or missing '+key)
        aliases=s.get('confirmed_alias_terms')
        require(isinstance(aliases,list),'confirmed_alias_terms must be an array')
        for alias in aliases if isinstance(aliases,list) else []:
            require(isinstance(alias,dict) and bool(alias.get('term')) and bool(alias.get('basis')) and choice(alias.get('confirmation_level'),{'manufacturer','dealer'}),'confirmed alias needs term, supporting basis and confirmation level')
        image=s.get('image_search')
        require(isinstance(image,dict) and bool(image.get('instructions')),'image search instructions required even when exact image unavailable')
        if isinstance(image,dict) and image.get('reference_url') is not None:
            require(web_url(image['reference_url']),'invalid image source URL')
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
