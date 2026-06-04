#!/usr/bin/env bash
set -u

NETLIST=/home/whqkrel/rfic_project/results/lc_dco_top_msb31_lsb24.cir
CSV=/home/whqkrel/rfic_project/results/lc_dco_data.csv
LOG=/home/whqkrel/rfic_project/results/lc_dco_msb31_lsb24.log

rm -f "$CSV" "$LOG"
timeout 150 ngspice -b "$NETLIST" > "$LOG" 2>&1
rc=$?

echo "NGSPICE_RC=$rc"
if test -s "$CSV"; then
  wc -c "$CSV"
else
  echo "CSV_MISSING_OR_EMPTY"
fi

exit "$rc"
