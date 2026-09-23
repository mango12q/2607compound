"""extract_paper_figs.py — 从论文/补充材料 PDF 正确提取全部插图

背景（2026-09-23 发现）：
    `pdf_extract/` 里此前的论文插图提取**命名混乱且不完整**：
      - `paper_fig1_p003_img1.png`  = 论文 Fig.1   ✓
      - `paper_fig1_p004_img1.png`  = 论文 **Fig.2**（旧名错标为 fig1）
      - `paper_fig2_p005_img1.png`  = 论文 **Fig.3**（旧名错标为 fig2）
      - 论文 Fig.4 / Fig.5 / Fig.6 **从未提取**
    而 `scripts/translate_to_word.py` 引用的是另一套**完全不存在的**文件名
    （`..._p3_img1.png` … `_p8_img1.png`），因此该脚本取图必然失败。

本脚本按"页 → 图"重新提取，输出规范化命名：
    pdf_extract/figN_pPP[_imgM].<ext>      N = 论文图号, PP = 页码
    pdf_extract/supp_figS1_p2[_imgM].<ext>
并写出 pdf_extract/FIGURE_MAP.md 记录映射与旧名更正。

用法:
    python scripts/extract_paper_figs.py --list     # 只列出，不落盘
    python scripts/extract_paper_figs.py            # 提取
"""
import argparse
import os
import sys

import pymupdf

BASE = r"D:\2607compound"
MAIN_PDF = os.path.join(BASE, "docs", "主论文.pdf")
SUPP_PDF = os.path.join(
    BASE, "docs",
    "附件材料-compound coastal marine-terrestrial heatwaves associated with "
    "humid-heat stress in europe(1).pdf",
)
OUT_DIR = os.path.join(BASE, "pdf_extract")

# 论文图 → 所在页（1-based）。与正文 "Fig. N" 的排版页核对得到。
MAIN_FIG_PAGES = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8}


def probe(path, label):
    doc = pymupdf.open(path)
    print(f"\n=== {label}  ({doc.page_count} pages) ===")
    found = []
    for i in range(doc.page_count):
        for k, x in enumerate(doc[i].get_images(full=True), 1):
            b = doc.extract_image(x[0])
            rec = dict(page=i + 1, idx=k, xref=x[0], w=b["width"], h=b["height"],
                       ext=b["ext"], nbytes=len(b["image"]))
            found.append(rec)
            print(f"  p{i+1} img{k}  xref={x[0]}  {b['width']}x{b['height']}  "
                  f"{b['ext']}  {len(b['image']) / 1e6:.2f} MB")
    doc.close()
    return found


def extract(path, found, name_fn, out_dir):
    doc = pymupdf.open(path)
    written = []
    for rec in found:
        name = name_fn(rec)
        if name is None:
            continue
        b = doc.extract_image(rec["xref"])
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(b["image"])
        written.append(name)
    doc.close()
    return written


def main():
    ap = argparse.ArgumentParser(description="提取论文/补充材料 PDF 的全部插图")
    ap.add_argument("--list", action="store_true", help="只列出，不写盘")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    main_found = probe(MAIN_PDF, "主论文")
    supp_found = probe(SUPP_PDF, "补充材料")

    page2fig = {p: n for n, p in MAIN_FIG_PAGES.items()}

    def main_name(rec):
        n = page2fig.get(rec["page"])
        if n is None:
            return None
        suffix = f"_img{rec['idx']}" if rec["idx"] > 1 else ""
        return f"fig{n}_p{rec['page']:02d}{suffix}.{rec['ext']}"

    def supp_name(rec):
        suffix = f"_img{rec['idx']}" if rec["idx"] > 1 else ""
        return f"supp_figS1_p{rec['page']}{suffix}.{rec['ext']}"

    if args.list:
        print("\n[--list] 未落盘。将导出：")
        for rec in main_found:
            fn = main_name(rec)
            if fn:
                print("   ", fn)
        for rec in supp_found:
            print("   ", supp_name(rec))
        return 0

    w1 = extract(MAIN_PDF, main_found, main_name, OUT_DIR)
    w2 = extract(SUPP_PDF, supp_found, supp_name, OUT_DIR)

    print("\n=== 已写出 ===")
    for n in w1 + w2:
        print("  ", n)

    mp = os.path.join(OUT_DIR, "FIGURE_MAP.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write("# pdf_extract 论文插图映射\n\n")
        f.write("> 由 `scripts/extract_paper_figs.py` 生成（2026-09-23）。\n\n")
        f.write("| 文件 | 论文图号 | 源页 | 尺寸 |\n|---|---|---|---|\n")
        for rec in main_found:
            n = page2fig.get(rec["page"])
            fn = main_name(rec)
            label = f"**Fig. {n}**" if n else f"（第 {rec['page']} 页非图区，未导出）"
            f.write(f"| `{fn or '—'}` | {label} | p{rec['page']} | "
                    f"{rec['w']}×{rec['h']} |\n")
        for rec in supp_found:
            f.write(f"| `{supp_name(rec)}` | Supplementary Fig. S1 | "
                    f"p{rec['page']} | {rec['w']}×{rec['h']} |\n")

        f.write("\n## 旧文件命名更正（重要）\n\n")
        f.write("| 旧文件名 | 实际内容 | 新文件名 |\n|---|---|---|\n")
        f.write("| `paper_fig1_p003_img1.png` | 论文 Fig. 1 | `fig1_p03.png` |\n")
        f.write("| `paper_fig1_p004_img1.png` | 论文 **Fig. 2**（旧名错标 fig1） | `fig2_p04.png` |\n")
        f.write("| `paper_fig2_p005_img1.png` | 论文 **Fig. 3**（旧名错标 fig2） | `fig3_p05.png` |\n")
        f.write("| （无） | 论文 Fig. 4 / 5 / 6 | 本次首次提取 |\n")

        f.write("\n## 待修\n\n")
        f.write("- `scripts/translate_to_word.py` 引用的 "
                "`..._p3_img1.png` … `_p8_img1.png` **全部不存在**，"
                "应改为引用本表的新文件名（第 181/213/260/316/399/438/778 行）。\n")
    print("\n映射 ->", mp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
