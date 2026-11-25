"""Independent source-derived EX-stage connectivity labels and bounded paths."""
from collections import deque
from scripts.cv32e40p_pr63 import label, PKG, APU
from scripts.run_scalability_pr55 import ALU_FILES

TOP="cv32e40p_ex_stage"
EX_FILE="rtl/cv32e40p_ex_stage.sv"
EX_PINS={EX_FILE:"488a83dc279ca11852c30e1a5d5415d5b377fa1c"}
SOURCES=[PKG,APU,*ALU_FILES[1:],"rtl/cv32e40p_mult.sv",EX_FILE]
INSTANCES={TOP,TOP+".alu_i",TOP+".alu_i.popcnt_i",TOP+".alu_i.ff_one_i",
           TOP+".alu_i.alu_div_i",TOP+".mult_i"}
INPUTS=("clk","rst_n","alu_operand_a_i","alu_operand_b_i","alu_operand_c_i",
        "alu_operator_i","mult_operand_a_i","mult_operand_b_i","mult_operator_i",
        "csr_rdata_i","csr_access_i","lsu_rdata_i","branch_in_ex_i")
OUTPUTS=("regfile_alu_wdata_fw_o","regfile_wdata_wb_o","jump_target_o",
         "branch_decision_o","ex_ready_o","ex_valid_o")

def port(source,target,line,kind="port_input",positive=True):
    return label(source,target,kind,line,"direct named port binding" if positive else
                 "not the signal connected to this named port",positive=positive)

LABELS=[
    port("clk","alu_i.clk",264),
    port("rst_n","alu_i.rst_n",265),
    port("alu_en_i","alu_i.enable_i",266),
    port("alu_operator_i","alu_i.operator_i",267),
    port("alu_operand_a_i","alu_i.operand_a_i",268),
    port("alu_operand_b_i","alu_i.operand_b_i",269),
    port("alu_operand_c_i","alu_i.operand_c_i",270),
    port("alu_i.result_o","alu_result",281,"port_output"),
    port("alu_i.comparison_result_o","alu_cmp_result",282,"port_output"),
    port("alu_i.ready_o","alu_ready",284,"port_output"),
    port("ex_ready_o","alu_i.ex_ready_i",285),
    port("clk","mult_i.clk",299),
    port("rst_n","mult_i.rst_n",300),
    port("mult_en_i","mult_i.enable_i",302),
    port("mult_operator_i","mult_i.operator_i",303),
    port("mult_operand_a_i","mult_i.op_a_i",308),
    port("mult_operand_b_i","mult_i.op_b_i",309),
    port("mult_operand_c_i","mult_i.op_c_i",310),
    port("mult_i.result_o","mult_result",321,"port_output"),
    port("mult_i.ready_o","mult_ready",325,"port_output"),
    port("ex_ready_o","mult_i.ex_ready_i",326),
    label("alu_result","regfile_alu_wdata_fw_o","data",220,"ALU forwarding data"),
    label("mult_result","regfile_alu_wdata_fw_o","data",221,"MUL forwarding data"),
    label("csr_rdata_i","regfile_alu_wdata_fw_o","data",222,"CSR forwarding data"),
    label("alu_en_i","regfile_alu_wdata_fw_o","control",220,"ALU forwarding guard"),
    label("mult_en_i","regfile_alu_wdata_fw_o","control",221,"MUL forwarding guard"),
    label("csr_access_i","regfile_alu_wdata_fw_o","control",222,"CSR forwarding guard"),
    label("lsu_rdata_i","regfile_wdata_wb_o","data",231,"LSU writeback data"),
    label("alu_cmp_result","branch_decision_o","data",250,"direct branch decision"),
    label("alu_operand_c_i","jump_target_o","data",251,"direct jump target"),
    label("regfile_waddr_i","regfile_waddr_lsu","data",461,"EX/WB address NBA",sequential=True),
    label("clk","regfile_waddr_lsu","event",452,"EX/WB clock",sequential=True),
    label("rst_n","regfile_waddr_lsu","event",452,"EX/WB reset",sequential=True),
    label("alu_ready","ex_ready_o","data",474,"ready conjunction"),
    label("mult_ready","ex_ready_o","data",474,"ready conjunction"),
    label("wb_ready_i","ex_ready_o","data",475,"ready conjunction"),
    port("mult_operand_a_i","alu_i.operand_a_i",268,positive=False),
    port("alu_operand_a_i","mult_i.op_a_i",308,positive=False),
    port("alu_i.result_o","mult_result",321,"port_output",False),
    port("mult_i.result_o","alu_result",281,"port_output",False),
    label("alu_operand_a_i","jump_target_o","data",251,"only operand C directly drives jump target",positive=False),
    label("alu_result","branch_decision_o","data",250,"comparison result is separate",positive=False),
    label("lsu_rdata_i","regfile_alu_wdata_fw_o","data",231,"separate writeback port",positive=False),
    label("regfile_waddr_i","regfile_waddr_lsu","data",461,"NBA, not combinational",positive=False),
]

PATHS=(
    ("alu_operand_a_i","regfile_alu_wdata_fw_o"),
    ("alu_operand_b_i","regfile_alu_wdata_fw_o"),
    ("mult_operand_a_i","regfile_alu_wdata_fw_o"),
    ("mult_operand_b_i","regfile_alu_wdata_fw_o"),
    ("alu_operand_a_i","branch_decision_o"),
)

def find_path(graph,source,target,*,max_hops=15,max_visits=5000):
    """Bounded observed data/control/port path, never a functional proof.

    No sequential edges or event edges. No claim of absence when missing.
    """
    if type(max_hops) is not int or not 1<=max_hops<=32 or type(max_visits) is not int or not 1<=max_visits<=10000:
        raise ValueError("invalid path bounds")
    nodes=set(graph["nodes"])
    if source not in nodes or target not in nodes:
        raise ValueError("unknown endpoint")
    adjacency={}
    for e in graph["edges"]:
        if e["sequential"] is False and e["kind"] in ("data","control","port_input","port_output"):
            adjacency.setdefault(e["source"],[]).append(e)
    queue=deque([(source,[])])
    seen={source}
    limited=False
    while queue:
        current,path=queue.popleft()
        if current==target:
            return {"status":"observed","edges":path,"max_hops":max_hops}
        if len(path)>=max_hops:
            limited=limited or bool(adjacency.get(current))
            continue
        for e in adjacency.get(current,[]):
            neighbor=e["target"]
            if neighbor in seen:
                continue
            if len(seen)>=max_visits:
                return {"status":"budget_exhausted","edges":[],"max_hops":max_hops}
            seen.add(neighbor)
            queue.append((neighbor,path+[e]))
    return {"status":"budget_exhausted" if limited else "not_observed",
            "edges":[],"max_hops":max_hops}
