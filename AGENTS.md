# AGENTS.md — 论文复现项目

## 项目性质

学术复现项目，非典型软件仓库。目标：复现论文 *Compound coastal marine–terrestrial heatwaves associated with humid-heat stress in Europe*（Scientific Reports 2025）。

**2026-10-30 第十八批：CESM1-LE 全量 80 件到位（20 成员 × all/xghg × TREFHT/SST）+ 论文口径复核 + 一个 P0 去重修复**：
- **数据全齐**：`data\CESM1-LE\proc\trefht_{all,xghg}_{001..020}_2000-2021.nc`（40 件，45–47 MB）
  与 `sst_{all,xghg}_{001..020}_2000-2021.nc`（40 件，113–114 MB），合计 **6.2 GB**（网络实搬 ≈18 GB）；
  ERA5 tmax **480/480**，仅剩 sp 0.25° **204/480**（引擎在跑，只能等 CDS 队列）。
- **★ 下载通道彻底换了：自写 DAP2 客户端 `python/dap2.py` + `download_cesm1le.py --engine dap2`**。
  原因是本机 **netCDF4/libcurl 的 DAP 通道全崩**（`OSError: [Errno -68] NetCDF: I/O failure`，schannel 证书吊销检查
  在 netCDF-C 里关不掉），pydap 又慢（6 路并发仅 33 kB/s，同条件 dap2 **1.5 MB/s**）。四条坑：
  ① TDS **每个 `.dods` 请求都有 30–60 s 固定延迟** ⇒ 时间轴绝不整条取，改成"取 1 个时间点 + `cftime.date2num` 算下标"；
  ② 自写客户端**不解码 `_FillValue`** ⇒ 陆地返回 9.96921e+36，必须 `|v|>1e30 → NaN`；
  ③ DAP2 响应里每个数组/坐标前有 **8 字节头 + 3 个 MAPS**，不跳过就整体错位；④ **`.bat`/`.ps1` 里不许出现中文**
  （`chcp 65001` 生效前已按 GBK 解析 ⇒ 报"字符串未终止"/"'shards' 不是内部或外部命令"）。
- **切片口径 = 分析切片，不是下整文件**：22 年（2000–2021）× 大气欧洲框 2 499/55 296（4.5%）× 海洋欧洲邻近
  11 328/122 880（9.2%，pad 回全球 384×320 形状以保 `coastal_pairs_cesm.csv` 的全局索引）× 只取 2 个变量。
  论文原文（`logs\_paper_main.txt`：Methods "We focus on the period 2000–2021 … 440 model years (22 years × 20 members)"）
  只用地海配对点、**没有任何 CESM 地图** ⇒ 口径够用。要 2080 情景 / 整盆平均 / 改区域框才需补下。
