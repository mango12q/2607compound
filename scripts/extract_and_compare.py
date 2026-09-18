import fitz, os, glob

# Paths
paper_path = r"E:\2607compound\compound coastal marine-terrestrial heatwaves associated with humid-heat stress in europe(1).pdf"
gen_fig1 = r"E:\2607compound\results\figures\fig1_compound_spatial.pdf"
gen_fig2 = r"E:\2607compound\results\figures\fig2_chr.pdf"
out_dir = r"E:\2607compound\pdf_extract"
os.makedirs(out_dir, exist_ok=True)

# Convert generated PDFs to PNG
for pdf_path, name in [(gen_fig1, "fig1_gen"), (gen_fig2, "fig2_gen")]:
    doc = fitz.open(pdf_path)
    print(f"{name}: {doc.page_count} page(s), metadata: {doc.metadata}")
    for i in range(doc.page_count):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=200)
        out_path = os.path.join(out_dir, f"{name}.png")
        pix.save(out_path)
        print(f"  Saved {out_path} ({os.path.getsize(out_path)} bytes)")
    doc.close()

# Extract embedded images from the paper PDF near fig1/fig2
doc = fitz.open(paper_path)
print(f"\nPaper pages: {doc.page_count}")

# Find pages with figure captions
fig_pages = []
for i in range(doc.page_count):
    text = doc.load_page(i).get_text()
    if "Figure 1" in text or "Fig. 1" in text:
        fig_pages.append(("fig1", i))
    if "Figure 2" in text or "Fig. 2" in text:
        fig_pages.append(("fig2", i))

print("Figure caption pages:", fig_pages)

# Extract images from those pages and a few neighbors
for label, page_idx in fig_pages:
    for neighbor in range(max(0, page_idx-1), min(doc.page_count, page_idx+2)):
        page = doc.load_page(neighbor)
        img_list = page.get_images(full=True)
        print(f"Page {neighbor+1} ({label}) has {len(img_list)} images")
        for img_index, img in enumerate(img_list, start=1):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n > 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            img_path = os.path.join(out_dir, f"paper_{label}_p{neighbor+1:03d}_img{img_index}.png")
            pix.save(img_path)
            print(f"  Saved {img_path} ({os.path.getsize(img_path)} bytes)")

doc.close()
print("\nDone")
