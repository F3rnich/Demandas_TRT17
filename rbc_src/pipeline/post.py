import json,os
D={x['case']:x for x in json.load(open('dataset.json'))}
for cid in os.listdir('casos'):
    p='casos/%s/caso.json'%cid
    if not os.path.exists(p) or cid not in D: continue
    c=json.load(open(p)); c['meta']['gabarito']=D[cid]['gold']['fmt']; c['meta']['gabaritoArq']=D[cid]['gold']['arquivo']
    json.dump(c,open(p,'w'),ensure_ascii=False,indent=1)