- **★ 修一个 P0**：`proc\` 里成员 001–003 同时留着 9 月旧通路（raw 整文件 + trim）分段件与新 gdex 整段件
  ⇒ `find_sst_segments("ALL","001")` 返回 3 个、`find_t2m_segments` 返回 2 个，`_load_sst_points` 会把 2000–2021
  **拼两遍**（阈值分位与事件天数全错）。`python/phase6_cesm.py:123` 新增 `_prefer_gdex()`，gdex 整段件在就只用它并打印
  `⚠ 同一成员有 N 个 raw/trim 分段件与 gdex 整段件并存 → 只用 …`。
- 产物体检 `logs\_audit_cesm80.py` → **80 件 / 异常 0**（atm `n=8030`、有限点 2 499/天；ocn 有限点 4 263/天、
  子网格外溢出 0；`ALL` 海洋 `n=8029` 因**原始数据缺 2006-01-02**，非下载 bug；"断点"另有 noleap 无 2/29）。

**2026-10-13 第十一批：本机科学栈丢失 ⇒ 按 requirements.txt 重建 + 重建后验证 + 数据现状复核**：
- **发现（换对话后第一件要确认的事）**：9 月跑通全链路的那套环境在本机**已不存在**——
  `python python\phase5_humid.py check` 直接 `ModuleNotFoundError: No module named 'xarray'`；
  C:/D:/E: 全盘按目录名搜 `xarray`/`scipy`/`cartopy`/`conda-meta` **零命中**，无 conda/miniconda、
  无 R、无 venv。**所以动手前先验环境，别默认还能跑。**
- **Python 已重建**（PATH 上的 `python` =
  `C:\Users\mango\AppData\Local\Programs\Python\Python313\python.exe`，3.13.9）：
  `python -m pip install -r requirements.txt` 全部按锁定版本装上并 import 通过 ——
  numpy 2.5.2（原 2.5.3 被降级对齐）/ scipy 1.18.1 / pandas 2.3.3 / xarray 2026.7.0 /
  netCDF4 1.7.4 / dask 2026.8.0 / matplotlib 3.11.1 / cartopy 0.26.0 / cdsapi 0.7.7 /
  s3fs 2026.7.0 / joblib 1.6.0 / pymupdf 1.28.2。**PyPI 直连可用**（无代理需求）。
  日志 `logs/pip_install.log`。
- **R 已重建**：TUNA 镜像静默安装 **R 4.6.1 → `C:\Program Files\R\R-4.6.1`（正好等于
  `config.RSCRIPT_PATH` 默认值，代码零改动）**；`install.packages(c('heatwaveR','ncdf4',
  'doParallel','foreach'))` 走 **Windows 二进制包（不需要 Rtools）**，装成
  **heatwaveR 0.5.5**（= 论文口径要求的版本）/ ncdf4 1.24 / doParallel 1.0.17 / foreach 1.5.2。
  日志 `logs/r_install.log`、`logs/r_packages_install.log`。
- **重建后验证（全过）**：四套自检 `calc_wbt`(25 项) / `gev_return_period`(16 项) /
  `results/phase5_selftest.py` / `results/phase6_selftest.py` 全 PASS，日志 `logs/selftests_rebuild.log`；
  **R 链路实跑 smoke**（`logs/_smoke/`）：
  `Rscript python\detect_events.R <E-OBS> T2m <out.csv> 1983 2012 <2 点 domains.csv> 5 2 2`
  → 2 格点匹配成功、**(49.875, 4.875) 检出 70 个事件**（1984–2023，事件数年 top =
  2018/2023/2015/2020/2022），另一格点 **(40.125, 9.875) 在 E-OBS 里是 100% NaN 的海洋格点、
  被脚本正确丢弃**（"1 valid points"）⇒ 检测链路与 NaN 处理均恢复正常。
- **数据现状（同日 `phase5_humid.py check`，7 项里 5 OK / 2 缺）**：
  `[缺]` **ERA5 tmax 只有 144 个月（1984-01…1995-12）**，缺 1996–2023；
  `[缺]` **`data\ERA5\sp_eur_daily\` 不存在**（sp 0.25° 欧洲框一个都没下，当前只能用 1.0° 兜底）；
  `[OK]` d2m 573 件 / sp 1.0° 46 件 / OAFlux / OISST / E-OBS。
  **tmax 下载自 2026-09-27 16:07 起停摆**（`logs/era5_fast_download.log` 末行 `第 2/4 次失败:
  SSLError … cds.climate.copernicus.eu`），无下载进程在跑。
- **★ 同日查明"为什么 9 月 27 日停了"的两个前提条件（重启下载前必须先满足，已写入 `待办.md` §1）**：
  ① **CDS 凭据文件随旧 profile 消失 → 同日已重建并联网验证 ✅** —— `C:\Users\Administrator\.cdsapirc`
  是 9 月下载实际用的那份（`logs/era5_fast_download.log` 开头两行自述
  `凭据: 使用 C:\Users\Administrator/.cdsapirc`），而本机现在**只剩 `mango` 一个用户 profile，
  `C:\Users\mango\.cdsapirc` 与 `C:\Users\Administrator\.cdsapirc` 都不存在**（C:/D:/E: 按文件名
  全盘搜 `cdsapirc` 零命中；旧脚本 `D:\python\ear5.py` 等只写 `cdsapi.Client()`、无硬编码 key）；
  当时 `cdsapi.Client()` 报 `Exception Missing/incomplete configuration file: C:\Users\mango/.cdsapirc`。
  **连 `D:\opencode\reinstall-backup`（2026-09-01 重装前备份，1499 文件 / 138.9 MB）内容全搜
  `cdsapirc|cds.climate.copernicus|CDSAPI|copernicus|ecmwf` 也是 0 命中，Browser 侧无 CDS 登录/访问记录**
  ⇒ 只能去 <https://cds.climate.copernicus.eu/profile> 重取 token（key 是账号级凭据没丢）。
  已重建 `C:\Users\mango\.cdsapirc`（url + key 两行）并**另备份到
  `D:\opencode\reinstall-backup\config\.cdsapirc`**；**验证证据**：`GET /api/profiles/v1/account`
  与 `/api/retrieve/v1/jobs` 均 **HTTP 200**，账号已接受 `cc-by` / `terms-of-use-cds` /
  `licence-to-use-E-OBS-products` 三条许可。同日 `--dry-run` 打印待下量：
  **tmax 144 在位 / 336 待下（1996-01…2023-12）、sp 0.25° 480 全待下（1984-01…2023-12）**。
  ② **系统代理端口踩空是 9 月停摆的直接原因** —— 日志里 `ProxyError('Unable to connect to proxy'…)`
  / `目标计算机积极拒绝 (127.0.0.1:8899)`：当时系统代理写 `127.0.0.1:8899` 而无进程监听，
  本机代理内核是 Sparkle 的 `mihomo.exe`，**2026-10-13 实测实际监听 `127.0.0.1:7890`**（控制口 9097）。
  同日实测 **CDS 直连可达（HTTP 202）、经 7890 亦可达**；系统代理当天为关闭状态（`ProxyEnable=0`）。

**2026-10-14 第十二批：ERA5 下载重启（显式窗口）+ 实测并发上限 3 + "在队年份台账/先收割后下载" + 一起外部杀进程事故**：
- **下载已重启并在跑**：入口 `run_phase5_fast_download.bat`（一个显式 Windows Terminal 窗口；`chcp 65001` +
  `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8`/`PYTHONUNBUFFERED=1`，日志**追加**写 `logs\era5_fast_download.log`）。
  现状 **tmax 204/480 个月**（1984–2001 齐；2000/2002 在队），**sp 0.25° 0/480** ⇒ 第十一批记的
  "tmax 144 个月 / sp 全缺" 已过期。窗口是否乱码**必须靠 UIA 读屏核验**
  （`pwsh -NoProfile -File %TEMP%\dsh_window_text.ps1` 读真实文字；不要只看字体设置）。
- **★ 并发上限实测 = 3**：`--jobs 6` 连排两轮、**12 个请求全被 `rejected`**（当时队列为空也拒），
  `--jobs 3` 则全部 `accepted` ⇒ 平台限的是**同数据集"排队中请求数"**，与带宽无关；被拒会冷却重试、不丢月份。
- **★ 新增"在队年份台账"，根治"重启就重复提交"**：`download_era5_fast.py` 提交某年时登记进
  **`logs\era5_pending_years.json`**，该年 12 个月落盘或该请求失败/被拒 ⇒ 自动注销；记录超 **24 h 自动解锁**
  （防某年永远卡住）。规划时跳过台账里的年份，日志打
  `⏸ 跳过 N 个「上一轮已提交、CDS 还没出结果」的年份：…`；`--dry-run` 也会打 `排队中   : …`。
- **★ 新增 `python/adopt_cds_jobs.py` + `run_era5_adopt.bat`**：把服务端 `successful` 的任务下载回月文件
  （按文件时间坐标判年份、逐月过 `verify_month`），已收 id 记 `logs\cds_adopted_jobs.json`（避免重复下载）；
  参数 `--list` / `--max-jobs`(5) / `--since-hours`(72) / `--all` / **`--wait-live`**（轮询在队任务、出结果即收，
  配 `--poll-sec`(60) / `--max-wait-min`(0=一直等)）。**bat 已改成"先 adopt 收割、再启动引擎"** ⇒
  2026-10-14 22:30 实测：`已就位 204 个月，待下 276 个月` → `⏸ 跳过 2 个…年份：2000, 2002` →
  `待下 252 个月 / 21 个请求` → 直接排 2003/2004/2005，**没有再重复排 2000/2002**。
  ⚠️ **有在队任务时绝不要跑 `--clean-queue`**（它删 `accepted`/`running`）；在队任务**不受关窗/关机影响**，
  服务端会自己跑完 ⇒ 想恢复先 `adopt --list`。
- **★ CDS 任务接口（本轮全部结论的来源）**：`GET {url}/retrieve/v1/jobs?limit=N`（header `PRIVATE-TOKEN: <key>`）
  列任务；`GET {url}/retrieve/v1/jobs/<id>/receipt` 可看**终态**任务申请的是哪一年（在队时 404）；
  ⚠️ **2026-10-15 更正：在队任务其实也能读到请求体** —— `GET …/jobs/<id>?request=true&log=true` →
  `metadata.request.ids`，见第十三批；所以"在队任务无法映射年份、只能自己登记台账"的说法已作废（台账仍保留，
  用于补"刚提交、实况还没刷出来"的几秒窗口）。
  `DELETE {url}/retrieve/v1/jobs/<id>` 精确删单个。据此删掉 3 个**重复**在队任务、只留排得最久的两个。
  另一发现：**完全相同请求的重复提交直接回缓存结果**（两个不同 jobID 的 `results.href` 指向同一个对象、几乎瞬时）
  ⇒ 重复提交"已算过"的年份几乎免费，只有"从未算过"的年份才真占队列槽位。
- **★ 10-14 21:06 的下载中断 = 外部 `TerminateProcess`**（窗口尾行 `exit code = -1` /
  `[已退出进程，代码为 4294967295 (0xffffffff)]`）：`download_era5_fast.py` 只有 `sys.exit(main())`，
  `main()` 只返回 0/1；`--log` 把 stdout/stderr 都 tee 进日志 ⇒ 异常必留痕，而日志**无任何 traceback**、
  脚本自己的收尾横幅也没打出来 ⇒ 不可能由脚本返回。已排除 bat 末尾的 `pause`（用户按的就是它）、计划任务、
  睡眠/关机、Windows 更新、Defender；`21:06–21:11` 无 PowerShell 4104 脚本块事件、无 `taskkill` prefetch，
  而 `%TEMP%\dsh-display-watch.log` 明确记着**同机另一个 agent 会话**在该时段反复起 `python`/`pwsh`
  （本机同时跑着 D:\opencode、D:\compound-cn 等多个 DSH 会话）⇒ 头号嫌疑是别的会话；
  进程创建审计（Security 4688）当时关闭 ⇒ **无法点名到具体进程**。数据无损，恢复流程 = `adopt` → 原样重启。
- **★ 代理与吞吐实测**（回答"是不是走代理 / 为什么这么慢"）：cdsapi 用 `requests`、继承系统代理，
  实测**确实经 `127.0.0.1:7890`**；**代理不是瓶颈**——单连接下 ECMWF 对象存储经代理 **68 kB/s**、
  直连只有 **37 kB/s（直连反而慢 1.9×）**，8 MB Cloudflare 经代理 800 kB/s；CDS 单流只给 **44–96 kB/s**
  且会中途断流（`IncompleteRead … attempt 1 of 500`，断点续传不丢数据）。**总吞吐随连接数近线性**
  （实测 2/4/8 连接 = 90/198/687 kB/s）⇒ 慢的根因是 **CDS 队列等待 + 排队上限（=3）**，
  整个 ERA5 剩余量只有 ~1.5 GB，不是带宽问题。

**2026-10-15 第十三批：查明"6.5 小时零产出"= CDS 对该数据集的全局拥塞；引擎改为"按平台实况去重 + 运行中收割 + 自动续轮"**：
- **现象**：10-15 15:20 起窗到 22:05，**6.5 小时 0 个月落盘**（tmax 仍 252），日志
  `已完成 0/216 个月（失败 72）` / `⏳ CDS 排队限流…冷却 300s` / `第 N/4 次失败: SSLError`。
- **★ 根因（有证据，别再怀疑脚本/代理/参数）**：被拒原文
  `Number queued requests for this dataset is temporarily limited` ⇒ **平台按数据集算的全局拥塞**。
  当天该数据集 200 条任务 **141 rejected / 10 successful（全是 10-14 的）**；我们 4 个 `accepted` 的年份里
  **2004（10-14T14:30 UTC 提交）排队 24 h 仍 `updated == created`** ⇒ 平台连"开始算"都没排到。
  **SSLError 实测发生在 cdsapi 的"轮询"阶段**（`/api/retrieve/v1/jobs/<id>?log=True&request=True`，
  `SSLEOFError(8,'UNEXPECTED_EOF_WHILE_READING')`）——而 `client.retrieve(ds, req, tmp)` 一句里
  **提交 + 轮询 + 下载是连在一起的**，所以旧引擎把"轮询失败"当"提交失败"重投 ⇒ **这才是 10-15 那 12 条重复件的来源**。
- **★ 在队任务的请求体可以读回来（推翻第十二批的"必须自己登记台账"）**：
  `GET {url}/retrieve/v1/jobs/<id>?request=true&log=true` → `metadata.request.ids`
  = `{day, area, year, month, variable}`（**普通 GET 看不到**；偶发返回空 ids，重试一次即得）。
- **引擎 5 处改动**（`python/download_era5_fast.py`，已 `py_compile` + `--selftest` 通过）：
  ① `live_job_keys()` / `queued_years()`：按平台实况识别"这一年已在队"，提交前跳过（抛 `AlreadyQueued`）；
  ② `retrieve_with_retry` 异常分支先 `queued_years(force=True)`：**POST 撞 SSLError 但平台已受理时不再重投**；
  ③ `reconcile_pending()`：开局把台账里"平台上已无在队任务"的年份解锁（实测清掉 2012/2013/2014、保留 2004）；
  ④ `harvest_loop()`：运行中每 10 分钟跑一次 adopt 逻辑，平台跑完的任务当场落盘；
  ⑤ `--loop-minutes 10`：一轮跑完仍有缺月就等 10 分钟重新规划，**窗口不关**（bat 已带该参数，
  title = `ERA5 download - harvest CDS first, then tmax + sp (3 jobs, auto-loop)`）；另有 `LIVE_CAP_MIN = 6`
  限制"我们最多占几个队列槽位"。
- **10-15 22:26 实测**：窗口里 `⏸ 跳过 4 个「CDS 队列里已经有」的年份：2004, 2006, 2007, 2008（平台实况 4 个 /
  本地台账 1 个）`；新排的 2009/2010/2011 先被拒、**重试后在 22:26 全部 `accepted`**（且未产生任何重复件）；
  已删掉唯一的精确重复件（第二个 2008，`f97ede65`，`DELETE → 200 dismissed`）。
- **逐小时 `reanalysis-era5-single-levels` 是另一条路（备选，暂不走）**：22:17 实测小请求**立刻 accepted**
  （同期 daily-statistics 是"投什么拒什么"），但它同样 `updated == created` 未被开始算；代价是体积 ~60 GB
  （19 年 tmax + 40 年 sp，欧洲框 0.25° 逐小时）且日最高/日均要本地自己算 ⇒ **等用户拍板**。

**2026-09-25 第十批：ERA5 下载引擎（分块 + 低并发 + 限流退避）+ 查明 CDS 三条硬约束**：
- **新增 `python/download_era5_fast.py`**：统一承载 ERA5 tmax / sp 的 CDS 下载。
  **请求粒度由 `--chunk-months` 控制：默认 12（一次申请一年）**，`1` = 一次一个月、
  `6` = 半年；并发 `--jobs`（默认 2）。返回结果在本地按 12 个月切开、**逐月过旧脚本的
  `verify_month()`**，所以 `config.py` / `phase5_humid.py` / `download_phase5.py` **下游零改动**。
  兼容平台两种返回形态（单个多月 `.nc` / zip 内每月一个 `.nc`）。`--selftest` 纯本地自检
  （含 zip 多文件分支）；`--clean-queue` 清在队任务；`--log` 脚本内置 UTF-8 日志。
- `download_era5_tmax.py` / `download_era5_sp025.py` **已接上该引擎**（同粒度默认，
  加 `--jobs` 重叠排队）；新增 **`run_phase5_fast_download.bat`**（显式窗口 + 日志）。
- **★ 实测 CDS 三条硬约束**（决定方案上限，详见 `待办.md` §1）：
  ① **单请求 size 上限 = 400 天**（costing 接口：1 年 366 OK、2 年 731 > 400 被拒）⇒ 12 个月是
  平台允许的最大块；② **同数据集"排队中请求数"临时受限**，超限时**连单月请求也被拒**
  （HTTP 201 → 12 s 后 `rejected`；真实原因只在 `GET /jobs/<id>/results` 里：
  `Number queued requests for this dataset is temporarily limited`）⇒ 并发默认 2；
  ③ **耗时几乎全在按请求排队、与请求大小无关**：2026-09-25 凌晨两个年请求分别 **3.1 h / 6.2 h**
  返回并各交付 12/8 个月文件 ⇒ 队列槽位才是瓶颈，"一月一请求"需约 12 倍排队次数。
- **Ctrl-C / 关窗口不会取消服务端任务**，被遗弃的 `accepted` 任务继续占额度；
  换入口重跑前先 `python python\download_era5_fast.py --clean-queue`。
- 慢的根因时间线（旧脚本逐月）：1984-02 用 25 s、1984-03 用 105 s、**1984-04 排了 29 min**。
- **★ OAFlux 已下载成功（换源）**：WHOI FTP/HTTP、NOAA PSL、APDRC 四个传统入口 2026-09-25
  实测**全部不可达**（端口 21 超时 / 502 / 404 已撤下 / 超时），代理也救不了。改走
  **NSF NCAR GDEX / OSDF 公开匿名 HTTPS**（= RDA ds260.1 的 GDEX 镜像，地址从
  `rda.ucar.edu/datasets/d260001/filelist/2` 页内嵌直链取得）：
  `https://osdf-director.osg-htc.org/ncar/gdex/d260001/monthly/evaporation/evapr_oaflux_YYYY.nc.gz`
  （月蒸发率 1° 全球、变量 `evapr`、units=cm/yr，1958–2022 齐全）。已写入
  `download_oaflux_evap.py` 作为**第一优先 discoverer**，`.gz` 自动解包；
  并修掉 `merge()` 里两个**从未被执行过**的死代码 bug（把 DataArray 当 Dataset、
  原始文件 `time` 只是 1..12 月号未补年份）。结果：
  `data/OAFlux/OAFlux_evap_1991_2020_monthly.nc`（360 步 1991-01…2020-12，47 MB，
  JAS 地中海框均值 112 cm/yr），`phase5_humid.py check` 中 OAFlux 已 **[OK]**。
  注：**1° 是 OAFlux v3 的原生分辨率**，与 `docs/复现方案.md` 的规划一致，不存在更高分辨率版本。

