
            yosys -import
            set SCL /home/videogamo/Work/mpw5/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
            read_liberty -lib -ignore_miss_dir -setattr blackbox $SCL
            read_verilog ./platforms/sky130A/sky130_fd_sc_hd/_building_blocks/rf/model.v
            catch { chparam -set WSIZE 32 DFFRF_2R1W }
            hierarchy -check -top DFFRF_2R1W
            synth -flatten
            yosys rename -top DFFRF_2R1W
            opt_clean -purge
            splitnets
            opt_clean -purge
            write_verilog -noattr -noexpr -nodec ./build/32x32_2R1W/DFFRF_2R1W.nl.v
            stat -top DFFRF_2R1W -liberty $SCL
            exit
            