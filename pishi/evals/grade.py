#!/usr/bin/env python3
"""Mechanical grader for pishi evals.

  python3 grade.py <run_dir> --eval <id>          # run_dir contains outputs/<file>
Writes <run_dir>/grading.json with `expectations` [{text, passed, evidence}].
Mechanical assertions get true/false; judgment assertions (from evals.json
`assertions`) are copied with passed=null for a reader to fill in.
"""
import argparse, json, os, re, subprocess, sys
HERE=os.path.dirname(os.path.abspath(__file__))
CHECK=os.path.join(HERE,"..","scripts","check.py")

def norm(s): return s.lower().replace("ё","е").replace(" "," ")
def has(text, s): return norm(s) in norm(text)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("run_dir"); ap.add_argument("--eval",type=int,required=True); a=ap.parse_args()
    d=json.load(open(os.path.join(HERE,"evals.json")))
    e=next(x for x in d["evals"] if x["id"]==a.eval); c=e["checks"]
    out=os.path.join(a.run_dir,"outputs",c["output"])
    exp=[]
    if not os.path.exists(out):
        # fall back: any file in outputs/
        files=[f for f in os.listdir(os.path.join(a.run_dir,"outputs")) if not f.startswith(".")] if os.path.isdir(os.path.join(a.run_dir,"outputs")) else []
        if files: out=os.path.join(a.run_dir,"outputs",files[0])
        else:
            json.dump({"expectations":[{"text":"output file exists","passed":False,"evidence":"no file in outputs/"}]},open(os.path.join(a.run_dir,"grading.json"),"w"),ensure_ascii=False,indent=1); print("NO OUTPUT"); return
    text=open(out,encoding="utf-8").read()
    args=[sys.executable,CHECK,out,"--json"]
    if c.get("source"): args+=["--source",os.path.join(HERE,c["source"])]
    if c.get("max_words"): args+=["--max-words",str(c["max_words"])]
    if c.get("no_greeting"): args+=["--no-greeting"]
    r=json.loads(subprocess.run(args,capture_output=True,text=True).stdout)
    exp.append({"text":f"check.py score ≥ {c['min_score']}","passed":r["score"]>=c["min_score"],"evidence":f"score {r['score']} (penalty {r['penalty_points']} / {r['words']} words); hits: "+", ".join(f"{k}×{len(v)}" for k,v in r["findings"].items())})
    if c.get("max_words"): exp.append({"text":f"≤ {c['max_words']} words","passed":r["words"]<=c["max_words"],"evidence":f"{r['words']} words"})
    if c.get("source"):
        fn=r["findings"].get("foreign_number",[])
        exp.append({"text":"no numbers absent from the source","passed":len(fn)==0,"evidence":"; ".join(h["hit"]+" @"+h["context"][:50] for h in fn[:6]) or "all numbers traceable"})
    if c.get("no_greeting"):
        g=r["findings"].get("greeting",[]); exp.append({"text":"no greeting","passed":len(g)==0,"evidence":(g[0]["hit"] if g else "none")})
    hard=r["findings"].get("hard",[])
    exp.append({"text":"zero HARD-category hits (AI-tells)","passed":len(hard)==0,"evidence":", ".join(h["hit"] for h in hard[:8]) or "none"})
    if c.get("max_paragraphs"): exp.append({"text":f"≤ {c['max_paragraphs']} paragraphs","passed":r["paragraphs"]<=c["max_paragraphs"],"evidence":f"{r['paragraphs']} paragraphs"})
    if c.get("max_emoji"):
        n=len(re.findall(r"[\U0001F300-\U0001FAFF☀-➿]",text)); exp.append({"text":f"≤ {c['max_emoji']} emoji","passed":n<=c["max_emoji"],"evidence":f"{n} emoji"})
    miss=[s for s in c.get("required",[]) if not has(text,s)]
    exp.append({"text":f"required facts present ({len(c.get('required',[]))})","passed":not miss,"evidence":("missing: "+", ".join(miss)) if miss else "all present"})
    for grp in c.get("required_any",[]):
        ok=any(has(text,s) for s in grp); exp.append({"text":"one of: "+" / ".join(grp),"passed":ok,"evidence":"found" if ok else "none found"})
    found=[s for s in c.get("forbidden",[]) if has(text,s)]
    exp.append({"text":f"forbidden phrases absent ({len(c.get('forbidden',[]))})","passed":not found,"evidence":("found: "+", ".join(found)) if found else "none"})
    if c.get("first_line_any"):
        fl=text.strip().splitlines()[0]; ok=any(has(fl,s) for s in c["first_line_any"]); exp.append({"text":"first line carries the rule: "+" / ".join(c["first_line_any"]),"passed":ok,"evidence":fl[:120]})
    if c.get("last_block_any"):
        tail=text.strip()[-400:]; ok=any(has(tail,s) for s in c["last_block_any"]); exp.append({"text":"ends with the ask ("+" / ".join(c["last_block_any"][:2])+"…)","passed":ok,"evidence":tail[-160:].replace("\n"," ⏎ ")})
    for s in e["assertions"]: exp.append({"text":"[judgment] "+s,"passed":None,"evidence":""})
    mech_ok=sum(1 for x in exp if x["passed"] is True); mech_tot=sum(1 for x in exp if x["passed"] is not None)
    json.dump({"eval_id":e["id"],"eval_name":e["name"],"output_file":out,"score":r["score"],"words":r["words"],"summary":{"passed":mech_ok,"failed":mech_tot-mech_ok,"total":len(exp),"pass_rate":round(mech_ok/len(exp),3),"note":"judgment assertions (passed=null) count as not-yet-passed until filled"},"expectations":exp},open(os.path.join(a.run_dir,"grading.json"),"w"),ensure_ascii=False,indent=1)
    mech=[x for x in exp if x["passed"] is not None]
    print(f"{e['name']}: {sum(1 for x in mech if x['passed'])}/{len(mech)} mechanical · score {r['score']} · {r['words']} words")
    for x in mech:
        if not x["passed"]: print("   ✗",x["text"],"—",x["evidence"][:140])
if __name__=="__main__": main()