**2026-09-24 第七批：图5/图6 出图落地 + PHASE_C 五处口径更正（第五轮一致性审查）**：
- **新增**：`python/fig5_sst_trend.py`（图5 a/b/c 趋势图，含 `--synthetic` 版式自检）、
  `python/fig6_wbt.py`（图6 a–f，含合成 demo 路径 `--stats`）、`python/table1_attribution.py`（Table 1）、
  `results/phase5_selftest.py`（纯合成自检 → `ALL PHASE5 SELFTESTS PASSED`）。
- **★ 推翻 `TECHNICAL_SPEC_PHASE_C.md` 五处关键口径**（逐像素校准论文原图）：
  ① 图6a/b 不是"每年一根柱"，而是**14 条曲线**（x = 阈值 WBT 25.5–27.1 °C / SH 19.0–20.9 g/kg）；
  ② 非复合年是论文 Fig.6c 图例直接列出的 **11 年**（1984/1986/1988/1990/1991/1992/1993/1996/2000/2004/2008），
  不是 S1 判读的 8 年——**caption 的"11"对、正文的"10"错**；
  ③ 锚点"非复合年 <5 天"实为 **≤~8 天**（2004 ≈7.8、1992 ≈3.9）；
  ④ ERA5 下载框太小（论文 Fig.5 范围 lon −15…43.5 / lat 29…69）→ **sp 0.25° 下载框已扩到
  `[70,−16,28,44]`**（用户尚未下载，零代价修正）；
  ⑤ 图6d–f 是**全域陆地**地图（lon −10…40.5 / lat 35…62），不是 100 km 缓冲域。
