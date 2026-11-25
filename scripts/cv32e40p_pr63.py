"""Pinned CV32E40P multi-unit source inventory and independent signal labels.

The additional blob pins are scoped to PR63; the existing fixture lock
and the sparse official checkout are not changed.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import os
import subprocess

from scripts.rtl_fixtures import git, FixtureError

COMMIT="b353438ff469c030c89f6804f3b24a2852880e8b"
PKG="rtl/include/cv32e40p_pkg.sv"
APU="rtl/include/cv32e40p_apu_core_pkg.sv"
FPU="rtl/include/cv32e40p_fpu_pkg.sv"
EXTRA_BLOBS={
    APU:"26cb42fa9269d4429ea24a78e2f94b748ac62eb1",
    FPU:"fe24153258d6a4cf06c514889df5773d72ce8cb4",
    "rtl/cv32e40p_decoder.sv":"c1608eb4a648dafb2e500c6eb55ee4251cd766d8",
    "rtl/cv32e40p_register_file_ff.sv":"4d31c1277552ade8ec162869975645925d5ddb12",
    "rtl/cv32e40p_mult.sv":"afdc5e2fcad69762855d4605936c751de35a7e5d",
    "rtl/cv32e40p_controller.sv":"d1c86d6c849e0cc4f41899f0db091866a1ed69ff",
}
MAX_BLOB_BYTES=2*1024*1024

def blob_bytes(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def materialize(upstream,destination,entry,*,additional_pins=None):
    """Copy exact Git blob bytes into a fresh report-local snapshot.

    No checkout, fetch, sparse-checkout changes, or text normalization.
    verify_checkout is called by the runner before and after this step.
    """
    if entry["commit"]!=COMMIT or entry["repository"]!="openhwfoundation/cv32e40p":
        raise FixtureError("unexpected CV32E40P lock identity")
    pins=dict(entry["blobs"])
    if set(pins)&set(EXTRA_BLOBS):
        raise FixtureError("PR63 extra pins overlap existing lock")
    pins.update(EXTRA_BLOBS)
    if additional_pins:
        if set(pins)&set(additional_pins):
            raise FixtureError("additional pins overlap existing pins")
        import re
        from pathlib import PurePosixPath
        for name,sha in additional_pins.items():
            p=PurePosixPath(name)
            if (p.is_absolute() or str(p)!=name or not p.parts or
                    any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part) for part in p.parts)
                    or not re.fullmatch(r"[0-9a-f]{40}",sha)):
                raise FixtureError("unsafe additional pin")
        pins.update(additional_pins)
    destination.mkdir(parents=False,exist_ok=False)
    env=dict(os.environ,GIT_OPTIONAL_LOCKS="0",GIT_TERMINAL_PROMPT="0",GIT_NO_LAZY_FETCH="1")
    for key in ("GIT_DIR","GIT_WORK_TREE","GIT_INDEX_FILE","GIT_COMMON_DIR"):
        env.pop(key,None)
    for relative,sha in sorted(pins.items()):
        if git(upstream,"rev-parse",COMMIT+":"+relative)!=sha:
            raise FixtureError("tree blob mismatch: "+relative)
        size=int(git(upstream,"cat-file","-s",sha))
        if not 0<size<=MAX_BLOB_BYTES:
            raise FixtureError("source blob outside size budget: "+relative)
        proc=subprocess.run(["git","-C",str(upstream),"cat-file","blob",sha],
                            env=env,capture_output=True,timeout=30,check=False)
        if proc.returncode or len(proc.stdout)!=size or blob_bytes(proc.stdout)!=sha:
            raise FixtureError("missing or invalid source blob: "+relative)
        target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(proc.stdout)
    return pins

REGFILE_WRAPPER="""module regfile_pr63 (
  input logic clk, rst_n, scan_cg_en_i,
  input logic [5:0] raddr_a_i, raddr_b_i, raddr_c_i,
  output logic [31:0] rdata_a_o, rdata_b_o, rdata_c_o,
  input logic [5:0] waddr_a_i, waddr_b_i,
  input logic [31:0] wdata_a_i, wdata_b_i,
  input logic we_a_i, we_b_i
);
  cv32e40p_register_file #(.ADDR_WIDTH(6), .DATA_WIDTH(32), .FPU(0), .ZFINX(0)) rf (
    .clk(clk), .rst_n(rst_n), .scan_cg_en_i(scan_cg_en_i),
    .raddr_a_i(raddr_a_i), .raddr_b_i(raddr_b_i), .raddr_c_i(raddr_c_i),
    .rdata_a_o(rdata_a_o), .rdata_b_o(rdata_b_o), .rdata_c_o(rdata_c_o),
    .waddr_a_i(waddr_a_i), .waddr_b_i(waddr_b_i),
    .wdata_a_i(wdata_a_i), .wdata_b_i(wdata_b_i), .we_a_i(we_a_i), .we_b_i(we_b_i)
  );
