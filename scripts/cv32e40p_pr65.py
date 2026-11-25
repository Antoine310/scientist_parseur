"""Source-pinned whole-core benchmark specification (one integer configuration)."""
from scripts.cv32e40p_pr63 import label, PKG, APU, FPU
from scripts.cv32e40p_pr64 import EX_PINS, find_path

TOP="cv32e40p_core"
CORE_FILE="rtl/cv32e40p_core.sv"
MANIFEST="cv32e40p_manifest.flist"
CLOCK_GATE="bhv/cv32e40p_sim_clock_gate.sv"
CORE_PINS={
    **EX_PINS,
    MANIFEST:"b69ccecd33a629cf18c5cce972eb6e4e31052189",
    CORE_FILE:"4275cf9c13aef1a4517e7696a5fd2a1acd6a996a",
    CLOCK_GATE:"65d2bfefbc6b093f2b14fab1fa326c8f0d298359",
    "rtl/cv32e40p_if_stage.sv":"23fd14f5f0c622dae1fdb34dcb6c4369dd79c0c3",
    "rtl/cv32e40p_cs_registers.sv":"d543179f5fb9dd02383250870becc270ddd2af04",
    "rtl/cv32e40p_load_store_unit.sv":"f9c4db4a85974ae6801b8525b194458e6f9fccad",
    "rtl/cv32e40p_id_stage.sv":"f323cbe5fdb9b2280be5d7e8a0273f1b4d8a03dd",
    "rtl/cv32e40p_aligner.sv":"a61f7e9282cad72fb47093a183cdba2c171fba45",
    "rtl/cv32e40p_fifo.sv":"496ac4ce0048d6b166363abc8c0ec79d32ef8649",
    "rtl/cv32e40p_prefetch_buffer.sv":"596bdfe94f4c74df657235d58d3d41739bd6b306",
    "rtl/cv32e40p_hwloop_regs.sv":"fc835fbe4b509da356cd23e8ccc32a4cf6e9314e",
    "rtl/cv32e40p_int_controller.sv":"af8489e0f5a86bfdf246e6cc1df7b75eefe4694b",
    "rtl/cv32e40p_apu_disp.sv":"94ca9bcbdbded0e1dd5ad518133fcffd20c42952",
    "rtl/cv32e40p_obi_interface.sv":"b44fbeba123f5228a3cf3620dd81b5c0923a6c1f",
    "rtl/cv32e40p_prefetch_controller.sv":"d00406e54fcba2c7025742640ff1719d154ea35f",
    "rtl/cv32e40p_sleep_unit.sv":"03e519487c0f620b39dd4cde0685e15c61723ae8",
}
# Official manifest order, stopping at core (not top/FPU wrapper/tracer).
SOURCES=[APU,FPU,PKG]+["rtl/cv32e40p_"+n+".sv" for n in (
    "if_stage","cs_registers","register_file_ff","load_store_unit","id_stage",
    "aligner","decoder","compressed_decoder","fifo","prefetch_buffer",
    "hwloop_regs","mult","int_controller","ex_stage","alu_div","alu",
    "ff_one","popcnt","apu_disp","controller","obi_interface",
    "prefetch_controller","sleep_unit","core")]+[CLOCK_GATE]
CONFIG={"COREV_PULP":0,"COREV_CLUSTER":0,"FPU":0,"FPU_ADDMUL_LAT":0,
        "FPU_OTHERS_LAT":0,"ZFINX":0,"NUM_MHPMCOUNTERS":1}