- **代码同步**：`config.WBT_NONCOMPOUND_YEARS` 改为论文 11 年（S1 8 年降为 `_S1` 敏感性）、
  新增 `WBT_EXCEED_THRESHOLDS`/`SH_EXCEED_THRESHOLDS`/`ERA5_MAP_BOX`；
  `phase5_humid.stats_fig6` 新增逐阈值扫描 `exceedance_curves`，6d–f 改全域；
  `fig5_sst_trend.py` 的地图范围与色板按原图；`fig6_wbt.py` 的配色/轴范围/色标按原图。
- 详见 `results/规划一致性审查.md` 第五轮（A6–A10 / B6–B10 / C1–C4）。

**当前进度（2026-10-30）**：
- **Phase 0–4（观测链路）✅ 完成**：检测→配对→复合→**图1/图2/S1/S2** 已出图；图1j-l 为 MHW 包络口径（方案 B），
  **图1j/l 绝对量级已定稿为"未复现项"**（`results/复现报告.md` §6）。
- **Phase 5（湿热）🔶 代码全就绪、数据未齐**：`check` 里 tmax 480/480 ✅、OAFlux/OISST/E-OBS ✅，
  唯缺 **sp 0.25° 204/480**（缺 276 个月，引擎在等 CDS 队列）⇒ **图5b / 图6 / Table 1 尚不能出**；
  图5a（SST 趋势）/ 5c（比湿趋势）已用真实数据核对（中位 0.59 / 0.278）。产物 `wbt_daily.nc`、`fig5_stats.json` 未生成。
- **Phase 6（归因）🔶 数据全齐、代码就绪、未跑全量**：CESM1-LE **80 件 6.2 GB**（20 成员 × all/xghg × TREFHT/SST），
  体检异常 0；口径决策 D7.1–D7.5 已定；现有产物仅 P0 三成员（`_p0chk`/旧 tag），
  **全量未跑**（待 sp 齐后按"快速参考"里那 5 条命令跑 `_v4`）。审计修复累计 F1–F13（F13 = `_prefer_gdex` 去重）。
- **Phase 7（环境固化 / 一键入口）✅ 完成**：`run_all_phases.bat` / `python/run_phases.py` / `requirements.txt`。
- 详见 `results/复现报告.md`（§2.2 未完成清单、§3.1 CESM 切片口径与体检）。

> ★ **换对话/换 agent 继续时**：先读 **`待办.md` 顶部的「断点续做」一节**——那里固化了
> 当前状态、数据下载完成后要跑的确切命令、要核对的锚点位置、已登记的交叉检查项、
> 已定稿不必再追的未复现项，以及两处待拍板口径。**不要依赖上一轮 agent 的记忆。**

**2026-09-24 第九批：Phase 7 打包（一键入口 + 环境固化）+ 自检捕获 gev 辅助函数 bug**：
- **新增 `run_all_phases.bat` / `python/run_phases.py`**：Phase 0→7 一键串联，
  每步调用文档里的**同一条命令**；缺数据自动跳过并说明缺哪一项；支持 `--dry-run` / `--phases` / `--tag`，
  末尾打印"完成/跳过/失败"总表与**论文图画清单核对**（图1–6 / Table 1 / 论文版 S1）。
- **新增 `requirements.txt`**：Python 依赖锁定本机实测版本 + R 侧（heatwaveR 0.5.5 等）安装说明。
- **`results/phase6_selftest.py` 新增第 6 节**（gev 辅助函数断言）——**当场捕获一个真 bug**：
  `_annual_exposure_from_masks` 里混进草稿表达式 `daily[years == uyears[0]] * 0 + …`，
  会把结果撑成 (n_days, n_key) 的三维数组。已修复，并让生产函数 `_member_exposure_series`
  **改走同一个被测试的函数**（消除"测的不是跑的那份"的漂移风险）。修复后 `gev` 结果不变
  （compound 100 年 Gap 86.8 年，与修复前同量级）。
- 文档同步：`待办.md`（懒人入口 + 全绿清单）、`docs/阶段计划.md` §4（Phase 7 完成）、
  `results/复现报告.md` §9（一键/分步复现命令 + 四套自检）。

