
            read_liberty /home/videogamo/Work/mpw5/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
            read_lef ./build/32x32_2R1W/merged.lef
            read_def ./build/32x32_2R1W/DFFRF_2R1W.placed.def
            if {[catch check_placement -verbose]} {
                puts "Placement failed: Check placement returned a nonzero value."
                exit 65
            }
            puts "Placement successful."
            