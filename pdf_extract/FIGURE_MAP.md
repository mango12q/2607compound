# pdf_extract 论文插图映射

> 由 `scripts/extract_paper_figs.py` 生成（2026-09-23）。

| 文件 | 论文图号 | 源页 | 尺寸 |
|---|---|---|---|
| `fig1_p03.png` | **Fig. 1** | p3 | 1501×2040 |
| `fig2_p04.png` | **Fig. 2** | p4 | 1514×894 |
| `fig3_p05.png` | **Fig. 3** | p5 | 1501×878 |
| `fig4_p06.png` | **Fig. 4** | p6 | 1454×430 |
| `fig5_p07.jpeg` | **Fig. 5** | p7 | 1501×1049 |
| `fig6_p08.png` | **Fig. 6** | p8 | 1501×1493 |
| `—` | （第 12 页非图区，未导出） | p12 | 1100×90 |
| `supp_figS1_p2.png` | Supplementary Fig. S1 | p2 | 6015×8024 |

## 旧文件命名更正（重要）

| 旧文件名 | 实际内容 | 新文件名 |
|---|---|---|
| `paper_fig1_p003_img1.png` | 论文 Fig. 1 | `fig1_p03.png` |
| `paper_fig1_p004_img1.png` | 论文 **Fig. 2**（旧名错标 fig1） | `fig2_p04.png` |
| `paper_fig2_p005_img1.png` | 论文 **Fig. 3**（旧名错标 fig2） | `fig3_p05.png` |
| （无） | 论文 Fig. 4 / 5 / 6 | 本次首次提取 |

## 待修

- `scripts/translate_to_word.py` 引用的 `..._p3_img1.png` … `_p8_img1.png` **全部不存在**，应改为引用本表的新文件名（第 181/213/260/316/399/438/778 行）。