**2026-09-24 第八批：图4 数据链路 + 论文版 Supplementary Fig. S1**：
- `phase6_cesm.py` 新增 **`gev` 子命令**：从 `mhw*_*.csv` / `thw*_*.csv` 汇总**海洋 / 陆地 / 复合**三类
  区域年暴露序列（地中海&黑海，点均值），调 `gev_return_period.py` 做 FixGHG→ALL 重现期映射，
  输出 `results/tables/phase6_gev{tag}.json`（`fig4_return_period.py` 直接消费）。
  P0 三成员实跑通过（N=66/组）：marine 208 vs 28、terrestrial 48 vs 11、compound 41 vs 3.7 天/年。
- `python/figS1_annual_maps.py` — **论文版 Supplementary Fig. S1**（1984–2023，4×10=40 面板年际
  复合日空间分布，色标 0–50 天）；与既有的 `figS1_jkl_maxcell.*`（图1j–l 替代口径，仅沿用旧编号）不是同一张图。
- `fig4_return_period.py` 修 CI 夹取导致的负误差棒崩溃（inf 按轴顶处理并强制 lo ≤ med ≤ hi）。

**2026-09-24 第六批：Phase 5 数值链路 + 图3/图4 绘图代码 + 图版式逐像素校准**：
- **新增代码**：`python/calc_wbt.py`（RH / WBT(Stull + psychrometric 迭代) / SH / 趋势；25 项合成自检全过）、
  `python/gev_return_period.py`（GEV MLE + bootstrap + FixGHG→ALL 重现期映射 + 图6c 阈值曲线；16 项自检全过）、
  `python/phase5_humid.py`（Phase 5 主链路：`check` / `fields` / `stats` / `all`）、
  `python/fig3_attribution.py`（论文图3，已用 P0 产物实跑出图）、
  `python/fig4_return_period.py`（论文图4，含 `--demo` 版式自检图）。
- **`python/load_data.py` 扩展**：ERA5 tmax / d2m / sp（0.25° 与 1.0° 兜底）/ OAFlux 加载器；
  统一维度名（`valid_time`→`time`）、经度（0..360→−180..180）、纬度升序、时间戳 floor 到日；
  `check_phase5_inputs()` 做开工前就位检查。实测 tmax(1 月) / d2m(全年) / sp 1.0°(全年) 均正常加载。
- **★ 图版式逐像素校准（推翻 SPEC 两处描述）**：`TECHNICAL_SPEC_PHASE_B.md` §B.4 称图4 为"双对数"——
  **实测 x 轴是 5/10/20/50/100 等距分类轴**；且 **§B.5 的图4 锚点（2.1/3.3/5.5/11.5/20.7 等）是图上
  印刷的 CI 下界，不是柱高**（柱高 = 中位数，图中不印）。图3 为 **2×2**（a/b 欧岸、c/d 地中海&黑海），
  x 上限上行 105、下行 100；PR 面板 b 为 1–1000 对数、d 为 1–100 对数；不确定带 alpha=0.40。
- **文档**：新增根目录 **`待办.md`**（操作指引：下载 → 复核 → Phase 5 → Phase 6）与
  **`docs/阶段计划.md`**（阶段计划、图号清单、验收锚点、阶段闸门）。

**2026-09-23 第四批：Phase 6 归因管线正确性审计 + 修复（任务 D）**：Lead + 3 名独立审计员四路并行，逐项核验 `python/phase6_cesm.py`。**发现 2 个 P0 级检测层错误**——① `_pooled_threshold_t2m` 的 `axis` 崩溃使 206 个陆点共用一条全欧阈值曲线（阈值 mean\|Δ\| 8.26 °C）；② `_run_events` 是「先桥接后过滤」而 heatwaveR `proto_event` 是「先过滤后桥接」（450 例模糊测试 429/450 不一致）；另模型侧 MHW 阈值缺 11 天窗。**3 个 P0 级工程缺陷**：`--members 20` 静默只跑 3 个成员、阈值缓存无成员指纹、不支持 leave-one-out。已修复 9 项（F1–F9）并给出前后对比：THW 的 ALL/XGHG 事件比 1.73→3.01，`PR=48.0/FAR=0.98` **作废**（修复后该阈值下 P_fix=0），可判读阈值（20.7 天）下 PR=52.0/FAR=0.981。**观测链路（Phase 1–4）不受影响**（全部走 R heatwaveR）。详见 **`results/Phase6审计报告.md`**（6 份分报告已合并为一件：§1 汇总 / §2 修复对比 / §3–§6 四份分报告全文）。

**2026-09-23 第五批：第三轮规划一致性审查（三路独立审计）**：发现 **3 项 Phase 6 全量开跑前的 P0 阻塞项**——① `gdex --members 20` 的产出命名（`{var}_{exp}_{mem}_2000-2021.nc`）与 `phase6_cesm.py` 的文件发现模式不匹配 ⇒ prepare 静默跳过新成员、detect 在成员 004 抛 `FileNotFoundError`（**全量实际只会跑 3 个成员**）；② `_load_sst_points` 未做 POP SST「物理日 +1」标签校正，MHW 掩码相对 THW 整体晚 1 天，而审计报告 §0.5 与 §四 C11 对此**给出相反结论**（C11 的"已否证"裁决被本轮实测推翻：CAM `date` 为区间左端、POP `time_bound` 为右端）；③ `_sweep_one` 不产出 FAR 置信区间，而 Table 1 验收锚点需要。另修正：SPEC §9.3 的 Phase 6 命令因 `--tag` 两端默认值不一致而**逐字不可执行**、`run_all.py` 已改走 `detect_events.R`（文档滞后）、D7 五项口径未进任何规格文档、CESM 全量体量与 E: 盘剩余空间（190 GB）自相矛盾（~750 GB 只适用于 raw 路径）。详见 `results/规划一致性审查.md`（第三轮）。

> **第三轮代码修改（2026-09-23，用户指令"执行修改但不跑代码"）**：上述 3 项 P0 已在源码层修掉——
> **F10** `_load_sst_points` 对 POP SST 时间轴回退 1 天（标签=物理日+1）；**F11** 文件发现兼容
> gdex 命名 + `download_cesm1le.py` 保留 KMT/TLAT/TLONG、`_mask_sst_box` 不再空间裁剪；
> **F12** `_sweep_one` 补 `FAR_lo/FAR_hi` 及区间列（Table 1 先决条件）；Phase 6 口径常量下沉
> `python/config.py`；`results/phase6_selftest.py` 补 5 项断言 + 新命名测试节。
> **⚠️ 未运行任何代码 ⇒ 未验证**：首次运行前先 `python -m py_compile python\phase6_cesm.py
> python\download_cesm1le.py python\config.py` 与 `python results\phase6_selftest.py`；
> 旧 `_x/_x2/_x3` 产物属未校正口径，需用新 `--tag` 重跑 `detect`+`compound`。
> 细则见 `results/规划一致性审查.md` 第三轮·代码修改记录。

**2026-09-23 第三批：下载脚本就绪 + 图1j/l 定稿**：① Phase 5/6 下载脚本全部编辑就绪并 dry-run 验证（**均未运行**）——新增 `python/download_era5_sp025.py`（0.25° sp 欧洲框，数据集 3b+），给 `download_era5_tmax.py` 补 `--dry-run`，新增两个一键入口 `run_phase5_downloads.bat` / `run_phase6_download.bat`；② 图1j/l 定稿为未复现项（THW 硬约束 23.2/35.1/48.3 天 ⇒ 共超标口径封顶；MHW 包络对区域框高度敏感；8 区域框扫描无一口径满足论文四约束）；③ 修正 `diagnose_subbasin.py` 的归一化（`Σwi·d/n` → `Σwi·d/Σwi`），并据此**撤销**复现报告与修订报告中不可复算的"西地中海弧 76.0/68.5 唯一全面命中"结论。详见 `results/复现报告.md` §6 与 `results/方法与证据.md §3`。

