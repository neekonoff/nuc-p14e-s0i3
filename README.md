# S0i3 on Intel NUC P14E Laptop Element + NUC 12 Compute Element (Linux)

[English](#english) · [Русский](#русский)

## English

### The problem

In suspend-to-idle (`s2idle`) this laptop only ever reached `S0i2.0`. The `S0i3.0` residency counter
stayed at 0, whatever was disabled, unplugged or reconfigured.

The cause is one BIOS default. `Enable TCO Timer = Enabled` keeps the ACPI PM timer of the chipset
running, and while that timer runs the chipset never shuts down its 38.4 MHz crystal, which S0i3
requires. With `Enable TCO Timer = Disabled` the laptop spends more than 99.8 % of suspend time in
`S0i3.0`.

The option is hidden in the Setup UI of this board; it has to be written with AMI's SCE utility.
The same cause is likely on other Tiger Lake and Alder Lake machines whose firmware leaves the ACPI
PM timer on.

### Configuration

- Intel NUC P14E Laptop Element (CMCN1CC) with Intel NUC 12 Compute Element ELM12HB
- Core i7-1265U (Alder Lake), Solidigm P44 Pro NVMe SSD
- BIOS HBADLMIV.0065 (AMI Aptio V, Intel FSP `$ADLFSP$`), ME 16.1.42
- Debian 13, kernel 6.12.107, `s2idle`

### Is this your problem?

```
sudo cat /sys/kernel/debug/pmc_core/substate_residencies   # S0i2.0 grows after a suspend, S0i3.0 stays 0
sudo busybox devmem 0xFE0018FC 32                          # 0x00000000: the ACPI PM timer is running
ls /sys/firmware/acpi/tables | grep WDAT                   # the BIOS publishes a WDAT table
```

`0xFE0018FC` is `PWRMBASE + 0x18FC`, the ACPI timer control register; bit 1 (`ACPI_TIM_DIS`) set
means the timer is off. `tools/s0ix_snapshot.sh` prints all of this in one go.

Other signs: Package C10 and `slp_s0_residency_usec` cover almost all of the suspend time;
[S0ixSelftestTool](https://github.com/intel/S0ixSelftestTool) says `Your system only get shallower
S0ix substate residency: S0i2.0`; in `substate_requirements` everything required for `S0i3.0` is
satisfied except `MainPLL_OFF_STS` and `Fast_XTAL_Osc_OFF_STS`.

### Why

To enter S0i3 the chipset has to shut down its main PLL and the 38.4 MHz crystal oscillator. The ACPI
PM timer needs that crystal, so with the timer enabled the power management controller stops at S0i2.

- Intel FSP for Alder Lake, parameter `EnableTcoTimer`: "When FALSE, it disables PCH ACPI timer, and
  stops TCO timer. NOTE: This will have huge power impact when it's enabled."
  ([FspsUpd.h](https://github.com/coreboot/coreboot/blob/main/src/vendorcode/intel/fsp/fsp2_0/alderlake/FspsUpd.h))
- coreboot, `src/soc/intel/alderlake/pmc.c`: "Disabling ACPI PM timer is necessary for XTAL OSC
  shutdown."
- coreboot commit `1ce0f3aab72d`: "Keeping the PM timer enabled will disqualify an ADL system from
  entering S0i3" ([review 59790](https://review.coreboot.org/c/coreboot/+/59790)).

Linux does not handle this by itself. The kernel patch `e86c8186d03a`, which turned the timer off
during suspend, was reverted by `5fa607880168` before 6.12 was released and has not come back as of
7.3-rc4. A newer kernel or another distribution changes nothing here.

### The fix

Set `Enable TCO Timer` to `Disabled`, then power the machine off and on.

The utility is in [amisce/](amisce/); the pitfalls are in [docs/amisce.md](docs/amisce.md).
A BIOS administrator password must be set. Everything here was done with Secure Boot disabled: with
it enabled the kernel lockdown blocks access to the registers.

```
sudo ./SCELNX_64 /o /s now.txt                           # dump all setup questions (read-only)
python3 tools/bios_diff.py script now.txt data/bios_0065_settings_dump.txt tco.txt B7E
sudo ./SCELNX_64 /cs tco.txt /o cmp.txt                  # compare with NVRAM, nothing is written
sudo ./SCELNX_64 /i /s tco.txt /cpwd '<BIOS administrator password>'
```

The result is the script in [data/tco_timer_off.txt](data/tco_timer_off.txt). Do not import that
file as is: `HIICrc32` and the token number belong to one machine and one BIOS version. On BIOS 0052
of the same board token `B7E` is a different option. Build the script from your own dump and check
that the block is named `Enable TCO Timer`.

Changing hidden firmware settings can leave a machine unbootable. Know how to reset your BIOS before
you start.

### Result

The measurements were taken on the same day after a full reset of the BIOS to build-time defaults,
with Secure Boot disabled so that the registers can be read.

| BIOS settings | suspend | S0i2.0 | S0i3.0 |
|---|---|---|---|
| defaults (`Enable TCO Timer = Enabled`) | 552 s | 550.2 s | 0 |
| `Enable TCO Timer = Disabled` | 393 s | 0.03 s | 392.1 s (99.8 %) |
| the same, two hours on battery | 7450 s | 0.1 s | 7439 s (99.9 %) |

After the change `PWRMBASE + 0x18FC` reads `0x2` and the WDAT table is gone. The `acpi_pm`
clocksource is still registered: the firmware enables microcode emulation of the PM timer
(MSR `0x121`) under the same condition that disables the hardware timer, see
[docs/firmware-analysis.md](docs/firmware-analysis.md).

Raw snapshot of the default state: [data/pmc_before_defaults.txt](data/pmc_before_defaults.txt).

### Side effects and limits

- The hardware watchdog is gone: without the ACPI PM timer the TCO timer does not count.
- The setting lives in NVRAM. A BIOS update or a reset to defaults brings `Enabled` back.
- Power: the two-hour suspend used 1.5-2 % of a 74 Wh battery, about 0.5-0.7 W. In `S0i2.0` the same
  laptop drew about 0.76 W, so the gain is within the error of such a short measurement. An
  overnight measurement has not been done yet.
- Windows was not tested. The limit is in the chipset, not in the OS. A clean Windows sleep study does
  not prove S0i3: it reports `SLP_S0` residency, and `SLP_S0` is asserted in S0i2 as well.

### How it was found

The search took two and a half weeks, from 15 September to 2 October 2026: more than forty sessions
with AI coding agents (about 18,000 steps), more than fifty BIOS dumps, over a hundred hidden BIOS
settings changed and reverted, a BIOS downgrade and upgrade, the camera and microphone cable
disconnected, a boot without the SSD. Almost all of it went into ruling things out: the NVMe drive
and its CLKREQ#, D3hot versus D3cold, PCIe clock outputs, root ports, audio DSP, DMIC and Wake on
Voice, CNVi, ISH, ME and AMT, Wake on LAN, HPET, S0ix auto-demotion, USB2 PHY power gating, LTR of
every IP block, a newer kernel, Secure Boot, the embedded controller. None of them was the cause.

The agents were agy CLI (Gemini 3.8 Flash) and Claude Code (Opus 5 and Opus 5.5). The agy sessions
produced most of the experiments, dumps and measurements. The root cause was found by Claude Code
(Opus 5.5, max effort) when it was pointed at the transcript of the last long agy CLI session
(Gemini 3.8 Flash (High), about 4,200 steps). It went back from the conclusions to the raw
measurements, saw that every device-level requirement for `S0i3.0` was already satisfied and only
the crystal and the main PLL stayed on, asked what inside the chipset needs the crystal, and found
the ACPI PM timer in the coreboot and Intel FSP sources. The register confirmed it, a disassembly of
the firmware showed that the option is safe to change, and the first suspend after the change went
to `S0i3.0`.

Notes on reading `intel_pmc_core` output without being misled are in
[docs/pmc-core-notes.md](docs/pmc-core-notes.md).

### Contents

| Path | What |
|---|---|
| `tools/s0ix_snapshot.sh` | read-only snapshot of S0ix counters, the ACPI timer register, WDAT |
| `tools/bios_diff.py` | compare AMISCE dumps, list non-default settings, build an import script |
| `tools/fw/` | unpack and disassemble Intel FSP-S modules from a BIOS capsule |
| `amisce/` | AMISCE builds for Linux (5.05.06.0007), Windows and EFI, and why they are included |
| `data/bios_0065_settings_dump.txt` | every setup option of BIOS HBADLMIV.0065: defaults plus the fix |
| `data/nondefault_settings.txt` | what differs from the default column in that dump |
| `data/tco_timer_off.txt` | the script that was imported |
| `data/pmc_before_defaults.txt` | `pmc_core` snapshot at default settings |
| `docs/amisce.md` | writing hidden settings on this board |
| `docs/firmware-analysis.md` | what the firmware does when the option is disabled |
| `docs/pmc-core-notes.md` | pitfalls of `intel_pmc_core` debugfs |

## Русский

### Проблема

Во сне (`s2idle`) этот ноутбук доходил только до `S0i2.0`. Счётчик `S0i3.0` оставался нулём, что бы
ни отключали, ни отсоединяли и ни перенастраивали.

Причина — одна заводская настройка BIOS. `Enable TCO Timer = Enabled` держит включённым ACPI
PM-таймер чипсета, а пока он работает, чипсет не глушит кварц 38,4 МГц, без чего S0i3 невозможен.
С `Enable TCO Timer = Disabled` ноутбук проводит в `S0i3.0` больше
99,8 % времени сна.

Пункт скрыт из меню Setup этой платы, писать его приходится утилитой AMI SCE. Та же причина возможна
и на других машинах с Tiger Lake и Alder Lake, где прошивка оставляет ACPI-таймер включённым.

### Конфигурация

- Intel NUC P14E Laptop Element (CMCN1CC) с модулем Intel NUC 12 Compute Element ELM12HB
- Core i7-1265U (Alder Lake), накопитель Solidigm P44 Pro
- BIOS HBADLMIV.0065 (AMI Aptio V, Intel FSP `$ADLFSP$`), ME 16.1.42
- Debian 13, ядро 6.12.107, `s2idle`

### Ваш ли это случай

```
sudo cat /sys/kernel/debug/pmc_core/substate_residencies   # после сна растёт S0i2.0, S0i3.0 = 0
sudo busybox devmem 0xFE0018FC 32                          # 0x00000000: ACPI PM-таймер работает
ls /sys/firmware/acpi/tables | grep WDAT                   # BIOS публикует таблицу WDAT
```

`0xFE0018FC` — это `PWRMBASE + 0x18FC`, регистр управления ACPI-таймером; выставленный бит 1
(`ACPI_TIM_DIS`) означает, что таймер выключен. Всё это разом печатает `tools/s0ix_snapshot.sh`.

Другие признаки: Package C10 и `slp_s0_residency_usec` покрывают почти всё время сна;
[S0ixSelftestTool](https://github.com/intel/S0ixSelftestTool) пишет `Your system only get shallower
S0ix substate residency: S0i2.0`; в `substate_requirements` для `S0i3.0` выполнено всё, кроме
`MainPLL_OFF_STS` и `Fast_XTAL_Osc_OFF_STS`.

### Почему так

Чтобы войти в S0i3, чипсет должен заглушить главный PLL и кварц 38,4 МГц. ACPI PM-таймеру этот
кварц нужен, поэтому при включённом таймере контроллер питания останавливается на S0i2.

- Intel FSP для Alder Lake, параметр `EnableTcoTimer`: «When FALSE, it disables PCH ACPI timer, and
  stops TCO timer. NOTE: This will have huge power impact when it's enabled.»
  ([FspsUpd.h](https://github.com/coreboot/coreboot/blob/main/src/vendorcode/intel/fsp/fsp2_0/alderlake/FspsUpd.h))
- coreboot, `src/soc/intel/alderlake/pmc.c`: «Disabling ACPI PM timer is necessary for XTAL OSC
  shutdown.»
- coreboot, коммит `1ce0f3aab72d`: «Keeping the PM timer enabled will disqualify an ADL system from
  entering S0i3» ([review 59790](https://review.coreboot.org/c/coreboot/+/59790)).

Linux сам с этим не справляется. Патч ядра `e86c8186d03a`, выключавший таймер на время сна, откатили
коммитом `5fa607880168` ещё до выхода 6.12, и в 7.3-rc4 его по-прежнему нет. Более свежее ядро или
другой дистрибутив здесь ничего не меняют.

### Исправление

Поставить `Enable TCO Timer` в `Disabled`, затем выключить и включить машину.

Утилита лежит в [amisce/](amisce/), подводные камни описаны в [docs/amisce.md](docs/amisce.md)
(на английском). Нужен заведённый пароль администратора BIOS. Всё описанное делалось с выключенным
Secure Boot: с включённым ядро закрывает доступ к регистрам.

```
sudo ./SCELNX_64 /o /s now.txt                           # выгрузка всех настроек, только чтение
python3 tools/bios_diff.py script now.txt data/bios_0065_settings_dump.txt tco.txt B7E
sudo ./SCELNX_64 /cs tco.txt /o cmp.txt                  # сверка с NVRAM, ничего не пишет
sudo ./SCELNX_64 /i /s tco.txt /cpwd '<пароль администратора BIOS>'
```

Получится скрипт, как в [data/tco_timer_off.txt](data/tco_timer_off.txt). Сам этот файл
импортировать не надо: `HIICrc32` и номер токена относятся к одной машине и одной версии BIOS. На
BIOS 0052 той же платы токен `B7E` — другой пункт. Скрипт собирать из собственной выгрузки и
проверять, что блок называется `Enable TCO Timer`.

Правка скрытых настроек прошивки может оставить машину без загрузки. Сначала выясните, как у вас
сбрасывается BIOS.

### Результат

Замеры сделаны в один день после полного сброса BIOS к заводским настройкам, с выключенным
Secure Boot, чтобы можно было читать регистры.

| Настройки BIOS | сон | S0i2.0 | S0i3.0 |
|---|---|---|---|
| заводские (`Enable TCO Timer = Enabled`) | 552 с | 550,2 с | 0 |
| `Enable TCO Timer = Disabled` | 393 с | 0,03 с | 392,1 с (99,8 %) |
| то же, два часа от батареи | 7450 с | 0,1 с | 7439 с (99,9 %) |

После правки `PWRMBASE + 0x18FC` читается как `0x2`, таблицы WDAT нет. Источник времени `acpi_pm`
в ядре остаётся: прошивка включает эмуляцию PM-таймера в микрокоде (MSR `0x121`) по тому же условию,
по которому выключает аппаратный таймер, см. [docs/firmware-analysis.md](docs/firmware-analysis.md).

Сырой снимок заводского состояния: [data/pmc_before_defaults.txt](data/pmc_before_defaults.txt).

### Побочные эффекты и оговорки

- Аппаратного сторожевого таймера больше нет: без ACPI-таймера TCO не считает.
- Настройка живёт в NVRAM. Обновление BIOS и сброс настроек возвращают `Enabled`.
- Расход: за двухчасовой сон ушло 1,5–2 % батареи на 74 Вт·ч, то есть около 0,5–0,7 Вт. В `S0i2.0`
  тот же ноутбук потреблял около 0,76 Вт, так что выигрыш лежит в пределах погрешности такого
  короткого замера. Замер за ночь ещё не сделан.
- Под Windows не проверялось. Ограничение сидит в чипсете, а не в ОС. Чистый отчёт сна Windows
  S0i3 не доказывает: он показывает время с сигналом `SLP_S0`, а тот выставляется и в S0i2.

### Как это было найдено

Поиск занял две с половиной недели, с 15 сентября по 2 октября 2026 года: больше сорока сессий с
ИИ-агентами (около 18 000 шагов), больше пятидесяти дампов BIOS, больше сотни скрытых настроек BIOS,
изменённых и возвращённых обратно, откат и обновление прошивки, отсоединённый шлейф камеры и
микрофонов, загрузка без накопителя. Почти всё ушло на то, чтобы исключать причины: накопитель и
его CLKREQ#, D3hot или D3cold, тактовые выходы PCIe, корневые порты, Audio DSP, DMIC и Wake on
Voice, CNVi, ISH, ME и AMT, Wake on LAN, HPET, S0ix auto-demotion, питание USB2 PHY, LTR каждого
блока, более свежее ядро, Secure Boot, контроллер EC. Ничто из этого причиной не было.

Агенты — agy CLI (Gemini 3.8 Flash) и Claude Code (Opus 5 и Opus 5.5). В сессиях agy проделана
основная масса опытов, дампов и замеров. Первопричину нашёл Claude Code (Opus 5.5, max effort),
когда его «натравили» на транскрипт последней длинной сессии agy CLI (Gemini 3.8 Flash (High),
около 4200 шагов). Он вернулся от выводов к сырым замерам, увидел, что все требования к устройствам
для `S0i3.0` уже выполнены и не гаснут только кварц с главным PLL, задался вопросом, кому внутри
чипсета нужен кварц, и нашёл ACPI PM-таймер в исходниках coreboot и Intel FSP. Регистр это
подтвердил, дизассемблирование прошивки показало, что пункт безопасно менять, и первый же сон после
правки ушёл в `S0i3.0`.

Как читать вывод `intel_pmc_core` и не обмануться — [docs/pmc-core-notes.md](docs/pmc-core-notes.md)
(на английском).

### Содержимое

| Путь | Что |
|---|---|
| `tools/s0ix_snapshot.sh` | снимок счётчиков S0ix, регистра ACPI-таймера, WDAT; только чтение |
| `tools/bios_diff.py` | сравнение выгрузок AMISCE, список отличий от заводских, сборка скрипта |
| `tools/fw/` | распаковка и дизассемблирование модулей Intel FSP-S из капсулы BIOS |
| `amisce/` | сборки AMISCE для Linux (5.05.06.0007), Windows и EFI и объяснение, почему они выложены |
| `data/bios_0065_settings_dump.txt` | все настройки BIOS HBADLMIV.0065: заводские плюс исправление |
| `data/nondefault_settings.txt` | что в этой выгрузке отличается от заводской колонки |
| `data/tco_timer_off.txt` | скрипт, который был импортирован |
| `data/pmc_before_defaults.txt` | снимок `pmc_core` на заводских настройках |
| `docs/amisce.md` | запись скрытых настроек на этой плате |
| `docs/firmware-analysis.md` | что делает прошивка, когда пункт выключен |
| `docs/pmc-core-notes.md` | ловушки debugfs `intel_pmc_core` |

## License

The scripts are under the MIT license, see [LICENSE](LICENSE). `tools/fw/efidec.py` is a port of the
decompression algorithm from EDK II (BSD-2-Clause-Patent). AMISCE belongs to AMI and is not covered by
this license; see [amisce/README.md](amisce/README.md). Firmware and Intel FSP are not included.
