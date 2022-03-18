
            set ::env(DESIGN_NAME) "DFFRF_2R1W"

            set ::env(CLOCK_PORT) "CLK"
            set ::env(CLOCK_PERIOD) "3.0"

            set ::env(LEC_ENABLE) "1"
            set ::env(FP_WELLTAP_CELL) "sky130_fd_sc_hd__tap*"

            set ::env(CELL_PAD) "0"
            set ::env(FILL_INSERTION) "0"
            set ::env(PL_RESIZER_DESIGN_OPTIMIZATIONS) "0"
            set ::env(PL_RESIZER_TIMING_OPTIMIZATIONS) "0"
            set ::env(GLB_RESIZER_DESIGN_OPTIMIZATIONS) "0"
            set ::env(GLB_RESIZER_TIMING_OPTIMIZATIONS) "0"

            set ::env(RT_MAX_LAYER) "met4"
            set ::env(GLB_RT_ALLOW_CONGESTION) "1"

            set ::env(CELLS_LEF) "$::env(DESIGN_DIR)/cells.lef"

            set ::env(DIE_AREA) "0 0 358.79999999999995 176.8"

            set ::env(DIODE_INSERTION_STRATEGY) "0"

            set ::env(ROUTING_CORES) 16

            set ::env(DESIGN_IS_CORE) "0"
            set ::env(FP_PDN_CORE_RING) "0"

            # set ::env(PRODUCTS_PATH) "./build/32x32_2R1W/products"
            set ::env(PRODUCTS_PATH) "$::env(DESIGN_DIR)/build/32x32_2R1W/products"

            set ::env(INITIAL_NETLIST) "$::env(DESIGN_DIR)/DFFRF_2R1W.nl.v"
            set ::env(INITIAL_DEF) "$::env(DESIGN_DIR)/DFFRF_2R1W.placed.def"
            set ::env(INITIAL_SDC) "$::env(BASE_SDC_FILE)"

            set ::env(LVS_CONNECT_BY_LABEL) "1"

            set ::env(QUIT_ON_TIMING_VIOLATIONS) "0"
            


            # ADDED VALUES
            set ::env(PDN_CFG) $::env(DESIGN_DIR)/pdn.tcl

            set ::env(RT_MAX_LAYER) {met3}
            # set ::env(RT_MIN_LAYER) {met1}

            set ::env(FP_PDN_RAILS_LAYER) {met1}
            set ::env(FP_PDN_LOWER_LAYER) {met2}
            set ::env(FP_PDN_UPPER_LAYER) {met3}

            # Custom pin order to work best with the wrapped_hack_soc design
            set ::env(FP_PIN_ORDER_CFG)  "$::env(DESIGN_DIR)/pin_order.cfg"

            set ::env(FP_PDN_VWIDTH) 1.6            
            set ::env(FP_PDN_VPITCH) 400
            set ::env(FP_PDN_VOFFSET) 100
            set ::env(FP_PDN_HPITCH) 200
            set ::env(FP_PDN_HOFFSET) 35



            # set ::env(FP_IO_HLAYER) 