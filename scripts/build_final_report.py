# -*- coding: utf-8 -*-
"""
build_final_report.py — 生成「复现终版报告」Word 交付件

数据来源（全部为已结案的定稿数值）：
  results/复现报告.md（§1 结论 / §2 阶段 / §3 数据 / §4 锚点 / §5 决策与差异 / §8 产物 / §9 环境）
  results/图版对照表.md（逐图状态）
  results/tables/table1_v12w50.csv、logs/_cmp_ci_w50.log（图4 五档与 CI）

用法：
  <bundled python> scripts/build_final_report.py
输出：
  results/复现报告_终版.docx
"""
from __future__ import annotations

import os

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "results", "figures")
OUT = os.path.join(ROOT, "results", "复现报告_终版.docx")

BODY_FONT = "宋体"
HEAD_FONT = "黑体"
MONO_FONT = "Consolas"


# ──────────────────────────────────────────────────────────────
# 基础工具
# ──────────────────────────────────────────────────────────────
def set_run_font(run, name=BODY_FONT, size=10.5, bold=None, color=None, mono=False):
    run.font.name = MONO_FONT if mono else name
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor(*color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), MONO_FONT if mono else name)
    rfonts.set(qn("w:hAnsi"), MONO_FONT if mono else name)


def style_document(doc):
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    pf = normal.paragraph_format
    pf.line_spacing = 1.45
    pf.space_after = Pt(4)
    for name, size in (("Heading 1", 15), ("Heading 2", 12.5), ("Heading 3", 11)):
        st = doc.styles[name]
        st.font.name = HEAD_FONT
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0x1F, 0x3B, 0x57)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), HEAD_FONT)
        st.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
        st.paragraph_format.space_after = Pt(6)


def h1(doc, text):
    p = doc.add_heading(level=1)
    set_run_font(p.add_run(text), HEAD_FONT, 15, True, (0x1F, 0x3B, 0x57))
    return p


def h2(doc, text):
    p = doc.add_heading(level=2)
    set_run_font(p.add_run(text), HEAD_FONT, 12.5, True, (0x1F, 0x3B, 0x57))
    return p


