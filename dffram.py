#!/usr/bin/env python3
# -*- coding: utf8 -*-
# Copyright ©2020-2021 The American University in Cairo and the Cloud V Project.
#
# This file is part of the DFFRAM Memory Compiler.
# See https://github.com/Cloud-V/DFFRAM for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os

try:
    import click
    import yaml
except ImportError:
    print("You need to install click and pyyaml: python3 -m pip install click pyyaml")
    exit(os.EX_CONFIG)

import re
import sys
import math
import time
import pathlib
import textwrap
import traceback
import subprocess

from scripts.python import sky130_hd_hack

def rp(path):
    return os.path.realpath(path)

def ensure_dir(path):
    return pathlib.Path(path).mkdir(parents=True, exist_ok=True)

# --

build_folder =""
pdk = ""
scl = ""
pdk_root = ""
pdk_tech_dir = ""
pdk_ref_dir = ""
pdk_liberty_dir = ""
pdk_lef_dir = ""
pdk_tlef_dir = ""
pdk_klayout_dir = ""
pdk_magic_dir = ""
pdk_openlane_dir = ""

def run_docker(image, args):
    global command_list
    cmd = [
        "docker", "run", "--rm",
        "-v",  f"{pdk_root}:{pdk_root}",
        "-v", f"{rp('.')}:/mnt/dffram",
        "-w", "/mnt/dffram",
        "-e", f"PDK_ROOT={pdk_root}",
        "-e", f"PDKPATH={pdk_root}/{pdk}",
        "-e", "LC_ALL=en_US.UTF-8",
        "-e", "LANG=en_US.UTF-8"
    ] + [image] + args
    command_list.append(cmd)
    subprocess.run(cmd, check=True)

def openlane(*args_tuple):
    args = list(args_tuple)
    run_docker("efabless/openlane:2021.10.25_20.35.00", args)

def prep(local_pdk_root):
    global pdk, scl
    global pdk_root, pdk_tech_dir, pdk_ref_dir
    global  pdk_liberty_dir, pdk_lef_dir, pdk_tlef_dir
    global pdk_klayout_dir, pdk_magic_dir, pdk_openlane_dir
    pdk_root = os.path.abspath(local_pdk_root)
    pdk_tech_dir = os.path.join(pdk_root, pdk, 'libs.tech')
    pdk_ref_dir = os.path.join(pdk_root, pdk, 'libs.ref')
    pdk_liberty_dir = os.path.join(pdk_ref_dir, scl, 'lib')
    pdk_lef_dir = os.path.join(pdk_ref_dir, scl, 'lef')
    pdk_tlef_dir = os.path.join(pdk_ref_dir, scl, 'techlef')
    pdk_openlane_dir = os.path.join(pdk_tech_dir, 'openlane')
    pdk_klayout_dir = os.path.join(pdk_tech_dir, 'klayout')
    pdk_magic_dir = os.path.join(pdk_tech_dir, 'magic')
    openlane(
        "openroad", "-python", "/openlane/scripts/mergeLef.py",
        "-i", f"{pdk_tlef_dir}/{scl}.tlef", f"{pdk_lef_dir}/{scl}.lef",
        "-o", f"{build_folder}/merged.lef"
    )
    if pdk == "sky130A":
        pathlib.Path(f"{build_folder}/route_only").mkdir(parents=True, exist_ok=True)
        sky130_hd_hack.process_lefs(lef=f"{build_folder}/merged.lef", output_cells=f"{build_folder}/route_only/merged.lef")

command_list = []
def cl():
    with open("./command_list.log", "w") as f:
        f.write("\n".join([" ".join(cmd) for cmd in command_list]))

