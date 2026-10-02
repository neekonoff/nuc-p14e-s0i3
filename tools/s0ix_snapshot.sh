#!/bin/bash
# Read-only snapshot of the S0ix state. Writes nothing; prints to stdout.
#
#   sudo ./s0ix_snapshot.sh          short form
#   sudo ./s0ix_snapshot.sh full     also dumps substate requirements, status registers and LTRs
#
# Needs: intel_pmc_core with debugfs mounted, busybox (for devmem).
# PWRMBASE is assumed to be 0xFE000000 (Tiger Lake / Alder Lake client platforms).
D=/sys/kernel/debug/pmc_core
PWRM=0xFE000000
rd() { busybox devmem $(printf '0x%X' $((PWRM + $1))) 32 2>/dev/null || echo "n/a"; }

echo "== date: $(date -Is)   boot: $(uptime -s)"
echo "== kernel: $(uname -r)"
echo "== BIOS: $(cat /sys/class/dmi/id/bios_version) $(cat /sys/class/dmi/id/bios_date)"
echo "== suspend log (this boot)"
journalctl -b 0 -k --no-pager -o short-iso | grep -aE "PM: suspend (entry|exit)" | tail -12
echo "== substate_residencies (usec)"; cat $D/substate_residencies
echo "== slp_s0_residency_usec: $(cat $D/slp_s0_residency_usec)"
echo "== package_cstate_show (usec)"; cat $D/package_cstate_show
echo "== ACPI PM timer: PWRM+0x18FC = $(rd 0x18FC)   (bit 1 ACPI_TIM_DIS: 0x2 = timer off, 0x0 = timer running)"
echo "== WDAT table: $(ls /sys/firmware/acpi/tables/ | grep -c '^WDAT')   wdat_wdt module: $(lsmod | grep -c '^wdat_wdt')   iTCO_wdt module: $(lsmod | grep -c '^iTCO_wdt')"
echo "== LPM_EN  PWRM+0x1C78 = $(rd 0x1C78)   LPM_PRI PWRM+0x1C7C = $(rd 0x1C7C)"
echo "== clocksource: current=$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource) available=$(cat /sys/devices/system/clocksource/clocksource0/available_clocksource)"
echo "== lpm_latch_mode: $(cat $D/lpm_latch_mode)"

if [ "$1" = "full" ]; then
	echo "== substate_requirements"; cat $D/substate_requirements
	echo "== substate_status_registers"; cat $D/substate_status_registers
	echo "== substate_live_status_registers"; cat $D/substate_live_status_registers
	echo "== ltr_show"; cat $D/ltr_show
fi