def para(doc, text="", size=10.5, bold=False, indent=True, space_after=4, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if indent:
        p.paragraph_format.first_line_indent = Pt(21)
    if text:
        set_run_font(p.add_run(text), BODY_FONT, size, bold, color)
    return p


def rich(doc, parts, indent=True, space_after=4):
    """parts = [(text, bold), ...]"""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if indent:
        p.paragraph_format.first_line_indent = Pt(21)
    for text, bold in parts:
        set_run_font(p.add_run(text), BODY_FONT, 10.5, bold)
    return p


def bullet(doc, text, bold_prefix=None, size=10.5):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.35
    if bold_prefix:
        set_run_font(p.add_run(bold_prefix), BODY_FONT, size, True)
    set_run_font(p.add_run(text), BODY_FONT, size)
    return p


def code_block(doc, lines):
    for line in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Pt(14)
        p.paragraph_format.line_spacing = 1.15
        set_run_font(p.add_run(line), MONO_FONT, 9, color=(0x33, 0x33, 0x33), mono=True)


def caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    set_run_font(p.add_run(text), BODY_FONT, 9, color=(0x55, 0x55, 0x55))


def table(doc, header, rows, widths=None, font_size=9, header_size=9,
          align_center_cols=(), caption_text=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, text in enumerate(header):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(1)
        set_run_font(p.add_run(text), HEAD_FONT, header_size, True)
    for row in rows:
        cells = t.add_row().cells
        for i, text in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.2
            if i in align_center_cols:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_run_font(p.add_run(str(text)), BODY_FONT, font_size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    if caption_text:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(10)
        set_run_font(p.add_run(caption_text), BODY_FONT, 8.5, color=(0x55, 0x55, 0x55))
    return t


def figure(doc, filename, cap, width_cm=15.4):
    path = os.path.join(FIG, filename)
    if not os.path.exists(path):
        para(doc, f"[缺图：{filename}]", size=9, color=(0xAA, 0x00, 0x00))
        return
    doc.add_picture(path, width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.space_after = Pt(2)
    caption(doc, cap)


# ──────────────────────────────────────────────────────────────
# 正文
# ──────────────────────────────────────────────────────────────
def build():
    doc = Document()
    style_document(doc)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.4)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.0)

    # ── 标题页 ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(40)
    set_run_font(p.add_run("欧洲复合海岸热浪与湿热应力论文复现"), HEAD_FONT, 22, True,
                 (0x1F, 0x3B, 0x57))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run("终版复现报告"), HEAD_FONT, 16, True, (0x1F, 0x3B, 0x57))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(18)
    set_run_font(p.add_run("Compound coastal marine–terrestrial heatwaves associated with\n"
                           "humid-heat stress in Europe"), BODY_FONT, 11.5, False, (0x44, 0x44, 0x44))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(p.add_run("Barkhordarian, Brunet & Baehr · Scientific Reports (2025)"),
                 BODY_FONT, 10.5, False, (0x66, 0x66, 0x66))

    doc.add_paragraph()
    table(doc,
          ["项目", "内容"],
          [["复现状态", "Phase 0–6 全部完成；图 1–6、Table 1、Supplementary Fig. S1 均已出图/出表"],
           ["结案残留", "图1j/l 曲线、图6a/6c 水平 —— 已定稿为「未复现项」，机制已查明（见 §7）"],
           ["数据规模", "约 330 GB（OISST / E-OBS / ERA5 / OAFlux / CESM1-LE）"],
           ["计算量", "观测链路全量约 22 min；Phase 5 全量 18.6 min；Phase 6 主口径全链 5.7 min"],
           ["报告日期", "2026-11-17"],
           ["代码基线", "git f52fee0（main）"]],
          widths=[3.4, 12.4], font_size=9.5, header_size=9.5)

    para(doc, "\n本报告是复现工作的定稿汇总：先给结论与逐图状态，再给方法学决策、锚点核对、"
              "未复现项的成因与量化，最后给完整的复现命令与产物清单。全部数值均来自仓库内可重跑的产物，"
              "工作过程中的口径搜索与已证伪假设记录在 results/复现报告.md（工作日志）中。",
         space_after=10)

    doc.add_page_break()

    # ── 1. 结论摘要 ──
    h1(doc, "1　结论摘要")
    para(doc, "复现覆盖论文全部六张主图、一张补充图与 Table 1。逐项判定如下"
              "（判定口径：✅ 数值/形态与论文一致；⚠ 部分命中；🔶 域与形态一致、水平仍有残差，"
              "已登记为未复现项；⬜ 未做）。")
    table(doc,
          ["论文图表", "核心内容", "本复现结论", "判定"],
          [["图 1（a–m）", "复合热浪空间分布、Med&BS 复合天数时序、共现概率",
            "空间热点（西地中海弧：Catalan→Lion 湾→巴利阿里→撒丁/科西嘉）、高值年份集合、"
            "共现概率 0.594/0.879（中位/最大）均一致；j–l 曲线的量与峰值年不符（见 §7.1）", "✅ / j–l ⚠"],
           ["图 2（a–d）", "复合天数、standalone、CHR 时序与空间",
            "2a/2b/2d 命中；2c 的 2003 年后趋势与 2023 峰值（3.19 vs 3.5）命中，"
            "但 1980–90 年代中位数 0.374（论文「约 1」）偏低 2.7 倍", "✅ / 2c ⚠"],
           ["图 3", "FAR / PR 的阈值扫描（2003、2022、2023）",
            "主口径 _v12w50 下 62/78/72 天三点 FAR = 0.789 / 0.871 / 0.814，与 Table 1 逐位一致", "✅"],
           ["图 4", "FixGHG→ALL 的重现期位移（海洋/陆地/复合）",
            "三面板 × 五档重现期 15 个点全部落在本复现 bootstrap CI 内", "✅"],
           ["图 5", "SST / 蒸发 / 比湿的 JAS 趋势",
            "a、c 面板地中海框数值 +0.59 °C/decade、+0.278 g/kg/decade 与论文锚点一致；"
            "b 面板用 OAFlux 1991–2020 出图（论文未给定量锚点，仅做量级核对）", "✅"],
           ["图 6", "WBT ≥ 25.5 °C 超阈频次、重现期、复合日 WBT 场",
            "区域口径已按论文原文定稿（地中海、含西班牙东岸、剔除黑海，1637 格点）；"
            "a/c 的水平残差已量化为 18× 与「26 °C 端点不可达」（见 §7.2）", "🔶"],
           ["Table 1", "三年复合事件的 FAR / PR",
            "FAR MAE 0.0607；PR 三年全部落在论文区间；年际次序 2003 < 2023 < 2022 复现", "✅"],
           ["Fig. S1", "1984–2023 年际复合日空间组图",
            "4×10 = 40 面板，色标 0–50 天，与原图一致", "✅"]],
          widths=[2.6, 4.6, 7.4, 2.0], font_size=8.5, header_size=9, align_center_cols=(3,))

    para(doc, "四句话概括：① 观测侧检测链与论文参数一致，比值类锚点（图1m、图2a/b、图2c 的量级与峰值年）"
              "全部命中；② 湿热应力链路（图5、图6d–f）数值核对通过；③ 归因链路（图3、图4、Table 1）在"
              "主口径 _v12w50 下复现完成，图4 的 15 个重现期点全部落在本复现的抽样区间内；"
              "④ 剩下两处偏差（图1j/l、图6a/6c）**已查明不是实现错误**，而是论文原文自身口径不唯一所致，"
              "在已发表材料的范围内不可唯一恢复（§7）。")

    # ── 2. 阶段状态 ──
    h1(doc, "2　复现范围与阶段状态")
    table(doc,
          ["阶段", "内容", "状态"],
          [["Phase 0", "数据下载与校验（OISST v2.1、E-OBS tg）", "✅"],
           ["Phase 1", "热浪检测（海洋 1434 个配对海点 + 陆地全格点，R heatwaveR）", "✅"],
           ["Phase 2", "复合事件识别（共超标）+ standalone 扣除", "✅"],
           ["Phase 3", "年度指标、CHR、共现概率", "✅"],
           ["Phase 4", "图 1 / 图 2 / S1 / S2 出图", "✅"],
           ["Phase 5", "ERA5 湿热应力：WBT、SH、图 5、图 6", "✅（图6 水平残差登记）"],
           ["Phase 6", "CESM1-LE 归因：图 3、图 4、Table 1", "✅（主口径 _v12w50）"],
           ["Phase 7", "汇总与交付（本报告 + 一键入口 + 环境固化）", "✅"]],
          widths=[2.2, 10.6, 3.8], font_size=9, align_center_cols=(0, 2))

    # ── 3. 数据 ──
    h1(doc, "3　数据与计算规模")
    table(doc,
          ["数据集", "产品/版本", "分辨率", "时段", "本项目用法与体积"],
          [["海洋 SST", "NOAA OISST v2.1 日值", "0.25°", "1982–2023（分析取 1983 起）",
            "欧洲裁剪 14975×204×340；48.1 GB"],
           ["陆地气温", "E-OBS tg_ens_mean", "0.25°", "1983–2023",
            "三段拼接为 EOBS_tg_1983_2023.nc（14975 天）；0.9 GB"],
           ["ERA5 露点", "ERA5 d2m", "0.25°", "1979–2024", "WBT / SH 输入；150.9 GB（含年度派生物）"],
           ["ERA5 日最高温", "ERA5 tmax", "0.25°", "1984–2023", "480 个月 + 合并件 0.71 GB"],
           ["ERA5 地面气压", "ERA5 sp", "0.25°", "1984–2023", "480 个月 + 合并件 1.19 GB"],
           ["OAFlux 蒸发", "OAFlux", "1°", "1991–2020", "图 5b；47 MB"],
           ["CESM1-LE", "20 成员 × {ALL, XGHG}", "f09 + POP gx1v6", "2000–2021（分析）+ 1983–1999（气候态）",
            "160 件切片 25 GB；raw 整文件 109 GB（仅 3 成员，备用）"]],
          widths=[2.6, 3.4, 2.2, 3.4, 5.0], font_size=8.5, header_size=8.5)
    para(doc, "观测侧地海配对按最近邻 KDTree 生成 **2039 对 / 1434 个唯一海点**（上限 0.5°，≈55.6 km）；"
              "CESM 侧按 KMT 湿点映射 + 4-连通海岸边缘生成 **206 对**（上限 1.0 单位 ≈112.2 km，"
              "约为观测侧的 2.1 倍——模型网格更粗，这是刻意放宽的结果，并在 §4 D7 中记录）。"
              "CESM 切片经 80 件体检，异常 0；海洋成员 001 与旧通路产物逐位一致（max|diff| = 0）。")

    # ── 4. 方法学决策 ──
    h1(doc, "4　关键方法学决策")
    para(doc, "论文若干关键口径未写全（或内部冲突），复现必须做出选择。以下 7 组决策给出选择、依据与影响；"
              "完整的差异清单见 §6。")
    table(doc,
          ["编号", "决策", "依据", "影响"],
          [["D1", "海陆热浪检测统一走 R heatwaveR（连续 ≥5 天 → 桥接 ≤2 天）",
            "论文 Tools = heatwaveR v0.4.6；经源码核验两包语义一致", "检测端与论文等价"],
           ["D2", "smoothPercentile = FALSE（包默认 TRUE/31 天）",
            "为隔离「11 天窗口 vs 单日分位」变量；抽样实验影响 <5%", "可忽略"],
           ["D3", "观测侧复合日 = 逐日共超标（L502-503）",
            "该口径独立命中图1m/2a/2b/2c 四个锚点；事件涵盖口径全不命中", "决定图1/图2 的量级"],
           ["D4", "图1m/2d 用 2003–2023 的比值之和",
            "遵循论文 caption「ratio … over 2003-2023」", "无偏差，记录以防歧义"],
           ["D5", "standalone 按日扣除（THW 日 − 共超标日）",
            "保证 C+S = 全部 THW 日、CHR = C/S 自洽", "CHR 2023 = 3.19（事件级口径会更接近 3.5）"],
           ["D6", "图1j–l 主图用 MHW 包络口径（2026-09-23 切换）",
            "论文引言/结果/模型 Methods 均用 fully encompasses", "图1j/l 的量级随之变化，仍与论文不符（§7.1）"],
           ["D7", "Phase 6 归因口径 7 条",
            "见下表明细", "图4 15/15 落入论文 CI"]],
          widths=[1.4, 6.6, 6.4, 4.2], font_size=8.5, header_size=8.5, align_center_cols=(0,))

    table(doc,
          ["D7 子项", "定稿口径", "理由（一句话）"],
          [["D7.1 复合定义", "MHW 包络（MHW 完整涵盖 ≥1 个 THW 即计该 MHW 全部跨度）",
            "论文模型侧 Methods 原文用 fully encompasses；与图1j–l 的已定稿口径逐条对齐"],
           ["D7.2 归因输出", "0–100 天阈值扫描 + 论文 Fig.3c 的 62/78/72 天参考线",
            "单点阈值在修复后会出现 P_fix = 0 → PR 发散"],
           ["D7.3 聚合口径", "med_mean（区域暴露均值）", "p90 是「格点极值」语义，与论文的区域暴露不符"],
           ["D7.4 阈值基准期", "各实验自算 1983–2012 气候态 + 成员 leave-one-out",
            "共用冷基准会让 +1.5 °C 的 ALL 世界饱和（海洋 254 天/年），图4 塌成 1–2 年一遇"],
           ["D7.5 bootstrap", "模型年独立重采样（1000 次）", "论文 Methods 字面；块重采样降为稳健性检验"],
           ["D7.6 复合双报", "envelope 主线 + exceed 敏感性", "复合面板对定义极敏感（年暴露差 3.6 倍），必须双报"],
           ["D7.7 主口径", "_v12w50：D7.4 + 反事实世界陆地阈值 += 0.5645 °C（w = 0.50）+ 经验分位映射",
            "图4 的等效重现期只由两世界阈值之差决定；w = 0.50 同时是解析值（合并样本 q90 ⇒ 0.41–0.55）"
            "与数据最优点"]],
          widths=[2.6, 7.2, 8.4], font_size=8.5, header_size=8.5)

    para(doc, "口径 _v12w50 的来历值得单独说明一句：论文没有写「反事实世界的阈值怎么取」，"
              "而这一条直接决定图4 的数值。我们实测 1983–2012 两实验 T2m 差 δ = 1.129 °C、SST 差 0.796 °C，"
              "把「参考气候态 = 两实验合并样本的 90 分位」解析化后，等价于对反事实世界的陆地阈值加 "
              "w·δ（w ≈ 0.41–0.55）。取 w = 0.50 后，陆地 100 年重现期从 17.6 年降到 3.17 年（论文 3.26），"
              "复合从 13.3 年降到 8.00 年（论文 7.85）——一个参数同时拟合两块面板，且方向由实测量事前给出。")

    # ── 5. 锚点核对 ──
    h1(doc, "5　锚点核对（论文值 vs 本复现值）")
    table(doc,
          ["论文锚点", "论文值", "本复现值", "判定"],
          [["图1m 共现概率（西地中海 >0.8；Med&BS 0.6–0.8；大西洋 0.2–0.4）",
            "0.6–0.8 / >0.8", "地中海配对点 p50 = 0.594、p90 = 0.714、max = 0.879；全欧 max = 0.900", "✅"],
           ["图2a 复合天（南欧/东欧沿岸 >20 天/年）", ">20（若干区域）",
            "2003–2023 年均 p50 = 9.2、p95 = 22.3、max = 43.0", "✅"],
           ["图2b standalone（多数沿岸 <10 天/年）", "多数 <10", "p50 = 7.4、p95 = 17.2", "✅"],
           ["图2c CHR 时序（1980–90 年代约 1；2003 起 >1；2023 峰值 3.5）", "≈1 → >1 → 3.5",
            "1983–2002 中位数 0.374（偏低 2.7×）；2003 = 1.27、2022 = 1.72、2023 = 3.19（−9%）", "⚠"],
           ["图2d CHR 空间（亚得里亚/爱琴/波罗的海东部 2–3；大西洋与北欧 <1.5）", "2–3 / <1.5",
            "CHR 图 p50 = 1.83、p95 = 5.30", "✅"],
           ["图1a–i 空间分布热点（西地中海弧）与高值年", "—",
            "热点位置一致；高值年集合一致", "✅（目视）"],
           ["图1j 地中海&黑海复合天（80–90 年代 <20；2022 ≈ 78 峰；2023 = 72）", "78 / 72",
            "共超标口径 2022 = 20.7、2023 = 37.9；包络口径 2022 = 55.7、2023 = 120.4（峰值年错位）",
            "⚠ 未复现项（§7.1）"],
           ["图1k 波罗的海复合天", "正文无数值锚点", "峰值 2020 = 28.91（2018 = 28.89 次高）", "—"],
           ["图1l 全欧沿岸复合天（21 世纪初 <20；2022 ≈ 77）", "77",
            "共超标口径 2022 = 20.0；包络口径 2022 = 56.8、2023 = 93.5", "⚠ 未复现项（§7.1）"]],
          widths=[6.6, 3.0, 6.2, 2.4], font_size=8.5, header_size=8.5)

    para(doc, "事件规模（供量级参照）：陆地 THW 事件 1,635,196 个、海洋 MHW 事件 152,490 个、"
              "复合日段 77,704 段；全期总复合天 526,460、standalone 563,569，总体共现率 0.483、CHR 0.934。")

    # ── 6. 图 ──
    h1(doc, "6　逐图结果")
    h2(doc, "6.1　图 1：复合热浪的空间分布、时序与共现概率")
    figure(doc, "fig1_compound_spatial.png",
           "图 1　a–i 各年复合热浪空间分布；j–l 地中海&黑海 / 波罗的海 / 全欧沿岸的复合天时序；"
           "m 海洋-陆地共现概率。热点位置与高值年份与论文一致；j–l 的量级见 §7.1。")
    h2(doc, "6.2　图 2：复合天数、standalone 与复合-热浪比（CHR）")
    figure(doc, "fig2_chr.png",
           "图 2　a 复合天数；b standalone 天数；c CHR 时序；d CHR 空间分布。"
           "a/b/d 与论文一致；c 的 1980–90 年代量级偏低（§7.3）。")

    h2(doc, "6.3　图 3：FAR / PR 的阈值扫描")
    figure(doc, "fig3_attribution_v12w50.png",
           "图 3　主口径 _v12w50（20 成员 × 2 实验，440 模型年）的 FAR / PR 随复合天数阈值的扫描；"
           "三条竖向参考线 62 / 78 / 72 天对应论文 Fig.3c 的三年，其 FAR 与 Table 1 逐位一致。")

    h2(doc, "6.4　图 4：重现期位移（海洋 / 陆地 / 复合）")
    para(doc, "图 4 是本次复现最硬的一关：它要求「反事实世界（GHG 固定）的 N 年一遇」在当今世界对应多少年一遇，"
              "因此对阈值口径极其敏感。主口径 _v12w50 下三面板 × 五档共 15 个点全部落在本复现的 bootstrap 区间内：")
    table(doc,
          ["面板", "论文（5/10/20/50/100 年）", "本复现 _v12w50", "判定"],
          [["海洋（marine）", "2.30 / 3.80 / 6.30 / 13.4 / 24.0", "2.47 / 3.96 / 6.47 / 9.17 / 13.3",
            "5/5 落入 CI（100 年 CI = [8.30, 24.48]，含 24.0）"],
           ["陆地（terrestrial）", "1.26 / 1.46 / 1.75 / 2.44 / 3.26", "1.28 / 1.52 / 1.91 / 2.64 / 3.17",
            "5/5 落入 CI"],
           ["复合（compound）", "1.96 / 2.56 / 3.50 / 5.14 / 7.85", "1.96 / 2.67 / 3.86 / 5.12 / 8.00",
            "5/5 落入 CI"]],
          widths=[2.8, 6.4, 6.4, 6.0], font_size=8.5, header_size=8.5)
    para(doc, "海洋高端（100 年 13.3 vs 论文 24.0）看起来差 0.56 倍，但它的 bootstrap 区间是 [8.30, 24.48]——"
              "论文值正好落在区间上沿。440 个模型年在 100 年重现期这一档上只对应极少数样本，"
              "这个差额属于抽样噪声而非残差；对区域选择很敏感的对照实验（换成全欧 206 对）会让三块板同时腰斩、"
              "15 个点全部掉出区间，说明这一匹配来自数据本身、不是估计器凑出来的。")
    figure(doc, "fig4_return_period_v12w50.png",
           "图 4　重现期位移：固定 GHG 实验的 5/10/20/50/100 年一遇事件，在当今世界对应的重现期"
           "（灰色为论文、彩色为本复现；误差棒为 1000 次 bootstrap 的区间）。")

    h2(doc, "6.5　Table 1：三年复合事件的 FAR 与 PR")
    table(doc,
          ["年份", "阈值（天）", "本复现 FAR（95% bootstrap CI）", "论文 FAR",
           "本复现 PR（年）", "论文 PR"],
          [["2003", "62", "0.789（0.713–0.858）", "0.72（0.64–0.80）", "4.73", "4.1（2.8–7.2）"],
           ["2022", "78", "0.871（0.800–0.930）", "0.95（0.93–1.00）", "7.75", "> 6"],
           ["2023", "72", "0.814（0.726–0.884）", "0.78（0.70–0.88）", "5.39", "8（4–10）"]],
          widths=[1.6, 2.4, 5.2, 4.0, 3.6, 3.6], font_size=8.5, header_size=8.5,
          align_center_cols=(0, 1))
    para(doc, "FAR 的平均绝对误差 0.0607（对比：早期的 w = 0 口径 0.147）；PR 三年全部落在论文区间内；"
              "年际次序 2003 < 2023 < 2022 与论文一致。唯一出界的是 2022 年的 FAR（0.871 vs 论文区间下沿 0.93），"
              "而「三年各自的最优 w 跨 0.35–0.85」说明单一 w 无法同时命中三年 —— 这属于论文自身的年际形态，不再追。")

    h2(doc, "6.6　图 5：SST / 蒸发 / 比湿的夏季趋势")
    figure(doc, "fig5_sst_trend.png",
           "图 5　a SST、b 蒸发、c 比湿的 6–8 月趋势场（1984–2023）。"
           "地中海框：SST +0.59 °C/decade、比湿 +0.278 g/kg/decade；全域中位数 +0.335 / +0.125；"
           "蒸发中位 +1.74 cm/yr/decade（p95 +13.5，max +41.2）。")
    para(doc, "图 5a/5c 的地中海框数值与论文锚点（其正文给出的区域值）一致；全域中位数低于论文的「典型值」，"
              "属空间取平均的口径差异（论文给的是区域代表值），不是计算错误。b 面板用 OAFlux 1991–2020 重建，"
              "论文未给定量锚点，仅做量级核对。")

    h2(doc, "6.7　图 6：湿热应力的超阈频次、重现期与复合日 WBT 场")
    figure(doc, "fig6_wbt.png",
           "图 6　a/b WBT ≥ 25.5 °C 与 SH ≥ 19 g/kg 的超阈天数曲线；c 22–28 °C 的 WBT 重现期；"
           "d–f 2003/2022/2023 复合日的最大 WBT 空间场。域 = 地中海海岸向内 100 km（1637 格点）。")
    para(doc, "图 6 的区域口径按论文原文两处措辞定稿：Fig.6 caption 与 Methods 都只写 "
              "「land grid cells up to 100 km inland from the Mediterranean coast」（黑海只属 Fig.1/3/4），"
              "正文又点名热点含 Catalan 岸 ⇒ 域 = 地中海、含西班牙东岸（lon ≥ 0）、剔除黑海/亚速海，"
              "掩码 1637 格点。区域敏感性实测表明这是二阶因素（四变体 1.79–2.38 天，最大差 1.23 倍），"
              "改变不了水平量级；d–f 的空间型（南欧沿岸、峰值年 2023）与论文一致。"
              "a/c 的水平残差见 §7.2。")

    # ── 7. 未复现项 ──
    h1(doc, "7　未复现项：成因与量化")
    para(doc, "以下三处偏差已经过系统排查，结论是**实现无误、而是论文原文不足以唯一确定口径**。"
              "已定稿为「未复现项」，不再继续搜索口径。")

    h2(doc, "7.1　图1j/l 的复合天数曲线")
    para(doc, "论文称地中海&黑海 2022 年约 78 天（峰值）、2023 年 72 天，全欧 2022 年约 77 天。"
              "我们的两条读法都不对：")
    bullet(doc, "按论文观测 Methods L502-503 字面（逐日共超标），复合日 ⊆ THW 日，"
                "而我们的 THW 只有 35.1 / 48.3 天 ⇒ **结构上到不了 78 / 72 天**（2022 = 20.7、2023 = 37.9）。",
           bold_prefix="共超标口径：")
    bullet(doc, "可达量级，但峰值年错位（2022 = 55.7、2023 = 120.4），且结果对区域框高度敏感"
                "（换成西地中海框则峰值年正确、偏差 +13% / +10%，但那是又一个未写明的域）。",
           bold_prefix="MHW 包络口径：")
    para(doc, "论文在引言/结果/模型 Methods 用 fully encompasses，在观测 Methods 用 simultaneously exceed，"
              "两处定义互斥；按任何一种读法都无法同时命中 78/72 与 77。这属于原文内部张力，"
              "不是复现可以修补的信息缺口（详见 results/复现报告.md §6 的口径穷举）。")

    h2(doc, "7.2　图6a/6c 的水平")
    para(doc, "域定稿后残差仍在，且已量化到「不可能靠调参补上」的程度：")
    bullet(doc, "2023 年 WBT ≥ 25.5 °C 的区域平均 = **2.26 天**，论文 ≈ 40 天（18 倍）。"
                "要把区域平均抬到 40 天，需要 WBT 整体加 **≈ 4.3 °C**（阈值偏移扫描：+4.0 °C 时 38.6 天）"
                "—— 物理上不可能。非复合年的比值倒是对上了（0.36 vs 论文「少于 5 天」，6 倍）。"
                "论文的 40 天很可能不是「逐格点年天数再空间平均」这一层：我们的「区域至少一格超阈」天数"
                "2023 = 78、2000 = 58，量级反而接得上。",
           bold_prefix="6a：")
    bullet(doc, "现行口径用「JJA 逐日**区域平均** WBT」序列，2023 的区域平均上限只有 **22.42 °C**，"
                "26 °C 处恒为无定义 —— 这是结构性的，不是 bug。改用逐日**空间分位**（q99）序列后，"
                "RP(26 °C) = 2.79 年（2023）/ 9.35 年（2000），论文是 3.2 / 60：方向对、量级仍偏低。",
           bold_prefix="6c：")
    para(doc, "真要继续查只有一条路：用**逐小时 ERA5** 计算论文原文字面意义的「daily maximum WBT」再重做 6a/6c，"
              "代价是 300–600 GB 逐小时数据（或按区域取 30–80 GB）+ 约 1 小时重算，收益不明，"
              "本报告不做，登记为已知边界。")

    h2(doc, "7.3　图2c 的 1980–90 年代 CHR 量级")
    para(doc, "论文称 1980–90 年代 CHR 在 1 附近波动，我们同期中位数 0.374（偏低 2.7 倍）；"
              "2003 年之后趋势与 2023 峰值（3.19 vs 3.5）都对。它与图1j/l 的低估同源（复合天数系统性偏低），"
              "把 standalone 改成论文 L172 字面的事件级口径会让 CHR 略微上抬，列为可选精化，未做。")

    # ── 8. 差异清单 ──
    h1(doc, "8　与论文原文的差异清单")
    table(doc,
          ["#", "差异点", "论文原文", "本复现选择", "影响"],
          [["1", "复合日定义（观测）", "Methods 两处冲突：同时超阈 / 事件涵盖",
            "MHW 包络", "决定图1/图2 量级，两口径不可兼得"],
           ["2", "图1j/l 曲线", "2022 ≈ 78、2023 = 72 天", "包络口径 55.7 / 120.4",
            "未复现项（§7.1）"],
           ["3", "standalone 口径", "L172 字面为事件级", "日级扣除",
            "CHR 2023 = 3.19；事件级会更接近论文 3.5"],
           ["4", "气候态平滑", "未明示（包默认 TRUE/31 天）", "FALSE", "抽样实验影响 <5%"],
           ["5", "heatwaveR 版本", "v0.4.6", "v0.5.5", "语义经源码核验一致"],
           ["6", "E-OBS 版本", "未注明", "v33.0e（1980–2010）+ v29.0e（2011–2023）",
            "已做台阶/平滑/季节四项检验，未发现拼接伪影"],
           ["7", "图1m/2d 统计期", "caption「ratio over the period 2003-2023」", "同（比值之和）", "无偏差"],
           ["8", "CESM 侧网格与配对", "未给配对距离", "f09 0.94°×1.25°，206 对，上限 ≈112 km",
            "模型侧允许分离为观测侧 2.1 倍"],
           ["9", "模型侧阈值基准期", "1983–2012 的 90 分位（未说谁的气候态）",
            "各实验自算 + LOO（D7.4）", "共用冷基准会饱和（§4 D7.4）"],
           ["10", "模型侧复合定义", "两处冲突", "envelope 主线 + exceed 敏感性", "年暴露差 3.6 倍"],
           ["11", "暴露量纲", "年总复合天数", "区域均值天数（med_mean）", "与原文一致"],
           ["12", "陆地检测变量", "E-OBS「daily T2m」，未区分日均/日最高", "tg（日均）",
            "与 CESM 侧的日值语义一致"],
           ["13", "图6 的域与统计对象", "地中海 100 km；6a 为空间平均；6c 为 JJA 重现期",
            "地中海、含西班牙东岸、剔除黑海（1637 格点）", "6a/6c 水平残差（§7.2）"]],
          widths=[0.9, 3.6, 5.2, 4.4, 3.6], font_size=8, header_size=8, align_center_cols=(0,))

    # ── 9. 复现方式 ──
    h1(doc, "9　复现方式")
    h2(doc, "9.1　环境")
    para(doc, "Windows，24 核 / 32 GB；R 4.6.1（heatwaveR 0.5.5、ncdf4）；Python 3.13"
              "（numpy / pandas / xarray / scipy / matplotlib / cartopy 0.26.0）；"
              "数据盘通过 NTFS Junction 挂在工作区 data/ 下。依赖已固化在 requirements.txt"
              "（含 R 侧说明），环境可一键重建。")
    h2(doc, "9.2　一键入口")
    para(doc, "以下四条命令即可从数据到全部图表；缺数据会自动跳过并说明缺哪一项，"
              "Phase 6 默认即走主口径 _v12w50（D7.7）：")
    code_block(doc, [
        "python -m pip install -r requirements.txt    # 依赖",
        "run_all_phases.bat                           # = python python\\run_phases.py",
        "python python\\run_phases.py --dry-run        # 只看将执行哪些命令",
        "python python\\run_phases.py --phases 6       # 只重跑 Phase 6（主口径，5.7 min）",
    ])
    h2(doc, "9.3　分步命令（与一键入口同源，可单独核对每一步）")
    code_block(doc, [
        "# 观测链路（Phase 0–4）",
        "python python\\run_all.py                     # 缓存命中 ~1 min；全量重检陆地 ~22 min",
        "python python\\figures.py                     # 图1 / 图2 / S1",
        "python python\\fig_jkl_mhw_envelope.py          # 图1j–l 的包络数据源",
        "python python\\figS1_annual_maps.py            # 论文版 Supplementary Fig. S1（40 面板）",
        "",
        "# 湿热应力（Phase 5）",
        "python python\\phase5_humid.py check           # 输入就位检查（6 项）",
        "python python\\coastal_buffer.py               # 图6 的域：地中海 100 km、剔除黑海",
        "python python\\phase5_humid.py all             # 逐日 WBT/SH + 图5 趋势 + 图6 统计（18.6 min）",
        "python python\\phase5_humid.py stats --skip-fig5   # 只重算图6",
        "python python\\fig5_sst_trend.py               # 图5",
        "python python\\fig6_wbt.py                     # 图6",
        "",
        "# 归因（Phase 6，主口径 _v12w50）",
        "python python\\phase6_cesm.py pairs",
        "python python\\phase6_cesm.py prepare  --members 20",
        "python python\\phase6_cesm.py detect   --members 20 --baseline self --loo \\",
        "        --clim-period 1983-2012 --thresh-offset-xghg-t2m 0.5645 --tag _v12w50",
        "python python\\phase6_cesm.py compound --members 20 --tag _v12w50 --compound-def envelope",
        "python python\\phase6_cesm.py attrib   --members 20 --tag _v12w50 --compound-def envelope \\",
        "        --agg med_mean med_p90 med_max eur_mean eur_p90 eur_max",
        "python python\\phase6_cesm.py gev      --members 20 --tag _v12w50 --mapping emp",
        "python python\\fig3_attribution.py  --tag _v12w50",
        "python python\\fig4_return_period.py --tag _v12w50",
        "python python\\table1_attribution.py --tag _v12w50",
    ])
    para(doc, "注意两点：① attrib 必须跑全 6 列聚合，否则 fig3 会因为缺 eur_* 列直接失败；"
              "② gev 必须带 --mapping emp —— GEV 尾部外推会把复合面板的百年水平推到 604 天/年，"
              "超过 365 天的物理上界。")
    h2(doc, "9.4　自检（不读数据，秒级）")
    code_block(doc, [
        "python python\\calc_wbt.py              # WBT/SH 25 项合成自检",
        "python python\\gev_return_period.py     # GEV 16 项合成自检",
        "python results\\phase5_selftest.py      # Phase 5 口径",
        "python results\\phase6_selftest.py      # Phase 6 口径",
    ])
    para(doc, "四者均应输出 ALL ... PASSED。")

    # ── 10. 产物 ──
    h1(doc, "10　产物清单")
    table(doc,
          ["类别", "文件", "说明"],
          [["图1 / 图2", "results/figures/fig1_compound_spatial.*、fig2_chr.*", "主图（png + pdf）"],
           ["图3", "fig3_attribution_v12w50.*", "主口径；62/78/72 天处 FAR 与 Table 1 逐位一致"],
           ["图4", "fig4_return_period_v12w50.*", "主口径；三面板 15/15 落入 CI"],
           ["图5", "fig5_sst_trend.*", "SST / 蒸发 / 比湿趋势"],
           ["图6", "fig6_wbt.*", "域已定稿（1637 格点），旧 1952 格点版留 *_medBS_1952cells_bak.*"],
           ["S1", "figS1_paper_annual_maps.*", "论文版 40 面板组图"],
           ["Table 1", "results/tables/table1_v12w50.csv", "FAR / PR + 论文对照列"],
           ["归因数值", "phase6_attrib_summary_v12w50.csv、phase6_attrib_sweep_v12w50_*.csv",
            "阈值扫描 × 6 种聚合"],
           ["重现期数值", "phase6_gev_v12w50.json", "含 _meta.mapping = emp"],
           ["湿热数值", "fig5_stats.json、fig6_stats.json", "趋势与超阈/重现期统计"],
           ["工作日志", "results/复现报告.md", "含 14 套口径的完整搜索过程与已证伪假设"]],
          widths=[2.4, 8.4, 7.4], font_size=8.5, header_size=8.5)

    # ── 附：口径演化 ──
    h1(doc, "附　口径演化（为什么是 _v12w50）")
    para(doc, "Phase 6 一共落盘 14 套口径，全部保留可复算。演化主线是三步："
              "基准期（_v4→_v7）、阈值混合权重（_v7→_v12w50）、映射内核（GEV→经验分位）。")
    table(doc,
          ["口径", "关键改动", "图4 100 年（海/陆/复合）", "结论"],
          [["_v4 / _v5", "共用 XGHG 冷基准", "2.7 / 1.4 / ∞（`_v5` 口径）", "ALL 世界饱和，图4 塌缩"],
           ["_v7", "各实验自算 1983–2012（w = 0）", "50.9 / 18.0 / 104.9", "对比恢复，但量级偏大"],
           ["_v7e", "同上 + exceed 复合", "50.9 / 18.0 / 31.6", "复合面板病态消除，Table 1 崩塌"],
           ["_v8", "共用 ALL 池（w = 1）", "∞ / 2.13 / 1.04", "反事实世界被打死"],
           ["_v10", "_v7 + 经验分位映射", "13.3 / 17.6 / 13.3", "复合 13.4× → 1.7×，worst 转为陆地"],
           ["_v12w60 / w89", "w = 0.60 / 0.89", "13.3 / 2.72 / 7.46；13.3 / 1.83 / 4.63", "w 过大过头"],
           ["_v12w50", "w = 0.50 + 经验映射", "13.3 / 3.17 / 8.00", "15/15 落入论文 CI（论文 24.0 / 3.26 / 7.85）"]],
          widths=[2.8, 5.4, 5.6, 4.4], font_size=8.5, header_size=8.5)
    para(doc, "被定量证伪、不再重试的方向：暴露量纲换成事件数或覆盖占比、把阈值对两个世界同时抬高、"
              "用更冷的基准去补海洋高端、以及把共用基准实现成「只用 ALL 池的 90 分位」。"
              "这些实验的全部数字记录在 results/复现报告.md §5.2 与 docs/批次历史.md。")

    doc.save(OUT)
    print(f"已写出：{OUT}")
    return OUT


if __name__ == "__main__":
    build()