**2026-09-23 规划文件一致性审查与修正**：对照论文 Methods/Results 全文审查全部规划文档，6 处实质性不一致已修正——① FAR 公式写反（SPEC §3.9 / PHASE_B，实际代码本正确）；② 归因统计单元改为"区域年暴露时间池化 440 模型年"（论文口径）；③ 新增 GEV 重现期规范（SPEC §3.9b + PHASE_B 步骤5；图4 marine/terrestrial/compound 三类，2.5–97.5% CI 与图3 的 5–95% 区分，config 新增 `GEV_RETURN_PERIODS`/`GEV_CI`）；④ `DATA_REQUIREMENTS` 立项 ERA5 sp 0.25° 欧洲框下载任务（数据集 3b+，现 sp 为 1.0° 偏差）；⑤ PHASE_A 图1 面板年份/区域、PHASE_C 蒸发/SST 验证锚点按论文更正；⑥ `docs/复现方案.md` 全面同步（E-OBS 1983–2023、复合定义方案 B、MHW 工具 R heatwaveR、XGHG=GHG 固定已实证 co2vmr 恒定 303 ppm）。详见 `results/规划一致性审查.md`（第一轮）。

**2026-09-23 第二轮独立复核**：对第一轮结论做独立重核，发现第一轮有 3 处错误/过度声明（其中「100 km 海岸缓冲已在 config」实为**未实现**）、并遗漏 **5 项与论文实质不符**（陆地检测变量 tg vs tx 未论证、图6c 缺 JJA 季节与 22–28 °C 范围、图6 非复合年选取判据未定义、模型侧检测基准期在规划中缺失、论文 Supplementary Fig. S1 未复现）。随后执行"零风险批次"清理：过期文件名/盘符/CESM 命名、SPEC §5.2–5.4 图1/图2 面板、§3.13 run_all（原误编为 §3.11）、§3.8 WBT 迭代实现、三份 PHASE 文档的 MATLAB 残留、AGENTS.md 检测链路口径统一。**方法学新增项（100 km 缓冲、CESM 基准期、图6c 规格等）待用户拍板后再改。** 详见 `results/规划一致性审查.md`（第二轮）。

## 当前可运行文件

主链路（Phase 1-4，已验证）：
- `python/run_all.py` — Phase 0–3 四阶段主控（预处理→检测→复合→年度指标/CHR/共现概率）
- `python/figures.py` — 图1/图2/S1 出图；`python/fig_jkl_mhw_envelope.py` — S2
- `python/detect_events.R` — **海陆统一热浪检测正式链路**（R heatwaveR）
- `python/phase6_cesm.py` — Phase 6 归因管线（P0 验证版；**2026-09-23 审计修复 F1–F9**：
  检测端与 R heatwaveR 等价、阈值逐点、11 天窗、缓存带指纹、`--members` 作用于全量 20 人名单、
  `--loo`、doy=366 阈值行）
- `python/coastal_buffer.py` — 图6 分析域：海岸向内 100 km 缓冲掩码（Phase 5 前置，已接入 `phase5_humid.py`）

Phase 5（湿热应力，2026-09-24 新增，数值链路已验证）：
- `python/calc_wbt.py` — RH / WBT（Stull 2011 + psychrometric 牛顿迭代）/ SH / JAS 趋势；`python python\calc_wbt.py` 跑 25 项合成自检
- `python/gev_return_period.py` — GEV MLE + bootstrap + FixGHG→ALL 重现期映射（图4/图6c 内核）；自带 16 项自检
- `python/phase5_humid.py` — Phase 5 主链路：`check` / `fields`（逐日 WBT·SH）/ `stats`（图5 趋势 + 图6 统计）/ `all`
- `python/fig3_attribution.py` — **论文图3**（FAR/PR 2×2，按原图逐像素校准）
- `python/fig4_return_period.py` — **论文图4**（重现期位移 1×3；`--demo` 可渲染论文锚点版式自检图）
- `python/fig5_sst_trend.py` — **论文图5**（SST / 蒸发 / 比湿 JAS 趋势三面板；`--synthetic` 版式自检）
- `python/fig6_wbt.py` — **论文图6**（a/b 超阈曲线、c 重现期、d–f 复合日最大 WBT 场）
- `python/table1_attribution.py` — **论文 Table 1**（62/78/72 天三点的 FAR/PR + 论文对照列）
- `results/phase5_selftest.py` — Phase 5 纯合成自检（不读观测）→ `ALL PHASE5 SELFTESTS PASSED`
- `python/figS1_annual_maps.py` — **论文版 Supplementary Fig. S1**（1984–2023 年际组图，4×10 面板）
- `phase6_cesm.py gev` — 图4 的海洋/陆地/复合年暴露序列 + GEV → `results/tables/phase6_gev{tag}.json`

⚠️ **检测链路口径提示**：`python/detect_thw.R` 有吞错 bug，**仅存档勿用**。
**（第三轮更正）`python/run_all.py` 现已海陆双路都走正式链路 `python/detect_events.R`**
（`run_all.py:47,73-95,161-181`，2026-09-23 提交 `e622993`）——此前"THW 环节仍指向
`detect_thw.R`"的说法已过期；`detect_thw_wrapper.py` 仅保留供单点复核。
另：全链路 `smoothPercentile=FALSE`，偏离两包默认（TRUE/31 天窗），理由见 `results/复现报告.md` D2。

下载工具：
- `python/download_cesm1le.py` — CESM1-LE（AWS zarr / GDEX）。**2026-10-30 起官方口径 = `--engine dap2`**
  （自写 `python/dap2.py`，把欧洲框/子网格当 DAP2 约束直取；本机 netCDF4 DAP 通道损坏、pydap 慢 40 倍）；
  配套入口 **`run_cesm_dap2_atm.bat`**（大气 6 路分片）与 **`run_cesm_dap2_ocn.bat`**（海洋 6 路分片，
  走子网格 9.2% + pad 回全球）；进度 `show_cesm_progress.bat`。旧入口 `run_p0_download.bat` /
  `run_phase6_download.bat`（`--members 20` 整文件口径）仍在，但**全量已下完，别重跑**。
- `python/dap2.py` — **DAP2 最小客户端**（`requests` + 手解 XDR 大端；每数组前 8 字节头必须跳过）。
  `.dds`/`.das` 打开 10 s（pydap 86–123 s）。
- `python/download_era5_tmax.py` — ERA5 日最高气温（CDS daily-statistics；支持 `--dry-run`）
- `python/download_era5_sp025.py` — ERA5 **0.25°** 地表气压欧洲框（数据集 3b+；支持 `--dry-run`）
- **`python/download_era5_fast.py`** — 上面两项的**分块并发引擎**（`--chunk-months` 选粒度，
  **默认 12 = 一次申请一年**；2 并发 + 限流退避；`--selftest` 本地自检 / `--clean-queue` 清在队任务）；
  一键入口 **`run_phase5_fast_download.bat`**