def sta(design, netlist, synth_info, clk_period=3, spef_file=None):
    print("--- Static Timing Analysis ---")
    with open(f"{build_folder}/sta.tcl", 'w') as f:
        spef_var = f"""
        set ::env(opensta_report_file_tag) {netlist}.sta
        """
        if spef_file:
            spef_var = f"""
            set ::env(CURRENT_SPEF) {spef_file}
            set ::env(opensta_report_file_tag) {spef_file}.sta
            """
            

        env_vars = f"""
            set ::env(SCRIPTS_DIR) /openlane/scripts
            set ::env(PDK) "sky130A"
            set ::env(STD_CELL_LIBRARY) "sky130_fd_sc_hd"
            set ::env(STD_CELL_LIBRARY_OPT) "sky130_fd_sc_hd"
            source "/openlane/configuration/synthesis.tcl"
            source "{pdk_openlane_dir}/config.tcl"
            set ::env(ESTIMATE_PL_PARASITICS) 1
            set ::env(MERGED_LEF_UNPADDED) {build_folder}/merged.lef
            set ::env(SYNTH_DRIVING_CELL) "{synth_info['sta_driving_cell']}"
            set ::env(SYNTH_DRIVING_CELL_PIN) "{synth_info['sta_driving_cell_pin']}"
            set ::env(SYNTH_CAP_LOAD) "17.65"
            set ::env(IO_PCT) 0.2
            set ::env(SYNTH_MAX_FANOUT) 5
            set ::env(CLOCK_PORT) "CLK"
            set ::env(CLOCK_PERIOD) "{clk_period}"
            set ::env(LIB_FASTEST) {pdk_liberty_dir}/{synth_info['fast']}
            set ::env(LIB_SLOWEST) {pdk_liberty_dir}/{synth_info['slow']}
            set ::env(LIB_SYNTH_COMPLETE) {pdk_liberty_dir}/{synth_info['typical']}
            set ::env(CURRENT_NETLIST) {netlist}
            set ::env(DESIGN_NAME) {design}
            set ::env(CURRENT_SDC) /openlane/scripts/base.sdc
            {spef_var}
            set ::env(CURRENT_DEF) 0
            source "/openlane/scripts/openroad/or_sta.tcl"
        """
        f.write(env_vars)
    openlane("openroad", "-exit", f"{build_folder}/sta.tcl")

# Not true synthesis, just elaboration.
def synthesis(design, building_blocks, synth_info, widths_supported, word_width_bytes, out_file):
    print("--- Synthesis ---")
    chparam = ""
    if len(widths_supported) > 1:
        chparam = "catch { chparam -set WSIZE %i %s }" % (word_width_bytes, design)
    with open(f"{build_folder}/synth.tcl", 'w') as f:
        f.write(f"""
        yosys -import
        set vtop {design}
        set SCL $env(LIBERTY)
        read_liberty -lib -ignore_miss_dir -setattr blackbox $SCL
        read_verilog {building_blocks}
        {chparam}
        hierarchy -check -top {design}
        synth -top {design} -flatten
        opt_clean -purge
        splitnets
        opt_clean -purge
        write_verilog -noattr -noexpr -nodec {out_file}
        stat -top {design} -liberty $SCL
        exit
        """)

    with open(f"{build_folder}/synth.sh", 'w') as f:
        f.write(f"""
        export LIBERTY={pdk_liberty_dir}/{synth_info['typical']}
        yosys {build_folder}/synth.tcl
        """)

    openlane("bash", f"{build_folder}/synth.sh")

last_def = None
def floorplan(design, synth_info, wmargin, hmargin, width, height, in_file, out_file):
    global last_def
    print("--- Floorplan ---")
    full_width = width + (wmargin * 2)
    full_height = height + (hmargin * 2)

    wpm = width + wmargin
    hpm = height + hmargin

    track_file = f"{build_folder}/tracks.tcl"

    with open(f"{build_folder}/fp_init.tcl", 'w') as f:
        f.write(f"""
        read_liberty {pdk_liberty_dir}/{synth_info['typical']}
        read_lef {build_folder}/merged.lef
        read_verilog {in_file}
        link_design {design}
        initialize_floorplan\\
            -die_area "0 0 {full_width} {full_height}"\\
            -core_area "{wmargin} {hmargin} {wpm} {hpm}"\\
            -site unithd
        source {track_file}
        write_def {out_file}
        """)

    with open(f"{build_folder}/fp_init.sh", 'w') as f:
        f.write(f"""
        set -e

        python3 /openlane/scripts/new_tracks.py -i {pdk_openlane_dir}/{scl}/tracks.info -o {track_file}
        openroad {build_folder}/fp_init.tcl
        """)

    openlane("bash", f"{build_folder}/fp_init.sh")
    last_def = out_file


