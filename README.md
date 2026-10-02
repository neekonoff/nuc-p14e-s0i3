# S0i3 on Intel NUC P14E Laptop Element + NUC 12 Compute Element (Linux)

[English](#english) · [Русский](#русский)

## English

### The problem

In sleep (`s2idle`, also called Modern Standby or S0ix) this laptop only reached the shallow state
`S0i2.0` and never the deepest one, `S0i3.0`, whatever was disabled, unplugged or reconfigured.

The cause is one factory BIOS setting: `Enable TCO Timer = Enabled`. With `Disabled` the laptop
spends about 99.8 % of its sleep time in `S0i3.0`.

The setting is not shown in BIOS Setup. It is changed from Linux with AMI's AMISCE utility, which is
included in this repository. The same cause is likely on other Tiger Lake and Alder Lake machines
that ship with this setting enabled.

### Configuration

- Intel NUC P14E Laptop Element (CMCN1CC) with Intel NUC 12 Compute Element ELM12HB
- Core i7-1265U (Alder Lake), Solidigm P44 Pro NVMe SSD
- BIOS HBADLMIV.0065 (AMI Aptio V), ME 16.1.42
- Debian 13, kernel 6.12.107

### Is this your problem?

```
sudo cat /sys/kernel/debug/pmc_core/substate_residencies
```

Run it, let the laptop sleep for a few minutes, wake it and run it again. The numbers are
microseconds spent in each state since boot. If `S0i2.0` has grown and `S0i3.0` is still 0, this is
your case:

```
Substate   Residency
S0i2.0     550159915
S0i3.0     0
```

Intel's [S0ixSelftestTool](https://github.com/intel/S0ixSelftestTool) says the same in its own
words: `Your system only get shallower S0ix substate residency: S0i2.0`.

### The fix

Before you start:

- **Secure Boot must be disabled** in BIOS Setup. Everything here was done with Secure Boot off;
  with it on, Linux restricts the direct memory access that the utility relies on.
- **A Supervisor password must be set** in BIOS Setup. Without one this BIOS does not let the
  utility write settings.

**1. Get this repository**

```
git clone https://github.com/neekonoff/nuc-p14e-s0i3.git ~/nuc-p14e-s0i3
```

**2. Save all current BIOS settings to a file.** This only reads.

```
sudo ~/nuc-p14e-s0i3/amisce/SceLnx/SCELNX_64 /o /s ~/bios_dump.txt
```

The last line of the output must be `Script file exported successfully.` The warning about duplicate
questions is normal.

If you get `ERROR:64 - HII Database needs reset` instead: reboot, enter BIOS Setup, change nothing,
leave without saving, let Linux start and run the command again. This error appears in the boot
that follows saving settings in BIOS Setup.

**3. Make a small file with the one setting.** The file that goes back into the BIOS must hold only
the header of the dump (its first six lines) and the block of the setting (the eight lines that
start with `Setup Question = Enable TCO Timer`). Delete everything else in a text editor, or let
two commands pick those lines:

```
head -n 6 ~/bios_dump.txt > ~/tco_off.txt
grep -A 7 'Enable TCO Timer' ~/bios_dump.txt >> ~/tco_off.txt
```

**4. Change the setting in that file.** Open it in any text editor, for example
`nano ~/tco_off.txt`, and move the asterisk from `[01]Enabled` to `[00]Disabled`. Change nothing
else. The file must look like this:

```
// Script File Name : /home/user/bios_dump.txt
// Created on 10/02/26 at 16:09:37
// AMISCE Utility. Ver 5.05.06.0007
// Copyright (c) 2023 AMI. All rights reserved.
HIICrc32= 5956593F

Setup Question	= Enable TCO Timer
Help String	= Enable/Disable TCO timer. When disabled, it disables PCH ACPI timer, stops TCO timer, and ACPI WDAT table will not be published.
Token	=B7E	// Do NOT change this line
Offset	=11
Width	=01
BIOS Default=[01]Enabled
Options	=*[00]Disabled	// Move "*" to the desired Option
         [01]Enabled
```

Your `HIICrc32` will be different, and on another BIOS version `Token` may differ too. Keep the
values from your own dump, do not copy them from this page.

**5. Load the file into the BIOS**

```
sudo ~/nuc-p14e-s0i3/amisce/SceLnx/SCELNX_64 /i /s ~/tco_off.txt /cpwd 'your Supervisor password'
```

The utility must answer:

```
Password accepted
Warning: Power cycle reset required for some of the updated controls.
Script file imported successfully.
```

**6. Shut the laptop down and switch it on again.** The utility asks for a power cycle; a plain
reboot was not tested.

**7. Check.** Let the laptop sleep for a few minutes and look at the counters again. Now `S0i3.0`
grows:

```
sudo cat /sys/kernel/debug/pmc_core/substate_residencies
```

To undo the change, repeat steps 2-6 with the asterisk on `[01]Enabled`, or load the defaults in
BIOS Setup. Keep `~/bios_dump.txt`: it holds all your BIOS settings as they were before the change.

### Result

Measured on 2 October 2026 after a full reset of the BIOS to factory defaults.

| BIOS settings | sleep | in S0i2.0 | in S0i3.0 |
|---|---|---|---|
| factory defaults (`Enable TCO Timer = Enabled`) | 552 s | 550.2 s | 0 |
| `Enable TCO Timer = Disabled` | 393 s | 0.03 s | 392.1 s (99.8 %) |
| the same, two hours on battery | 7450 s | 0.1 s | 7439 s (99.9 %) |

### Good to know

- The setting is stored in the BIOS. A BIOS update or a reset to defaults brings `Enabled` back:
  repeat the steps with a fresh dump.
- The hardware watchdog of the chipset (TCO) stops working. Nothing else was found broken in a day
  of use: boot, clocks, sleep and wake-up work as before.
- The power saving is not measured properly yet. A two-hour sleep took 1.5-2 % of the 74 Wh battery
  (about 0.5-0.7 W); in `S0i2.0` the same laptop drew about 0.76 W. An overnight measurement is
  still to be done.
- Windows was not tested. The cause is in the firmware, below the operating system.
- Any other hidden BIOS setting is changed the same way: find its block in the dump by name. A
  careless change can leave the machine unbootable. The way out is the power button menu: with the
  laptop off, hold the power button for about three seconds until it blinks yellow, release it and
  press F5 to restore the BIOS to factory defaults.

### Why it works

To enter S0i3 the chipset has to switch off its 38.4 MHz crystal oscillator. The chipset's ACPI PM
timer runs from that crystal, and `Enable TCO Timer = Enabled` keeps the timer running, so sleep
stops one step short, at S0i2. With `Disabled` the firmware switches the timer off. The operating
system does not lose its `acpi_pm` clock: the firmware replaces the timer with an emulation in CPU
microcode.

- Intel FSP for Alder Lake, parameter `EnableTcoTimer`: "When FALSE, it disables PCH ACPI timer, and
  stops TCO timer. NOTE: This will have huge power impact when it's enabled."
  ([FspsUpd.h](https://github.com/coreboot/coreboot/blob/main/src/vendorcode/intel/fsp/fsp2_0/alderlake/FspsUpd.h))
- coreboot, `src/soc/intel/alderlake/pmc.c`: "Disabling ACPI PM timer is necessary for XTAL OSC
  shutdown."
- coreboot commit `1ce0f3aab72d`: "Keeping the PM timer enabled will disqualify an ADL system from
  entering S0i3" ([review 59790](https://review.coreboot.org/c/coreboot/+/59790)).

Linux does not do this by itself. The kernel patch that switched the timer off during sleep
(`e86c8186d03a`) was reverted before 6.12 was released (`5fa607880168`) and has not come back as of
7.3-rc4. A newer kernel or another distribution does not help.

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
measurements, saw that every device was already ready for `S0i3.0` and only the crystal stayed on,
asked what inside the chipset needs the crystal, and found the ACPI PM timer in the coreboot and
Intel FSP sources. A look into the firmware code showed that the setting is safe to change, and the
first sleep after the change went to `S0i3.0`.

### What is in this repository

| Path | What |
|---|---|
| `amisce/SceLnx/SCELNX_64` | AMISCE 5.05.06.0007 for Linux, the one used in the steps above |
| `amisce/SceWin/` | the Windows build from the same package; not tested on this laptop |
| `amisce/SceEfi/` | the UEFI Shell build; on this laptop it reads settings but fails to write them |
| `docs/AMI_Aptio_5.x_AMISCE_User_Guide_NDA.pdf` | AMISCE user guide (AMI, revision 1.83) |
| `docs/elm12hb_compute_element_prod_spec.pdf` | Intel NUC 12 Compute Element, product specification |
| `docs/p14e_cmcn1cc_prod_spec.pdf` | Intel NUC P14E Laptop Element, product specification |
| `docs/p14e_cmcn1cc_integration_guide.pdf` | Intel NUC P14E Laptop Element, integration guide |

**Why AMISCE is here.** AMISCE is AMI's proprietary utility. It is included for one reason: on this
platform it is the only way to change the hidden BIOS setting that prevents S0i3, the version that
works is very hard to find, and without it the fix cannot be applied. The files are unmodified
copies from a tools package that Lenovo distributes for its ThinkSystem SR590 V2 servers
(`lnvgy_fw_uefi_xwe160d-1.14_anyos_32-64_tools.zip`); sha256 of `SCELNX_64` is
`b5218752a7b6d330f1e29ff2ea48b7ed76f40d61e86b66dcc0670023b21ab806`. They are provided so that
owners can repair hardware they own, not for any commercial purpose. All rights belong to AMI.
Rights holders who want the files removed can open an issue.

## Русский

### Проблема

Во сне (`s2idle`, он же Modern Standby или S0ix) этот ноутбук доходил только до неглубокого
состояния `S0i2.0` и ни разу до самого глубокого, `S0i3.0`, что бы ни отключали, ни отсоединяли и
ни перенастраивали.

Причина — одна заводская настройка BIOS: `Enable TCO Timer = Enabled`. С `Disabled` ноутбук
проводит в `S0i3.0` около 99,8 % времени сна.

В меню BIOS Setup этой настройки нет. Её меняют из Linux утилитой AMISCE компании AMI, утилита
лежит в этом репозитории. Та же причина возможна и на других машинах с Tiger Lake и Alder Lake, где
эта настройка включена с завода.

### Конфигурация

- Intel NUC P14E Laptop Element (CMCN1CC) с модулем Intel NUC 12 Compute Element ELM12HB
- Core i7-1265U (Alder Lake), накопитель Solidigm P44 Pro
- BIOS HBADLMIV.0065 (AMI Aptio V), ME 16.1.42
- Debian 13, ядро 6.12.107

### Ваш ли это случай

```
sudo cat /sys/kernel/debug/pmc_core/substate_residencies
```

Выполните команду, усыпите ноутбук на несколько минут, разбудите и выполните её ещё раз. Числа —
это микросекунды, проведённые в каждом состоянии с момента загрузки. Если `S0i2.0` выросло, а
`S0i3.0` осталось нулём, случай ваш:

```
Substate   Residency
S0i2.0     550159915
S0i3.0     0
```

[S0ixSelftestTool](https://github.com/intel/S0ixSelftestTool) от Intel сообщает о том же своими
словами: `Your system only get shallower S0ix substate residency: S0i2.0`.

### Исправление

Заранее:

- **Secure Boot должен быть выключен** в BIOS Setup. Всё описанное делалось с выключенным Secure
  Boot: с включённым Linux ограничивает прямой доступ к памяти, а утилите он нужен.
- **В BIOS Setup должен быть задан пароль Supervisor.** Без него этот BIOS не даёт утилите
  записывать настройки.

**1. Скачать репозиторий**

```
git clone https://github.com/neekonoff/nuc-p14e-s0i3.git ~/nuc-p14e-s0i3
```

**2. Сохранить все текущие настройки BIOS в файл.** Команда только читает.

```
sudo ~/nuc-p14e-s0i3/amisce/SceLnx/SCELNX_64 /o /s ~/bios_dump.txt
```

Последней строкой вывода должно быть `Script file exported successfully.` Предупреждение про
duplicate questions — это нормально.

Если вместо этого вышло `ERROR:64 - HII Database needs reset`: перезагрузитесь, зайдите в BIOS
Setup, ничего не меняйте, выйдите без сохранения, дождитесь загрузки Linux и повторите команду.
Такая ошибка бывает в загрузке, которая идёт сразу после сохранения настроек в BIOS Setup.

**3. Сделать маленький файл с одной настройкой.** В файле, который пойдёт обратно в BIOS, должны
остаться только шапка дампа (первые шесть строк) и блок этой настройки (восемь строк, начиная с
`Setup Question = Enable TCO Timer`). Всё остальное можно удалить в текстовом редакторе, а можно
выбрать нужные строки двумя командами:

```
head -n 6 ~/bios_dump.txt > ~/tco_off.txt
grep -A 7 'Enable TCO Timer' ~/bios_dump.txt >> ~/tco_off.txt
```

**4. Поменять настройку в этом файле.** Откройте его в любом текстовом редакторе, например
`nano ~/tco_off.txt`, и перенесите звёздочку с `[01]Enabled` на `[00]Disabled`. Больше ничего не
трогайте. Файл должен выглядеть так:

```
// Script File Name : /home/user/bios_dump.txt
// Created on 10/02/26 at 16:09:37
// AMISCE Utility. Ver 5.05.06.0007
// Copyright (c) 2023 AMI. All rights reserved.
HIICrc32= 5956593F

Setup Question	= Enable TCO Timer
Help String	= Enable/Disable TCO timer. When disabled, it disables PCH ACPI timer, stops TCO timer, and ACPI WDAT table will not be published.
Token	=B7E	// Do NOT change this line
Offset	=11
Width	=01
BIOS Default=[01]Enabled
Options	=*[00]Disabled	// Move "*" to the desired Option
         [01]Enabled
```

Значение `HIICrc32` у вас будет другим, а на другой версии BIOS может отличаться и `Token`.
Оставьте значения из своего дампа, с этой страницы их не копируйте.

**5. Загрузить файл в BIOS**

```
sudo ~/nuc-p14e-s0i3/amisce/SceLnx/SCELNX_64 /i /s ~/tco_off.txt /cpwd 'ваш пароль Supervisor'
```

Утилита должна ответить:

```
Password accepted
Warning: Power cycle reset required for some of the updated controls.
Script file imported successfully.
```

**6. Выключить ноутбук и включить снова.** Утилита просит именно выключения и включения; простая
перезагрузка не проверялась.

**7. Проверить.** Усыпите ноутбук на несколько минут и посмотрите счётчики ещё раз. Теперь растёт
`S0i3.0`:

```
sudo cat /sys/kernel/debug/pmc_core/substate_residencies
```

Чтобы вернуть как было, повторите шаги 2–6 со звёздочкой на `[01]Enabled` или загрузите заводские
настройки в BIOS Setup. Файл `~/bios_dump.txt` сохраните: в нём все ваши настройки BIOS, какими они
были до правки.

### Результат

Замеры сделаны 2 октября 2026 года после полного сброса BIOS к заводским настройкам.

| Настройки BIOS | сон | в S0i2.0 | в S0i3.0 |
|---|---|---|---|
| заводские (`Enable TCO Timer = Enabled`) | 552 с | 550,2 с | 0 |
| `Enable TCO Timer = Disabled` | 393 с | 0,03 с | 392,1 с (99,8 %) |
| то же, два часа от батареи | 7450 с | 0,1 с | 7439 с (99,9 %) |

### Что ещё нужно знать

- Настройка хранится в BIOS. Обновление BIOS и сброс настроек возвращают `Enabled`: шаги придётся
  повторить со свежим дампом.
- Перестаёт работать аппаратный сторожевой таймер чипсета (TCO). Больше ничего сломанного за день
  работы не нашлось: загрузка, часы, сон и пробуждение работают как раньше.
- Выигрыш в расходе толком ещё не измерен. За двухчасовой сон ушло 1,5–2 % батареи на 74 Вт·ч
  (около 0,5–0,7 Вт); в `S0i2.0` тот же ноутбук потреблял около 0,76 Вт. Замер за ночь ещё
  впереди.
- Под Windows не проверялось. Причина сидит в прошивке, ниже операционной системы.
- Любая другая скрытая настройка BIOS меняется так же: её блок находят в дампе по названию.
  Неосторожная правка может оставить машину без загрузки. Выход — меню кнопки питания: на
  выключенном ноутбуке подержите кнопку питания около трёх секунд, пока она не замигает жёлтым,
  отпустите и нажмите F5 — BIOS вернётся к заводским настройкам.

### Почему это работает

Чтобы войти в S0i3, чипсет должен выключить свой кварцевый генератор на 38,4 МГц. От этого кварца
работает ACPI PM-таймер чипсета, а `Enable TCO Timer = Enabled` держит таймер включённым, поэтому
сон останавливается на шаг раньше, в S0i2. С `Disabled` прошивка таймер выключает. Операционная
система свои часы `acpi_pm` при этом не теряет: прошивка заменяет таймер эмуляцией в микрокоде
процессора.

- Intel FSP для Alder Lake, параметр `EnableTcoTimer`: «When FALSE, it disables PCH ACPI timer, and
  stops TCO timer. NOTE: This will have huge power impact when it's enabled.»
  ([FspsUpd.h](https://github.com/coreboot/coreboot/blob/main/src/vendorcode/intel/fsp/fsp2_0/alderlake/FspsUpd.h))
- coreboot, `src/soc/intel/alderlake/pmc.c`: «Disabling ACPI PM timer is necessary for XTAL OSC
  shutdown.»
- coreboot, коммит `1ce0f3aab72d`: «Keeping the PM timer enabled will disqualify an ADL system from
  entering S0i3» ([review 59790](https://review.coreboot.org/c/coreboot/+/59790)).

Linux сам этого не делает. Патч ядра, выключавший таймер на время сна (`e86c8186d03a`), откатили
ещё до выхода 6.12 (`5fa607880168`), и в 7.3-rc4 его по-прежнему нет. Более свежее ядро или другой
дистрибутив не помогут.

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
около 4200 шагов). Он вернулся от выводов к сырым замерам, увидел, что все устройства к `S0i3.0`
уже готовы и не гаснет только кварц, задался вопросом, кому внутри чипсета этот кварц нужен, и
нашёл ACPI PM-таймер в исходниках coreboot и Intel FSP. Разбор кода прошивки показал, что настройку
безопасно менять, и первый же сон после правки ушёл в `S0i3.0`.

### Что лежит в репозитории

| Путь | Что |
|---|---|
| `amisce/SceLnx/SCELNX_64` | AMISCE 5.05.06.0007 для Linux — та самая, что в шагах выше |
| `amisce/SceWin/` | сборка для Windows из того же пакета; на этом ноутбуке не проверялась |
| `amisce/SceEfi/` | сборка для UEFI Shell; на этом ноутбуке настройки читает, но записать не может |
| `docs/AMI_Aptio_5.x_AMISCE_User_Guide_NDA.pdf` | руководство по AMISCE (AMI, редакция 1.83) |
| `docs/elm12hb_compute_element_prod_spec.pdf` | Intel NUC 12 Compute Element, спецификация |
| `docs/p14e_cmcn1cc_prod_spec.pdf` | Intel NUC P14E Laptop Element, спецификация |
| `docs/p14e_cmcn1cc_integration_guide.pdf` | Intel NUC P14E Laptop Element, руководство по сборке |

**Почему здесь выложена AMISCE.** AMISCE — закрытая утилита компании AMI. Выложена по одной
причине: на этой платформе скрытую настройку BIOS, мешающую S0i3, больше нечем поменять, рабочую
версию утилиты очень трудно найти, а без неё исправление не применить. Файлы — неизменённые копии
из пакета, который Lenovo распространяет для серверов ThinkSystem SR590 V2
(`lnvgy_fw_uefi_xwe160d-1.14_anyos_32-64_tools.zip`); sha256 файла `SCELNX_64` —
`b5218752a7b6d330f1e29ff2ea48b7ed76f40d61e86b66dcc0670023b21ab806`. Выложены для ремонта
собственного железа, не для коммерческого использования. Все права принадлежат AMI.
Правообладатели, которые хотят убрать файлы, могут открыть issue.

## License

The text of this repository is under the MIT license, see [LICENSE](LICENSE). AMISCE and its user
guide belong to AMI, the product documents belong to Intel; they are not covered by this license.