- `python/download_oaflux_evap.py` — OAFlux 蒸发（**主源 = NSF NCAR GDEX/OSDF**，WHOI/PSL/APDRC 四镜像降级备份）
- `run_phase5_downloads.bat` — 一键跑 tmax + sp 0.25° + OAFlux（Phase 5 的全部输入）
- **`python/adopt_cds_jobs.py`** + **`run_era5_adopt.bat`**（2026-10-14 新增）— 认领**服务端已跑完**
  （`successful`）的 CDS 任务并切回月文件，已收 id 记 `logs\cds_adopted_jobs.json`；`--list` 只看清单、
  `--wait-live` 轮询在队任务出结果即收、`--since-hours` / `--max-jobs` / `--all`。
  **`run_phase5_fast_download.bat` 已把它当第一步（先收割、后下载）**——这样重启引擎不会重复排队，见第十二批。
- `scripts/translate_to_word.py` — 读取 `pdf_extract/` 图片生成中文翻译 Word（注意：其引用的图片文件名与当前 `pdf_extract/` 实际文件名不一致，需先核对）

数据格式转换（2026-10-17 新增）：
- **`python/make_yearly_d2m.py`** + **`run_make_yearly_d2m.bat`** — 把 `d2m_global_daily/` 的
  573 个**月度 netCDF-4/chunked/zlib** 文件合并成 **classic netCDF-3（CDF-2 64-bit offset，不压缩不分块）**
  年度文件 `E:\2607compound\data\ERA5\d2m_yearly\d2m.era5.daily.YYYY.nc`（≈1.4 GB/年，约 45 s/年）。
  **动机**：用户那台机器的 GrADS 对这些文件报 `NetCDF: Unknown file format` / `nc_get_vara_double failed; NetCDF: HDF error`
  ⇒ 已实测确认**源月度数据完好（573/573 头正常、纳值 0%）**，坏的是年度文件那一层（截断 / chunked+deflate 读不出）；
  GrADS `sdfopen` 只吃 classic 格式。全量 1979–2026 已生成 **48 个 / 67.3 GB**，
  审计脚本 `logs/audit_yearly_d2m.py`（格式/天数/时间轴连续性/网格/缺测/量程）→ **47 好 + 1 未走完(2026 止于 09-03) + 0 坏**。
  `--check-only --out <dir>` 可体检任意目录里的年度文件；`--format NETCDF3_CLASSIC` 可出更老的格式（单文件 <2 GB 时可行）。
  操作口径见 `待办.md` §「d2m 年度文件"GrADS 打不开"已修」。

> **数据下载进度（2026-10-30 实测）**：ERA5 **tmax 480/480 ✅**、**sp 0.25° 204/480**（引擎
> `python\download_era5_fast.py` 在跑，本轮计划 276 个月，卡在 CDS 队列，只能等）；
> **CESM1-LE 80 件全齐 ✅**（6.2 GB）；OAFlux ✅。**唯一未齐的就是 sp**，图5b / 图6 / Table 1 等它。

## 目录结构（已建成；`data` 为 NTFS Junction → `E:\2607compound\data`）

```
D:\2607compound\        ← 工作区根目录（代码、文档、结果）
├── 待办.md              # ★ 你的操作指引（下载 → 复核 → Phase 5 → Phase 6），先读这份
├── data/                # NTFS Junction → E:\2607compound\data（合计 ~330 GB，2026-10-30 实测）
│   ├── OISST/           # 48.1 GB（全球合并件 + 欧洲裁剪件）
│   ├── E-OBS/           # 0.9 GB（合并件 14975 天 + 3 个分段原始）
│   ├── ERA5/            # 150.9 GB = d2m_global_daily 78.3（月度×620）+ d2m_yearly 67.3（年度×48）
│   │                    #           + sp 1.0° 4.1 + sp_eur_daily 0.5（206 件）+ tmax_eur_daily 0.7（480 件）
│   ├── OAFlux/          # OAFlux_evap_1991_2020_monthly.nc（47 MB）
│   └── CESM1-LE/        # raw/（3 成员整文件 109 GB）+ proc/（20 成员切片 80 件 6.2 GB）
├── python/              # 全部处理 + 绘图代码
├── results/             # 产物 + 文档（2026-09-23 整理，见 results/README.md）
│   ├── 复现报告.md        # ★ 主报告：进度 / 锚点总表 / 决策 D1–D7 / 偏差清单
│   ├── Phase6审计报告.md  # Phase 6 审计（6 份合并）：§1 汇总 §2 修复对比 §3–§6 分报告
│   ├── 规划一致性审查.md   # 规划文件 vs 论文两轮审查（合并）
│   ├── 方法与证据.md      # 目视比对 / E-OBS 核查 / S1 读取 / R-Python 交叉验证 + 2 份历史存档
│   ├── README.md         # 本目录导航
│   ├── globalize_mhw_idx.py  # ★ 被 run_all.py 运行时调用，勿移动
│   ├── build_oisst_clip.py / build_domains.py / run_detection_R.py  # Phase 0/1 入口
│   ├── phase6_selftest.py    # Phase 6 口径纯合成自检
│   ├── figures/ tables/ intermediate/ s1/   # 出图 / 快照 / 中间产物 / S1 裁剪
│   └── tools/            # 诊断与复算脚本，按主题分组（见 tools/README.md）
├── docs/                # 主论文/补充材料 PDF、复现方案.md
├── pdf_extract/         # 从 PDF 提取的论文原图
└── scripts/             # 工具脚本（extract_paper_figs.py、translate_to_word.py 等）
```

> 注：`matlab/` 目录**不存在**——绘图已全面切换 Python (matplotlib + cartopy)，
> 三份 PHASE 文档中的 MATLAB 段落均标注为"已弃用，仅作对照"。

## 技术栈（全量）

- **Python ≥ 3.10**：xarray, numpy, scipy, matplotlib, cartopy, joblib, pandas（`marineHeatWaves` 仅作单格点核验，DEPRECATED）
- **R ≥ 4.0**：heatwaveR (**本机 v0.5.5**；论文标注 v0.4.6，两版语义已核验一致), ncdf4, doParallel, foreach — 通过 `Rscript` 调用（**不用 rpy2**）
- **Python 环境**：本机**没有 conda**（2026-10-13 全盘搜过）——用系统 Python 3.13 +
  `python -m pip install -r requirements.txt` 锁定版本；R 由 `Rscript` 直调。

## 关键约束与陷阱

1. **数据依赖极重（2026-10-30 实测 ≈330 GB，E: 剩 114.9 GB）**：OISST 48.1 GB + E-OBS 0.9 GB +
   ERA5 150.9 GB（含 d2m_yearly 67.3 GB 派生件）+ CESM1-LE 129.5 GB（raw 109.3 整文件 + proc 20.2 切片）+ OAFlux 0.1 GB。
   真正的计算瓶颈是 **40 个 CESM 模拟的逐格点热浪检测**（P0 实测 27 s/成员）；
   归因 bootstrap 本身很轻（样本是池化后的 440 个模型年标量）。**CESM 数据 2026-10-30 已全齐，不必再下**；
   下载侧唯一未完成的是 ERA5 sp 0.25°（204/480）。
