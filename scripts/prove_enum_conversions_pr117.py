"""Binary encoding and fixed-slice model checks; not an RTL equivalence proof."""
import argparse,json,subprocess,tempfile
from pathlib import Path
from rtlprep.enum_conversion_candidates import enum_table


def execute(out):
    out=out.resolve(); out.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix="run-",dir=out)); path=run/"summary.json"
    report={"status":"incomplete","scope":"binary_enum_conversion_models",
            "rtl_equivalence":"not_performed","temporal_proof":"not_performed"}
    def save(): path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    save()
    try:
        report["z3_version"]=subprocess.check_output(["z3","--version"],text=True,timeout=10).strip()
        lines=["(set-logic QF_BV)","(set-option :timeout 10000)","(declare-fun word () (_ BitVec 32))"]
        queries=[]
        for n,codes,explicit in [(4,list(range(15)),False),(2,list(range(4)),False),(3,[0,1,2,3,4],True),(3,[2,5],True)]:
            typ=f"logic[{n-1}:0]"
            members=[]
            for i,v in enumerate(codes):
                entry={"kind":"EnumValue","addr":i+1,"name":f"E{i}","value":f"{n}'b{v:b}"}
                if explicit:
                    entry["initializer"]={"kind":"Conversion","type":typ,
                                          "operand":{"kind":"IntegerLiteral","type":"bit[31:0]","value":f"32'd{v}"}}
                members.append(entry)
            _,_,table=enum_table({"baseType":typ,"members":members})
            for i,((_,actual,_),expected) in enumerate(zip(table.values(),codes)):
                queries.append((f"encoding_{n}_{len(codes)}_{i}",f"(distinct (_ bv{actual} {n}) (_ bv{expected} {n}))","unsat"))
        queries.append(("csr_slice","(distinct (concat ((_ extract 14 14) word) ((_ extract 13 13) word)) ((_ extract 14 13) word))","unsat"))
        queries.extend([("mutant_enum_off_by_one","(distinct #b0010 #b0011)","sat"),
                        ("mutant_swap_csr_bits","(distinct (concat ((_ extract 13 13) word) ((_ extract 14 14) word)) ((_ extract 14 13) word))","sat"),
                        ("mutant_wrong_slice","(distinct ((_ extract 15 14) word) ((_ extract 14 13) word))","sat")])
        for _,expr,_ in queries:
            lines.extend(["(push 1)",f"(assert {expr})","(check-sat)","(pop 1)"])
        smt=run/"models.smt2"; smt.write_text("\n".join(lines+["(exit)"])+"\n")
        p=subprocess.run(["z3","-smt2",str(smt)],capture_output=True,text=True,timeout=120)
        (run/"stdout.log").write_text(p.stdout); (run/"stderr.log").write_text(p.stderr)
        actual=p.stdout.splitlines()
        report["queries"]=[{"name":q[0],"expected":q[2],"actual":actual[i] if i<len(actual) else None} for i,q in enumerate(queries)]
        assert p.returncode==0 and actual==[q[2] for q in queries],(p.stdout,p.stderr)
        report.update(status="passed",query_count=len(queries),unsat=27,sat=3)
        assert len(queries)==30
    except Exception as exc:
        report.update(status="failed",error=f"{type(exc).__name__}: {exc}"[:1000]); raise
    finally:
        save(); print(path.read_text(),flush=True); print(f"Summary: {path}",flush=True)
    return path


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,required=True)
    execute(p.parse_args().out)
