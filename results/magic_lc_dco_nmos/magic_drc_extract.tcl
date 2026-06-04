
gds readonly true
gds read /home/whqkrel/rfic_project/layouts/lc_dco_nmos.gds
load LC_DCO_NMOS
drc style drc(full)
drc check
set count [drc count total]
puts "MAGIC_DRC_TOTAL $count"
extract do local
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice -o /home/whqkrel/rfic_project/results/magic_lc_dco_nmos/lc_dco_nmos_magic.spice
quit -noprompt
