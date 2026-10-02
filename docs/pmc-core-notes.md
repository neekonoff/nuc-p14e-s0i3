# Reading `intel_pmc_core` without being misled

Things that cost time on this machine (Core i7-1265U, kernel 6.12). All files are under
`/sys/kernel/debug/pmc_core/`.

- **A status bit of 1 means "condition satisfied".** In `LPM_STATUS_*` the `*_REQ_STS` and `*_PG_STS`
  bits read 1 when the block is out of the way. `PCIe_Clk_REQ_STS_12 = 1` does not mean that a device
  holds CLKREQ#; it was 1 in every measurement, awake and asleep.
- **Use the right register map.** For Alder Lake-P/U the kernel uses the Tiger Lake LP maps (`tgl.c`),
  not `adl.c`, which describes Alder Lake-S. Decoding `LPM_STATUS_0` with the wrong file gives PLLs
  that do not exist.
- **`MainPLL_OFF_STS` and `Fast_XTAL_Osc_OFF_STS` stay empty even when S0i3.0 works.** With the default
  `lpm_latch_mode` (`c10`) the status is latched on C10 entry, before the PMC shuts the crystal down.
  Judge by `substate_residencies`, not by these two rows.
- **Only the rows marked `Required` matter.** `SPE_PG_STS`, `SPF_PG_STS`, `FIA_PG_STS` and similar are
  not required for S0i2.0 or S0i3.0 here.
- **`Int_Timer_SS_Wake*_Pol_STS` are listed as required and unmet for S0i2.0 too**, which is reached
  anyway. Ignore them.
- **`Status` versus `Live Status`.** `Status` is the latched value from the suspend; `Live Status` is
  read after resume, when most blocks are active again. S0ixSelftestTool printed the wrong column
  ([issue 43](https://github.com/intel/S0ixSelftestTool/issues/43)).
- **A suspend counts only if the residency counter moved.** If `S0i2.0` did not grow, the status
  registers still show the previous suspend.
- **A device without a working driver stays in D0 and blocks S0ix entirely.** Unbinding or removing
  devices as an experiment produces exactly that.
- **`last_hw_sleep` in `/sys/power/suspend_stats` is a 32-bit microsecond counter.** Suspends longer
  than about 71 minutes wrap around.
- **`lspci` wakes Thunderbolt and Type-C devices from D3cold.** Read `power_state` in sysfs instead
  when checking device states before a suspend.
- **PEP device constraints from the BIOS are only read by the kernel**, not enforced. Changing the
  `PEP ...` setup options has no effect on Linux 6.12.