2. **路径硬编码**：`config.py` 中 `BASE_DIR = D:\2607compound`，`DATA_DIR = D:\2607compound\data`（NTFS Junction → `E:\2607compound\data`）；`translate_to_word.py` 使用工作区内的 `pdf_extract` 和 `results` 目录。已统一。
3. **混合语言调用**：陆地/海洋热浪检测统一走 R，经 `subprocess.run([RSCRIPT_PATH, ...])` 调用
   `python/detect_events.R`（正式链路）；`RSCRIPT_PATH` 与 `DETECT_THW_R_SCRIPT` 定义在 `config.py`。
4. **海洋-陆地网格对齐**：OISST 与 E-OBS 格点不对齐。**不重采样**——用 KDTree 最近邻配对
   （`MAX_GRID_DIST_DEG = 0.5°`，实测 2039 对 / 1434 唯一海点），下游全部按配对索引匹配。
   **CESM 侧另有一套**：POP gx1v6 → f09（实测 0.9424°×1.25°）KMT 湿点映射 + 4-连通海岸边缘 +
   KDTree cos 加权，上限 `MAX_PAIR_DIST_DEG = 1.0` 单位 ≈ **112.2 km**（观测侧 0.5 单位 ≈ 55.6 km，
   **模型侧允许分离约为观测侧 2.1×**），实测 **206 对 / 唯一陆点 206 / 唯一海点 191**。
   `python/phase6_cesm.py` 的 `cmd_pairs`。
5. **WBT 计算输入已确认**：论文明确由 ERA5 的 **Tmax + 露点 + 地表气压**估算**日最高 WBT**；
   具体近似式未给，`TECHNICAL_SPEC.md` §3.8 提供 Stull / 牛顿迭代双实现待定稿。
   **图6 的 100 km 海岸缓冲已实现**：`python/coastal_buffer.py` + `config.COASTAL_BUFFER_KM`
   （实测 1952/4492 格点落入缓冲区；区域口径待确认，见 PHASE_C 步骤 8）。
6. **无包管理/CI 配置**：有 `requirements.txt`（2026-09-24 新增，锁定本机实测版本），但没有 `pyproject.toml`、
   `environment.yml`、`Makefile` 或 CI 工作流。环境需手动搭建。
7. **无单元测试框架**：验证方式是 ① 四套纯合成自检（`calc_wbt` 25 项 / `gev_return_period` 16 项 /
   `results/phase5_selftest.py` / `results/phase6_selftest.py`）② 与论文图表目视比对（锚点总表见
   `results/复现报告.md` §4）③ `python/verify_data.py` 数据完整性检查。

## 快速参考

| 任务 | 命令/说明 |
|------|----------|
| 一键复现 Phase 0-3 | `python python\run_all.py`（缓存命中 ~1 min；全量重检陆地 ~22 min）|
| 出图 1/2/S1/S2 | `python python\figures.py` + `python python\fig_jkl_mhw_envelope.py` |
| **下 Phase 5 全部输入** | **`python python\download_phase5.py`**（VSCode 点开即跑；= ERA5 tmax + sp 0.25° + OAFlux；支持 `--dry-run` / `--skip-oaflux`）。**⚠️ 2026-10-14 起 ERA5 那部分请走 `run_phase5_fast_download.bat`**（显式窗口 + 先收割后下载），两者别同时跑 |
| **下 CESM 全量** | **已完成（2026-10-30，80 件全齐）**；要重跑/补件时用 `run_cesm_dap2_atm.bat` / `run_cesm_dap2_ocn.bat`（`--engine dap2` 分片）。旧的 `python python\download_phase6.py`（整文件口径，+80–100 GB）与 `run_phase6_download.bat` 保留但别用 |
| 下 ERA5 tmax | `python python\download_era5_tmax.py [--dry-run]`（`--merge` 合并） |
| 下 ERA5 sp 0.25° | `python python\download_era5_sp025.py [--dry-run]`（数据集 3b+） |
| 下 OAFlux | `python python\download_oaflux_evap.py [--probe]` |
| 下 CESM1-LE | **已完成**；补件用 `run_cesm_dap2_atm.bat` / `run_cesm_dap2_ocn.bat`，或 `python python\download_cesm1le.py gdex --engine dap2 --member-ids 007 --only-comp ocn`（`aws` 路径 2026-10-20 起不可用） |
| Phase 6 归因（全量，口径已定） | `pairs` → `prepare --members 20` → `detect --members 20 --baseline xghg --loo --tag _v4` → `compound --members 20 --tag _v4 --compound-def envelope` → `attrib --members 20 --tag _v4 --compound-def envelope` |
| Phase 6 口径决策 | 复合=**MHW 包络**(D7.1)；归因=**阈值扫描+62/78/72 参考线**(D7.2)；主口径 **med_mean**(D7.3)；基准期 **XGHG+LOO**(D7.4)；bootstrap **indep**(D7.5) —— 见 `results/复现报告.md` §5 D7 |
| Phase 6 逻辑自检（不读数据） | `python results\phase6_selftest.py` → `ALL SELFTESTS PASSED` |
| **Phase 5 输入检查** | `python python\phase5_humid.py check`（明确列出缺哪一项） |
| **Phase 5 全长链路** | `python python\coastal_buffer.py` → `python python\phase5_humid.py all`（逐日 WBT/SH + 图5 趋势 + 图6 统计） |
| Phase 5 公式自检 | `python python\calc_wbt.py`（25 项）/ `python python\gev_return_period.py`（16 项） |
| **图3（FAR/PR）** | `python python\fig3_attribution.py --tag _v4`（旧产物可 `--agg-eur eur_max`） |
| **图4（重现期）** | `python python\fig4_return_period.py --tag _v4`；版式自检 `--demo` |
| 检查数据完整性 | `python python\verify_data.py` |
| 环境搭建 | 见 §技术栈；关键包 xarray/cartopy/heatwaveR(R)/cdsapi |

## 权威文档

- `TECHNICAL_SPEC.md` — 详细代码规范、API 设计、算法说明（最权威）
- `TECHNICAL_SPEC_PHASE_A/B/C.md` — 阶段 A（观测，图1–2）／B（归因，图3–4）／C（湿热，图5–6）；
  MATLAB 段落均为"已弃用，仅作对照"
- `DATA_REQUIREMENTS.md` — 数据下载步骤、目录结构、验证脚本、优先级
- `docs/复现方案.md` — 论文基本信息、阶段规划、注意事项
- `results/README.md` — **results/ 目录导航（先看这个）**
- `results/复现报告.md` — 进度、锚点验证总表、方法学决策记录 **D1–D7**、偏差清单 §5.1、图1j/l 定稿 §6
- `results/Phase6审计报告.md` — Phase 6 归因管线审计（含修复前后对比与四份分报告）
- `results/规划一致性审查.md` — 规划文件 vs 论文**三轮**审查；**第二轮对第一轮有 3 处更正、
  第三轮给出 3 项 Phase 6 全量开跑前的 P0 阻塞项**（**Phase 5/6 开工前必须先读**）
- `results/方法与证据.md` — §1 目视比对 / §2 E-OBS 拼接核查 / §3 S1 读取与图6年份判据 /
  §4 R-Python 检测交叉验证 / §5–§6 历史存档
- `results/tools/README.md` — 诊断与复算脚本索引（**哪个结论由哪个脚本算出**）