def placeram(in_file, out_file, size, building_blocks, dimensions=os.devnull, density=os.devnull, represent=os.devnull):
    global last_def
    print("--- placeRAM Script ---")
    unaltered = out_file + ".ref"

    openlane(
        "openroad", "-python", "-m", "placeram",
        "--output", unaltered,
        "--tech-lef", f"{pdk_tlef_dir}/{scl}.tlef",
        "--lef", f"{pdk_lef_dir}/{scl}.lef",
        "--size", size,
        "--write-dimensions", dimensions,
        "--write-density", density,
        "--represent", represent,
        "--building-blocks", building_blocks,
        in_file
    )

    unaltered_str = open(unaltered).read()

    altered_str = re.sub(r"\+ PORT", "", unaltered_str)

    with open(out_file, 'w') as f:
        f.write(altered_str)

    last_def = out_file


def place_pins(design, synth_info, in_file, out_file, pin_order_file):
    global last_def
    print("--- Pin Placement ---")

    if os.getenv("OR_PIN_PLACE") == "1":
        with open(f"{build_folder}/place_pins.tcl", "w") as f:
            f.write(f"""
            read_liberty {pdk_liberty_dir}/{synth_info['typical']}
            read_lef {build_folder}/merged.lef
            read_def {in_file}
            place_pins -ver_layers met2 -hor_layers met3
            write_def {out_file}
            """)

        openlane("openroad", f"{build_folder}/place_pins.tcl")
    else:
        openlane(
            "openroad", "-python",
            "/openlane/scripts/io_place.py",
            "--input-lef", f"{build_folder}/merged.lef",
            "--input-def", in_file,
            "--config", pin_order_file,
            "--hor-layer", "4",
            "--ver-layer", "3",
            "--ver-width-mult", "1",
            "--hor-width-mult", "1",
            "--hor-extension", "-1",
            "--ver-extension", "-1",
            "--length", "2",
            "-o", out_file
        )

    last_def = out_file

def verify_placement(design, synth_info, in_file):
    print("--- Verify ---")
    with open(f"{build_folder}/verify.tcl", 'w') as f:
        f.write(f"""
        read_liberty {pdk_liberty_dir}/{synth_info['typical']}
        read_lef {build_folder}/merged.lef
        read_def {in_file}
        if [check_placement -verbose] {{
            puts "Placement failed: Check placement returned a nonzero value."
            exit 65
        }}
        puts "Placement successful."
        """)
    openlane("openroad", f"{build_folder}/verify.tcl")

def create_image(in_file, width=256,height=256):
    print("--- Create Image ---")
    openlane(
        "bash",
        "xvfb-run", "-a", "klayout", "-z",
        "-rd", f"input_layout={in_file}",
        "-rd", f"extra_lefs={build_folder}/merged.lef",
        "-rd", f"tech_file={pdk_klayout_dir}/{pdk}.lyt",
        "-rd", f"width={width}",
        "-rd", f"height={height}",
        "-rm", "./scripts/klayout/scrot_layout.py"
    )
    return in_file + ".png"

def pdngen(width, height, in_file, out_file):
    global last_def
    print("--- Power Distribution Network Construction ---")
    pitch = 50 # temp: till we arrive at a function that takes in width
    offset = 25 # temp: till we arrive at a function that takes in width
    pdn_cfg = f"""

    set ::halo 0
    # POWER or GROUND #Std. cell rails starting with power or ground rails at the bottom of the core area
    set ::rails_start_with "POWER" ;

    # POWER or GROUND #Upper metal stripes starting with power or ground rails at the left/bottom of the core area
    set ::stripes_start_with "POWER" ;

    set ::power_nets "VPWR";
    set ::ground_nets "VGND";

    set pdngen::global_connections {{
      VPWR {{
        {{inst_name .* pin_name VPWR}}
        {{inst_name .* pin_name VPB}}
      }}
      VGND {{
        {{inst_name .* pin_name VGND}}
        {{inst_name .* pin_name VNB}}
      }}
    }}

    pdngen::specify_grid stdcell {{
        name grid
        rails {{
            met1 {{width 0.17 pitch 2.7 offset 0}}
        }}
        straps {{
            met4 {{width 1.6 pitch {pitch} offset {offset}}}
        }}
        connect {{
        {{ met1 met4 }}
        }}
        pins {{ met4 }}
    }}

    set pdngen::voltage_domains {{ CORE {{ primary_power VPWR primary_ground VGND }} }}
    """

    pdn_cfg_file = f"{build_folder}/pdn.cfg"
    with open(pdn_cfg_file, 'w') as f:
        f.write(pdn_cfg)

    pdn_tcl = f"""
    read_lef {build_folder}/merged.lef

    read_def {in_file}

    pdngen {pdn_cfg_file} -verbose

    write_def {out_file}
    """

    with open(f"{build_folder}/pdn.tcl", 'w') as f:
        f.write(pdn_tcl)
    openlane("openroad", f"{build_folder}/pdn.tcl")

