
            read_liberty /home/videogamo/Work/mpw5/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
            read_lef ./build/32x32_2R1W/merged.lef
            read_verilog ./build/32x32_2R1W/DFFRF_2R1W.nl.v
            link_design DFFRF_2R1W
            initialize_floorplan\
                -die_area "0 0 358.79999999999995 176.8"\
                -core_area "2.7600000000000002 2.72 356.03999999999996 174.08"\
                -site unithd
            source ./build/32x32_2R1W/tracks.tcl
            write_def ./build/32x32_2R1W/DFFRF_2R1W.fp.def
            