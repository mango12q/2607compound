"""s1_extract.py — 从补充材料 PDF 抽取 Supplementary Fig. S1 原图"""
import os
import pymupdf  # noqa: F401  (新 API)

PDF = r"docs\附件材料-compound coastal marine-terrestrial heatwaves associated with humid-heat stress in europe(1).pdf"
OUT_DIR = r"results\s1"

os.makedirs(OUT_DIR, exist_ok=True)

doc = pymupdf.open(PDF)
print("pages:", doc.page_count)
for pno in range(doc.page_count):
    page = doc[pno]
    for img in page.get_images(full=True):
        xref = img[0]
        base = doc.extract_image(xref)
        print(f"page {pno+1}: xref={xref} ext={base['ext']} "
              f"{base['width']}x{base['height']} colorspace={base['colorspace']} "
              f"bytes={len(base['image'])}")
        out = os.path.join(OUT_DIR, f"s1_page{pno+1}_xref{xref}.{base['ext']}")
        with open(out, "wb") as f:
            f.write(base["image"])
        print("  ->", out)

        # 同时渲染该页为高 dpi PNG（用于对照版式）
        pix = page.get_pixmap(dpi=400)
        out2 = os.path.join(OUT_DIR, f"page{pno+1}_render400dpi.png")
        pix.save(out2)
        print(f"  -> {out2}  ({pix.width}x{pix.height})")
doc.close()