def obs_route(metal_layer, width, height, wmargin, hmargin, in_file, out_file):
    global last_def
    print("--- Routing Obstruction Creation---")

    full_width = width + 2 * wmargin
    full_height = height + 2 * hmargin

    openlane(
        "openroad", "-python",
        "/openlane/scripts/add_def_obstructions.py",
        "--lef", f"{build_folder}/merged.lef",
        "--input-def", in_file,
        "--obstructions",
        f"met{metal_layer} 0 0 {full_width} {full_height}",
        "--output", out_file)
    last_def = out_file

def route(synth_info, in_file, out_file):
    global last_def
    print("--- Route ---")
    global_route_guide = f"{build_folder}/gr.guide"

    with open(f"{build_folder}/route.tcl", 'w') as f:
        f.write(f"""
        source ./platforms/{pdk}/{scl}/openroad.vars
        read_liberty {pdk_liberty_dir}/{synth_info['typical']}
        read_lef {build_folder}/route_only/merged.lef
        read_def {in_file}
        set tech [[ord::get_db] getTech]
        set grt_min_layer [[$tech findRoutingLayer $grt_min_layer_no] getName]
        set grt_max_layer [[$tech findRoutingLayer $grt_max_layer_no] getName]
        set grt_clk_min_layer [[$tech findRoutingLayer $grt_clk_min_layer_no] getName]
        set grt_clk_max_layer [[$tech findRoutingLayer $grt_clk_max_layer_no] getName]
        foreach layer_adjustment $global_routing_layer_adjustments {{
            lassign $layer_adjustment layer adjustment
            set_global_routing_layer_adjustment $layer $adjustment
        }}
        set_routing_layers\\
            -signal $grt_min_layer-$grt_max_layer\\
            -clock $grt_min_layer-$grt_max_layer
        global_route \\
            -guide_file {global_route_guide} \\
            -congestion_iterations 64\\
            -allow_congestion
        set_thread_count {os.getenv("ROUTING_CORES") or '2'}
        detailed_route \\
            -guide {global_route_guide} \\
            -output_guide {build_folder}/dr.guide \\
            -output_drc {build_folder}/dr.drc \\
            -or_seed 70\\
            -verbose 1
        write_def {out_file}
        """)

    openlane("openroad", f"{build_folder}/route.tcl")
    last_def = out_file

def spef_extract(def_file, spef_file=None):
    print("--- Extract SPEF ---")
    openlane("openroad", "-python", "/openlane/scripts/spef_extractor/main.py",
            "--def_file", def_file,
            "--lef_file", f"{build_folder}/merged.lef",
            "--wire_model", "L",
            "--edge_cap_factor", "1")

