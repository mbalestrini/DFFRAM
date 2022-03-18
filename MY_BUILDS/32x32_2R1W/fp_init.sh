
        set -e

        python3 /openlane/scripts/new_tracks.py -i /home/videogamo/Work/mpw5/pdk/sky130A/libs.tech/openlane/sky130_fd_sc_hd/tracks.info -o ./build/32x32_2R1W/tracks.tcl
        openroad -exit ./build/32x32_2R1W/fp_init.tcl
        