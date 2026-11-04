"""Synthetic documents for behavioral workflow tests; no contest material."""
import json
import workflow as w
import harness as h


def intake(root):
    (root/'BRIEF.md').write_text('Synthetic brief: return the integer three. CLI delivery.')
    d={
        'schema_version':1,'goal':'Return three via the CLI',
        'sources':[{'id':'S1','path':'BRIEF.md','locator':'sentence 1','role':'synthetic requirements'}],
        'components':[{'id':'C1','kind':'behavior','decision':'Return constant','inputs':'none','outputs':'integer','depends_on':[],'requirement_ids':['R1']}],
        'composition':'One component; no shared resources','couplings':[],
        'rules':[{'id':'K1','type':'behavior','source':'S1','meaning':'Return three','requirement_ids':['R1'],'check_ids':['value']}],
        'data_review':{'keys':'No entity IDs','joins':'No joins','units':'integer','time':'No dates','missing':'No input','duplicates':'No input rows','scale':'One constant'},
        'objective':{'order':'Correct output only','tradeoffs':'No optimization'},
        'delivery':{'run_command':'python app.py','submission_method':'Local source file app.py'},
        'baseline':{'method':'Return constant','feasibility':'Directly verifiable','check':'value'},
        'model_size':{'estimate':'One scalar','growth_risk':'constant','reduction':'Not applicable: no search'},
        'unknowns':[],'next_slice':{'behavior':'CLI value','check':'value'},'out_of_scope':'No UI requested'}
    h.write_json(w.path(root,'intake.json'),d)
    return d


def build_ready(root):
    intake(root)
    w.event(root,'inputs-reviewed','Synthetic brief reviewed')
    w.select(root,'baseline','No optimization','Unnecessary solver runtime','Synthetic input has one constant')
    h.write_json(w.path(root,'contract.json'),{'revision':'v1','owner':'core','requirement_ids':['R1'],
                 'input':'none','output':'integer three','failure_behavior':'nonzero exit'})
    w.event(root,'contract-ready','Interface recorded')


def verify_phase(root):
    build_ready(root)
    w.event(root,'candidate-ready','Candidate connected')
    w.event(root,'integrated','Real CLI path connected')