def add_pwr_gnd_pins(original_netlist,
        def_file, intermediate_file, out_file1,
        out_file2):
    global last_def
    print("--- Adding power and ground pins to netlist ---")

    openlane("openroad", "-python", "/openlane/scripts/write_powered_def.py",
            "-d", def_file,
            "-l", f"{build_folder}/merged.lef",
            "--power-port", "VPWR",
            "--ground-port", "VGND",
            "-o", intermediate_file)

    with open(f"{build_folder}/write_pwr_gnd_verilog.tcl", "w") as f:
        f.write(f"""
        read_lef {build_folder}/merged.lef
        read_def {intermediate_file}
        read_verilog {original_netlist}
        puts "Writing the modified nl.v "
        puts "writing file"
        puts {out_file1}
        write_verilog -include_pwr_gnd {out_file1}
        """)

    openlane("openroad",
            f"{build_folder}/write_pwr_gnd_verilog.tcl")

    with open(f"{build_folder}/rewrite_netlist.tcl", 'w') as f:
        f.write(f"""
        yosys -import
        read_verilog {out_file1}; # usually from openroad
        write_verilog -noattr -noexpr -nohex -nodec {out_file2};
        """)

    openlane("yosys", "-c", f"{build_folder}/rewrite_netlist.tcl")
    last_def = out_file2


def write_ram_lef(design, in_file, out_file):
    print("--- Write LEF view of the RAM Module ---")
    with open(f"{build_folder}/write_lef.tcl", "w") as f:
        f.write(f"""
        puts "Running magic script…"
        lef read {build_folder}/merged.lef
        def read {in_file}
        load {design} -dereference
        lef write {out_file} -hide
        """)

    openlane("magic",
            "-dnull",
            "-noconsole",
            "-rcfile",
            f"{pdk_magic_dir}/{pdk}.magicrc",
            f"{build_folder}/write_lef.tcl")

def write_ram_lib(design, netlist, libfile):
    print("--- Write LIB view of the RAM Module ---")
    openlane("perl",
            "./scripts/perl/verilog_to_lib.pl",
            design,
            netlist,
            libfile)

def magic_drc(design, def_file):
    print("--- Magic DRC ---")
    with open(f"{build_folder}/drc.tcl", "w") as f:
        f.write(f"""
            set ::env(MAGIC_DRC_USE_GDS) 0
            set ::env(TECH_LEF) {pdk_tlef_dir}/{scl}.tlef
            set ::env(magic_report_file_tag) {def_file}
            set ::env(magic_result_file_tag) {def_file}
            set ::env(CURRENT_DEF) {def_file}
            set ::env(DESIGN_NAME) {design}
            source /openlane/scripts/magic/drc.tcl
        """)
    openlane("magic",
            "-dnull",
            "-noconsole",
            "-rcfile",
            f"{pdk_magic_dir}/{pdk}.magicrc",
            f"{build_folder}/drc.tcl")
    drc_report = "%s.drc" % def_file
    drc_report_str = open(drc_report).read()
    count = r"COUNT:\s*(\d+)"
    errors = 0
    count_match = re.search(count, drc_report_str)
    if count_match is not None:
        errors = int(count_match[1])
    if errors != 0:
        print("Error: There are %i DRC errors. Check %s." % (errors, drc_report))
        exit(os.EX_DATAERR)

def lvs(design, in_1, in_2, report):
    print("--- LVS ---")
    with open(f"{build_folder}/lvs.tcl", "w") as f:
        f.write(f"""
        puts "Running magic script…"
        lef read {build_folder}/merged.lef
        def read {in_1}
        load {design} -dereference
        extract do local
        extract no capacitance
        extract no coupling
        extract no resistance
        extract no adjust
        extract unique
        extract
        ext2spice lvs
        ext2spice
        """)

    with open(f"{build_folder}/lvs.sh", "w") as f:
        f.write(f"""
        set +e
        magic -rcfile {pdk_magic_dir}/{pdk}.magicrc -noconsole -dnull < {build_folder}/lvs.tcl
        mv *.ext *.spice {build_folder}
        netgen -batch lvs "{build_folder}/{design}.spice {design}" "{in_2} {design}" -full
        mv comp.out {report}
        """)

    openlane("bash", f"{build_folder}/lvs.sh")