endmodule
"""

def label(source,target,kind,line,note,*,sequential=False,positive=True):
    return {"source":source,"target":target,"kind":kind,"sequential":sequential,
            "label":"positive" if positive else "negative","line":line,"note":note}

# Labels concern direct syntactic signal links, not transitive influence.
# Negative candidates are deliberately limited to the listed assignments'
# unique targets (or distinct kind / sequential flag), not absent edges
# inferred by running the extractor.
CASES={
    "compressed_decoder":{
        "top":"cv32e40p_compressed_decoder","file":"rtl/cv32e40p_compressed_decoder.sv",
        "sources":[PKG,"rtl/cv32e40p_compressed_decoder.sv"],"owner":"",
        "inputs":["instr_i"],"outputs":["instr_o","is_compressed_o","illegal_instr_o"],
        "labels":[label("instr_i","is_compressed_o","data",599,"comparison of instruction low bits"),
                  label("instr_i","is_compressed_o","control",599,"comparison is a data expression, not a branch",positive=False),
                  label("instr_i","is_compressed_o","data",599,"continuous assignment, not sequential",sequential=True,positive=False)]},
    "decoder":{
        "top":"cv32e40p_decoder","file":"rtl/cv32e40p_decoder.sv",
        "sources":[PKG,APU,FPU,"rtl/cv32e40p_decoder.sv"],"owner":"",
        "inputs":["instr_rdata_i","deassert_we_i"],"outputs":["alu_en_o","regfile_alu_we_o","data_req_o"],
        "labels":[label("deassert_we_i","alu_en_o","control",2997,"write suppression mux selector"),
                  label("alu_en","alu_en_o","data",2997,"mux data arm"),
                  label("deassert_we_i","regfile_alu_we_o","control",3002,"write suppression mux selector"),
                  label("regfile_alu_we","regfile_alu_we_o","data",3002,"mux data arm"),
                  label("data_req","data_req_o","data",3003,"mux data arm"),
                  label("deassert_we_i","data_req_o","control",3003,"write suppression mux selector"),
                  label("instr_rdata_i","alu_en_o","data",2997,"instruction influence is not a direct read in this assignment",positive=False),
                  label("deassert_we_i","alu_en_o","data",2997,"selector rather than data arm",positive=False)]},
    "register_file":{
        "top":"regfile_pr63","file":"rtl/cv32e40p_register_file_ff.sv",
        "sources":["rtl/cv32e40p_register_file_ff.sv"],"owner":"rf.",
        "inputs":["clk","rst_n","raddr_a_i","wdata_a_i","wdata_b_i"],"outputs":["rdata_a_o","rdata_b_o","rdata_c_o"],
        "labels":[label("mem","rdata_a_o","data",89,"integer register read"),
                  label("raddr_a_i","rdata_a_o","data",89,"dynamic element selector"),
                  label("raddr_a_i","rdata_a_o","control",89,"bank mux selector"),
                  label("mem_fp","rdata_a_o","data",89,"FP-bank syntax retained even when disabled"),
                  label("wdata_b_i","mem","data",133,"B-port write",sequential=True),
                  label("wdata_a_i","mem","data",134,"A-port write",sequential=True),
                  label("clk","mem","event",129,"clock event",sequential=True),
                  label("rst_n","mem","event",129,"reset event",sequential=True),
                  label("wdata_a_i","rdata_a_o","data",89,"no direct write-data to read-output edge",positive=False),
                  label("raddr_b_i","rdata_a_o","data",89,"different read port",positive=False)]},
    "multiplier":{
        "top":"cv32e40p_mult","file":"rtl/cv32e40p_mult.sv",
        "sources":[PKG,"rtl/cv32e40p_mult.sv"],"owner":"",
        "inputs":["clk","rst_n","op_a_i","op_b_i","operator_i"],"outputs":["result_o","ready_o"],
        "labels":[label("imm_i","short_round_tmp","data",98,"shift amount"),
                  label("operator_i","short_round","control",99,"rounding mux"),
                  label("short_round_tmp","short_round","data",99,"selected rounding bits"),
                  label("op_a_i","short_op_a","data",102,"subword data"),
                  label("short_subword","short_op_a","control",102,"subword selector"),
                  label("short_signed","short_op_a","data",105,"sign-extension bit"),
                  label("mulh_ready","ready_o","data",350,"direct ready assignment"),
                  label("op_b_i","short_op_a","data",102,"other operand absent from both writes",positive=False),
                  label("operator_i","ready_o","data",350,"not a direct read",positive=False)]},
    "controller":{
        "top":"cv32e40p_controller","file":"rtl/cv32e40p_controller.sv",
        "sources":[PKG,"rtl/cv32e40p_controller.sv"],"owner":"",
        "inputs":["clk","rst_n","data_misaligned_i","apu_read_dep_i"],"outputs":["misaligned_stall_o","apu_stall_o","debug_mode_o"],
        "labels":[label("data_misaligned_i","misaligned_stall_o","data",1387,"direct stall assignment"),
                  label("apu_read_dep_i","apu_stall_o","data",1390,"OR operand"),
                  label("apu_write_dep_i","apu_stall_o","data",1390,"AND operand"),
                  label("apu_en_i","apu_stall_o","data",1390,"negated AND operand"),
                  label("debug_mode_q","debug_mode_o","data",1469,"direct debug state output"),
                  label("apu_en_i","misaligned_stall_o","data",1387,"unrelated stall input",positive=False),
                  label("debug_req_i","debug_mode_o","data",1469,"not a direct read",positive=False)]},
}