# Source-derived active hierarchy in this configuration. Inactive hardware
# loops, PMP and APU dispatcher are not expected instances.
INSTANCE_MODULES={
    "":"cv32e40p_core",
    "sleep_unit_i":"cv32e40p_sleep_unit",
    "sleep_unit_i.core_clock_gate_i":"cv32e40p_clock_gate",
    "if_stage_i":"cv32e40p_if_stage",
    "if_stage_i.aligner_i":"cv32e40p_aligner",
    "if_stage_i.compressed_decoder_i":"cv32e40p_compressed_decoder",
    "if_stage_i.prefetch_buffer_i":"cv32e40p_prefetch_buffer",
    "if_stage_i.prefetch_buffer_i.prefetch_controller_i":"cv32e40p_prefetch_controller",
    "if_stage_i.prefetch_buffer_i.fifo_i":"cv32e40p_fifo",
    "if_stage_i.prefetch_buffer_i.instruction_obi_i":"cv32e40p_obi_interface",
    "id_stage_i":"cv32e40p_id_stage",
    "id_stage_i.register_file_i":"cv32e40p_register_file",
    "id_stage_i.decoder_i":"cv32e40p_decoder",
    "id_stage_i.controller_i":"cv32e40p_controller",
    "id_stage_i.int_controller_i":"cv32e40p_int_controller",
    "ex_stage_i":"cv32e40p_ex_stage",
    "ex_stage_i.alu_i":"cv32e40p_alu",
    "ex_stage_i.alu_i.alu_div_i":"cv32e40p_alu_div",
    "ex_stage_i.alu_i.ff_one_i":"cv32e40p_ff_one",
    "ex_stage_i.alu_i.popcnt_i":"cv32e40p_popcnt",
    "ex_stage_i.mult_i":"cv32e40p_mult",
    "load_store_unit_i":"cv32e40p_load_store_unit",
    "load_store_unit_i.data_obi_i":"cv32e40p_obi_interface",
    "cs_registers_i":"cv32e40p_cs_registers",
}
INPUTS=("clk_i","rst_ni","boot_addr_i","instr_gnt_i","instr_rvalid_i","instr_rdata_i",
        "data_gnt_i","data_rvalid_i","data_rdata_i","irq_i","debug_req_i","fetch_enable_i")
OUTPUTS=("instr_req_o","instr_addr_o","data_req_o","data_we_o","data_be_o",
         "data_addr_o","data_wdata_o","irq_ack_o","irq_id_o","core_sleep_o")

def binding(source,target,line,kind="port_input",positive=True):
    return label(source,target,kind,line,"named connection in pinned core" if positive
                 else "not the named connection for this port",positive=positive)