def antenna_check(def_file, out_file):
    # using openroad antenna check
    print("--- Antenna Check ---")
    with open(f"{build_folder}/antenna_check.tcl", 'w') as f:
        f.write(f"""
        set ::env(REPORTS_DIR) {build_folder}
        set ::env(MERGED_LEF_UNPADDED) {build_folder}/merged.lef
        set ::env(CURRENT_DEF) {def_file}
        read_lef $::env(MERGED_LEF_UNPADDED)
        read_def -order_wires {def_file}
        check_antennas -report_file {out_file}
        # source /openlane/scripts/openroad/or_antenna_check.tcl
        """)
    openlane("openroad", f"{build_folder}/antenna_check.tcl")

    antenna_report_str = open(out_file).read()
    net = ""
    cell = ""

    issues = []
    for line in antenna_report_str.split("\n"):
        if "Net" in line:
            net = line
        elif scl in line:
            cell = line
        elif "*" in line:
            issues.append(f"{net}\n{cell}\n{line}")
    issue_count = len(issues)
    print(f"Antenna Report Summary: {issue_count} violations")
    for issue in issues:
        print(issue)



def gds(design, def_file, gds_file):
    
    def_file_rel = os.path.relpath(def_file, build_folder)
    gds_file_rel = os.path.relpath(gds_file, build_folder)

    gds_file_noext = gds_file_rel
    if gds_file_noext.endswith(".gds"):
        gds_file_noext = gds_file_noext[:-4]

    print("--- GDS ---")
    with open(f"{build_folder}/gds.sh", "w") as f:
        f.write(f"""
        set -e
        cd {build_folder}
        mkdir -p magic

        export TECH_LEF={pdk_tlef_dir}/{scl}.tlef
        export DESIGN_NAME={design}
        export CURRENT_DEF={def_file_rel}
        export CURRENT_GDS={gds_file_rel}
        export magic_report_file_tag={gds_file_rel}
        export magic_result_file_tag={gds_file_noext}
        export MAGIC_PAD=0
        export MAGIC_ZEROIZE_ORIGIN=1
        export MAGIC_GENERATE_GDS=1
        export MAGIC_DRC_USE_GDS=1
        export RESULTS_DIR=.

        cat /openlane/scripts/magic/mag_gds.tcl > ./gds.tcl
        sed -i "s/def read \$::env(CURRENT_DEF)/def read \$::env(CURRENT_DEF) -labels/" ./gds.tcl
        sed -i "s/exit 0/feedback save .\/magic\/feedback.txt; exit 0/" ./gds.tcl

        echo "Streaming out GDSII..."
        magic -rcfile {pdk_magic_dir}/{pdk}.magicrc -noconsole -dnull < ./gds.tcl
        echo "Running GDS DRC..."
        magic -rcfile {pdk_magic_dir}/{pdk}.magicrc -noconsole -dnull < /openlane/scripts/magic/drc.tcl
        """)

    
    openlane("bash", f"{build_folder}/gds.sh")

    drc_report = "%s.drc" % gds_file
    drc_report_str = open(drc_report).read()
    count = r"COUNT:\s*(\d+)"
    errors = 0
    count_match = re.search(count, drc_report_str)
    if count_match is not None:
        errors = int(count_match[1])
    if errors != 0:
        print("Error: There are %i DRC errors. Check %s." % (errors, drc_report))
        exit(os.EX_DATAERR)
    else:
        print("DRC successful.")

@click.command()
# Execution Flow
@click.option("-f", "--from", "frm", default="synthesis", help="Start from this step")
@click.option("-t", "--to", default="gds", help="End after this step")
@click.option("--only", default=None, help="Only execute these semicolon;delimited;steps")
@click.option("--skip", default=None, help="Skip these semicolon;delimited;steps")

# Configuration
@click.option("-p", "--pdk-root", required=os.getenv("PDK_ROOT") is None, default=os.getenv("PDK_ROOT"), help="Path to OpenPDKs PDK root")
@click.option("-O", "--output-dir", default="./build", help="Output directory.")
@click.option("-b", "--building-blocks", default="sky130A:sky130_fd_sc_hd:ram", help="Format {pdk}:{scl}:{name} : ID of the building blocks to use.")
@click.option("-v", "--variant", default=None, help="Use design variants (such as 1RW1R)")
@click.option("-s", "--size", required=True, help="Size")
@click.option("-C", "--clock-period", default=3, type=float, help="clk period for sta")
@click.option("-H", "--halo", default=2.5, type=float, help="Halo in microns")

