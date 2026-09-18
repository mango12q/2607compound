import fitz, os

paper_path = r"E:\2607compound\compound coastal marine-terrestrial heatwaves associated with humid-heat stress in europe(1).pdf"
out_dir = r"E:\2607compound\pdf_extract"
os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(paper_path)
print(f"Total pages: {doc.page_count}")

for i in range(doc.page_count):
    text = doc.load_page(i).get_text()
    if any(k in text for k in ["Figure 1", "Fig. 1", "Figure 2", "Fig. 2"]):
        print(f"Page {i+1} contains figure caption")
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=200)
        img_path = os.path.join(out_dir, f"page_{i+1:03d}.png")
        pix.save(img_path)
        print(f"  Saved {img_path}")

for i in range(min(12, doc.page_count)):
    page = doc.load_page(i)
    pix = page.get_pixmap(dpi=150)
    img_path = os.path.join(out_dir, f"page_{i+1:03d}_full.png")
    pix.save(img_path)

doc.close()
print("Done")