LABELS=[
    binding("clk_i","sleep_unit_i.clk_ungated_i",386),
    binding("rst_ni","sleep_unit_i.rst_n",387),
    binding("sleep_unit_i.clk_gated_o","clk",388,"port_output"),
    binding("sleep_unit_i.core_sleep_o","core_sleep_o",392,"port_output"),
    binding("fetch_enable_i","sleep_unit_i.fetch_enable_i",395),
    binding("clk","if_stage_i.clk",430),
    binding("rst_ni","if_stage_i.rst_n",431),
    binding("boot_addr_i","if_stage_i.boot_addr_i",434),
    binding("if_stage_i.instr_req_o","instr_req_pmp",449,"port_output"),
    binding("if_stage_i.instr_addr_o","instr_addr_pmp",450,"port_output"),
    binding("instr_rdata_i","if_stage_i.instr_rdata_i",453),
    binding("if_stage_i.instr_rdata_id_o","instr_rdata_id",459,"port_output"),
    binding("jump_target_ex","if_stage_i.jump_target_ex_i",493),
    binding("instr_rdata_id","id_stage_i.instr_rdata_i",543),
    binding("branch_decision","id_stage_i.branch_decision_i",548),
    binding("id_stage_i.alu_operator_ex_o","alu_operator_ex",581,"port_output"),
    binding("id_stage_i.alu_operand_a_ex_o","alu_operand_a_ex",582,"port_output"),
    binding("id_stage_i.alu_operand_b_ex_o","alu_operand_b_ex",583,"port_output"),
    binding("irq_i","id_stage_i.irq_i",680),
    binding("debug_req_i","id_stage_i.debug_req_i",693),
    binding("regfile_alu_wdata_fw","id_stage_i.regfile_alu_wdata_fw_i",715),
    binding("alu_operand_a_ex","ex_stage_i.alu_operand_a_i",761),
    binding("alu_operand_b_ex","ex_stage_i.alu_operand_b_i",762),
    binding("lsu_rdata","ex_stage_i.lsu_rdata_i",836),
    binding("csr_rdata","ex_stage_i.csr_rdata_i",840),
    binding("ex_stage_i.jump_target_o","jump_target_ex",857,"port_output"),
    binding("ex_stage_i.branch_decision_o","branch_decision",858,"port_output"),
    binding("ex_stage_i.regfile_alu_wdata_fw_o","regfile_alu_wdata_fw",864,"port_output"),
    binding("load_store_unit_i.data_req_o","data_req_pmp",893,"port_output"),
    binding("load_store_unit_i.data_addr_o","data_addr_pmp",899,"port_output"),
    binding("load_store_unit_i.data_wdata_o","data_wdata_o",903,"port_output"),
    binding("data_rdata_i","load_store_unit_i.data_rdata_i",904),
    binding("load_store_unit_i.data_rdata_ex_o","lsu_rdata",915,"port_output"),
    binding("csr_wdata","cs_registers_i.csr_wdata_i",976),
    binding("cs_registers_i.csr_rdata_o","csr_rdata",978,"port_output"),
    label("instr_req_pmp","instr_req_o","data",1108,"PMP-disabled direct wiring"),
    label("instr_addr_pmp","instr_addr_o","data",1109,"PMP-disabled direct wiring"),
    label("data_req_pmp","data_req_o","data",1113,"PMP-disabled direct wiring"),
    label("data_addr_pmp","data_addr_o","data",1114,"PMP-disabled direct wiring"),
    binding("data_rdata_i","if_stage_i.instr_rdata_i",453,positive=False),
    binding("instr_rdata_i","load_store_unit_i.data_rdata_i",904,positive=False),
    binding("alu_operand_b_ex","ex_stage_i.alu_operand_a_i",761,positive=False),
    binding("alu_operand_a_ex","ex_stage_i.alu_operand_b_i",762,positive=False),
    binding("ex_stage_i.jump_target_o","branch_decision",858,"port_output",False),
    binding("ex_stage_i.branch_decision_o","jump_target_ex",857,"port_output",False),
    label("data_addr_pmp","instr_addr_o","data",1109,"separate bus",positive=False),
    label("instr_addr_pmp","data_addr_o","data",1114,"separate bus",positive=False),
]

# Diagnostic probes: no assertion that all paths must be observed.
# Combinational probes intentionally stop at sequential edges.
PATHS=[
    ("id_stage_i.alu_operand_a_ex_o","id_stage_i.regfile_alu_wdata_fw_i"),
    ("id_stage_i.alu_operand_b_ex_o","id_stage_i.regfile_alu_wdata_fw_i"),
    ("id_stage_i.alu_operand_c_ex_o","if_stage_i.jump_target_ex_i"),
    ("data_rdata_i","ex_stage_i.lsu_rdata_i"),
    ("if_stage_i.prefetch_buffer_i.instruction_obi_i.obi_addr_o","instr_addr_o"),
    ("load_store_unit_i.data_obi_i.obi_addr_o","data_addr_o"),
    ("cs_registers_i.csr_rdata_o","id_stage_i.regfile_alu_wdata_fw_i"),
]

def check_manifest(text):
    """Confirm the reviewed source list against the pinned upstream flist."""
    prefix="${DESIGN_RTL_DIR}/"
    listed=[]
    for raw in text.splitlines():
        line=raw.strip()
        if line.startswith(prefix):
            rel=line[len(prefix):]
            if rel=="cv32e40p_top.sv":
                break
            listed.append("rtl/"+rel)
    if listed!=SOURCES[:-1] or prefix+"../"+CLOCK_GATE not in text.splitlines():
        raise ValueError("official source inventory differs from reviewed core subset")
    return list(SOURCES)