# Enable/Disable
@click.option("--drc/--no-drc", default=True, help="Perform DRC on latest generated def file. (Default: True)")
@click.option("--image/--no-image", default=False, help="Create an image using Klayout. (Default: False)")
@click.option("--klayout/--no-klayout", default=False, help="Open the last def in Klayout. (Default: False)")

def flow(frm, to, only, pdk_root, skip, size, building_blocks, clock_period, halo, variant, drc, image, klayout, output_dir):
    global build_folder
    global last_def
    global pdk, scl
    
    if variant == "DEFAULT":
        variant = None

    pdk, scl, blocks = building_blocks.split(":")

    bb_dir = os.path.join(".", "platforms", pdk, scl, "_building_blocks", blocks)
    if not os.path.isdir(bb_dir):
        print("Looking for building blocks in :", bb_dir)
        print("Building blocks %s not found." % building_blocks)
        exit(os.EX_NOINPUT)

    bb_used = os.path.join(bb_dir, "model.v")
    config_file = os.path.join(bb_dir, "config.yml")
    config = yaml.safe_load(open(config_file))

    pin_order_file = os.path.join(bb_dir, "pin_order.cfg")

    m = re.match(r"(\d+)x(\d+)", size)
    if m is None:
        print("Invalid RAM size '%s'." % size)
        exit(os.EX_USAGE)

    words = int(m[1])
    word_width = int(m[2])
    word_width_bytes = word_width / 8

    if os.getenv("FORCE_ACCEPT_SIZE") is None:
        if words not in config["counts"] or word_width not in config["widths"]:
            print("Size %s not supported by %s." % (size, building_blocks))
            exit(os.EX_USAGE)

        if variant not in config["variants"]:
            print("Variant %s is unsupported by %s." % (variant, building_blocks))
            exit(os.EX_USAGE)

    wmargin, hmargin = (halo, halo) # Microns

    variant_string = (("_%s" % variant) if variant is not None else "")
    design_name_template = config["design_name_template"]
    design = os.getenv("FORCE_DESIGN_NAME") or design_name_template.format(**{
        "count": words,
        "width": word_width,
        "width_bytes": word_width_bytes,
        "variant": variant_string
    })
    build_folder = f"{output_dir}/{size}_{variant or 'DEFAULT'}"

    ensure_dir(build_folder)

    def i(ext=""):
        return f"{build_folder}/{design}{ext}"

    synth_info_path = os.path.join(".", "platforms", pdk, scl, "synth.yml")
    synth_info = yaml.safe_load(open(synth_info_path))

    site_info_path = os.path.join(".", "platforms", pdk, scl, "site.yml")
    site_info = None
    try:
        site_info = yaml.safe_load(open(site_info_path).read())
    except FileNotFoundError:
        if halo != 0.0:
            print(f"Note: {site_info_path} does not exist. The halo will not be rounded up to the nearest number of sites. This may cause off-by-one issues with some tools.")

    # Normalize margins in terms of minimum units
    if site_info is not None:
        site_width = site_info["width"]
        site_height = site_info["height"]

        wmargin = math.ceil(wmargin / site_width) * site_width
        hmargin = math.ceil(hmargin / site_height) * site_height
    else:
        pass

    prep(pdk_root)

    start = time.time()

    netlist = i(".nl.v")
    initial_floorplan = i(".initfp.def")
    initial_placement = i(".initp.def")
    dimensions_file = i(".dimensions.txt")
    density_file = i(".density.txt")
    final_floorplan = i(".fp.def")
    no_pins_placement = i(".npp.def")
    final_placement = i(".placed.def")
    pdn = i(".pdn.def")
    obstructed = i(".obs.def")
    routed = i(".routed.def")
    spef = i(".routed.spef")
    powered_def = i(".powered.def")
    norewrite_powered_netlist = i(".norewrite_powered.nl.v")
    powered_netlist = i(".powered.nl.v")
    antenna_report = i(".antenna.rpt")
    report = i(".rpt")
    drc_report = i(".drc.rpt")

    products = f"{build_folder}/products"

    ensure_dir(products)

    def p(ext=""):
        return f"{products}/{design}{ext}"

    lef_view = p(".lef")
    lib_view = p(".lib")
    gds_file = p(".gds")

    width, height = 20000, 20000


    def placement(in_width, in_height):
        nonlocal width, height
        floorplan(design, synth_info, wmargin, hmargin, in_width, in_height, netlist, initial_floorplan)
        placeram(initial_floorplan, initial_placement, size, building_blocks, dimensions=dimensions_file)
        width, height = map(lambda x: float(x), open(dimensions_file).read().split("x"))
        floorplan(design, synth_info, wmargin, hmargin, width, height, netlist, final_floorplan)
        placeram(final_floorplan, no_pins_placement, size, building_blocks, density=density_file)
        place_pins(design, synth_info, no_pins_placement, final_placement, pin_order_file)
        verify_placement(design, synth_info, final_placement)

    steps = [
        (
            "synthesis",
            lambda: synthesis(
                design,
                bb_used,
                synth_info,
                config["widths"],
                word_width_bytes,
                netlist
            )
        ),
        ("sta_1", lambda: sta(design, netlist, synth_info, clock_period)),
        ("placement", lambda: placement(width, height)),
        (
            "pdngen",
            lambda: pdngen(width, height, final_placement, pdn)
        ),
        (
            "obs_route",
            lambda: obs_route(5, width, height, wmargin, hmargin, pdn, obstructed)
        ),
        (
            "routing",
            lambda: (
                route(synth_info, obstructed, routed)
            )
        ),
        (
            "antenna_check",
            lambda: antenna_check(
                routed,
                antenna_report
            )
        ),
        (
            "sta_2",
            lambda: (
                spef_extract(routed, spef),
                sta(design, netlist, synth_info, clock_period, spef)
            )
        ),
        (
            "add_pwr_gnd_pins",
            lambda: (
                add_pwr_gnd_pins(
                    netlist,
                    routed,
                    powered_def,
                    norewrite_powered_netlist,
                    powered_netlist
                )
            )
        ),
        (
            "write_lef",
            lambda: write_ram_lef(
                design,
                routed,
                lef_view
            )
        ),
        (
            "write_lib",
            lambda: write_ram_lib(
                design,
                powered_netlist,
                lib_view
            )
        ),
        (
            "lvs",
            lambda: lvs(
                design,
                routed,
                powered_netlist,
                report
            )
        ),
        (
            "gds",
            lambda: gds(
                design,
                powered_def,
                gds_file
            )
        )
    ]

    only = only.split(";") if only is not None else None
    skip = skip.split(";") if skip is not None else []

    execute_steps = False
    for step in steps:
        name, action = step
        if frm == name:
            execute_steps = True
        if execute_steps:
            if (only is None or name in only) and (name not in skip):
                action()
        if to == name:
            execute_steps = False

    if last_def is not None:
        if drc:
            magic_drc(design, last_def)

        if image:
            image = create_image(last_def)
            if sys.platform == "darwin":
                try:
                    subprocess.run([
                        "open", "-a", "Preview",
                        image
                    ], check=True)
                    print("Opened last image in Preview.")
                except:
                    pass
            if sys.platform == "linux":
                try:
                    # WSL
                    subprocess.run([
                        "wslview",
                        image
                    ], check=True)
                    print("Opened last image in Windows.")
                except:
                    try:
                        # xdg-compatible
                        subprocess.run([
                            "xdg-open",
                            image
                        ], check=True)
                    except:
                        pass

        if klayout:
            env = os.environ.copy()
            env["LAYOUT"] = last_def
            env["PDK"] = pdk
            subprocess.Popen([
                "klayout",
                "-rm",
                last_def
            ], env=env)

    elapsed = time.time() - start

    

    print("Done in %.2fs." % elapsed)
    cl()

def main():
    try:
        flow()
    except subprocess.CalledProcessError as e:
        print("A step has failed:", e)
        print(f"Quick invoke: {' '.join(e.cmd)}")
        cl()
        exit(os.EX_UNAVAILABLE)
    except Exception:
        print("An unhandled exception has occurred.", traceback.format_exc())
        cl()
        exit(os.EX_UNAVAILABLE)

if __name__ == '__main__':
    main()
