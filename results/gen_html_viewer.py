import xarray as xr
import numpy as np
import json
import base64
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

path = r'C:\Users\Administrator\.dsh\attachments\v1\files\41\419f1b652a4158fbaa1fbf3ee57538edadc4dff7785d1caf301d2a925fbf103a\d2m_global_1979_01.nc'

print("正在加载数据...")
ds = xr.open_dataset(path, chunks={'valid_time': 1})
d2m = ds['d2m'].values
lat = ds.latitude.values
lon = ds.longitude.values
times = ds.valid_time.values

d2m_c = d2m - 273.15

lat_europe_mask = (lat >= 35) & (lat <= 70)
lon_europe_mask = (lon >= -10) & (lon <= 40)
lat_europe = lat[lat_europe_mask]
lon_europe = lon[lon_europe_mask]
d2m_europe = d2m_c[:, lat_europe_mask][:, :, lon_europe_mask]

print(f"数据加载完成: {d2m_europe.shape}")

print("正在生成图片...")
images_base64 = []
for i in range(len(times)):
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.pcolormesh(lon_europe, lat_europe, d2m_europe[i], 
                       cmap='RdYlBu_r', shading='auto', vmin=-20, vmax=25)
    ax.set_title(f'ERA5 d2m (2m dewpoint temperature) - {times[i]}', fontsize=11)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    plt.colorbar(im, ax=ax, label='d2m (°C)')
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    images_base64.append(img_base64)
    plt.close()
    print(f"  已生成 {i+1}/{len(times)} 天")

dates = [str(t)[:10] for t in times]

html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ERA5 d2m 交互式查看器</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; text-align: center; }}
        .image-container {{ text-align: center; margin: 20px 0; }}
        #image {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
        .controls {{ display: flex; align-items: center; justify-content: center; gap: 10px; margin: 20px 0; }}
        button {{ padding: 10px 20px; font-size: 16px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }}
        button:hover {{ background: #0056b3; }}
        button:disabled {{ background: #ccc; cursor: not-allowed; }}
        .slider-container {{ margin: 20px 0; text-align: center; }}
        #slider {{ width: 80%; max-width: 600px; height: 8px; }}
        .date-display {{ text-align: center; font-size: 24px; font-weight: bold; color: #333; margin: 10px 0; }}
        .info {{ background: #e7f3ff; padding: 10px; border-radius: 4px; margin-top: 20px; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ERA5 d2m (2m 露点温度) - 欧洲区域 1979年1月</h1>
        <div class="date-display" id="dateDisplay">{dates[0]}</div>
        <div class="image-container">
            <img id="image" src="data:image/png;base64,{images_base64[0]}" alt="d2m map">
        </div>
        <div class="controls">
            <button id="prevBtn" onclick="changeImage(-1)">◀ 前一天</button>
            <button id="nextBtn" onclick="changeImage(1)">后一天 ▶</button>
        </div>
        <div class="slider-container">
            <input type="range" id="slider" min="0" max="{len(times)-1}" value="0" onchange="updateImage(this.value)">
        </div>
        <div class="info">
            <strong>数据信息：</strong><br>
            变量：d2m (2 metre dewpoint temperature)<br>
            时间范围：{dates[0]} 到 {dates[-1]}（共 {len(times)} 天）<br>
            区域：欧洲 (35°N-70°N, 10°W-40°E)<br>
            单位：°C（已从 K 转换）<br>
            操作：使用滑块、按钮或键盘 ← → 方向键翻页
        </div>
    </div>
    <script>
        const images = {json.dumps(images_base64)};
        const dates = {json.dumps(dates)};
        let currentIndex = 0;
        function updateImage(index) {{
            currentIndex = parseInt(index);
            document.getElementById('image').src = 'data:image/png;base64,' + images[currentIndex];
            document.getElementById('dateDisplay').textContent = dates[currentIndex];
            document.getElementById('slider').value = currentIndex;
            updateButtons();
        }}
        function changeImage(delta) {{
            const newIndex = currentIndex + delta;
            if (newIndex >= 0 && newIndex < images.length) {{
                updateImage(newIndex);
            }}
        }}
        function updateButtons() {{
            document.getElementById('prevBtn').disabled = currentIndex === 0;
            document.getElementById('nextBtn').disabled = currentIndex === images.length - 1;
        }}
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'ArrowLeft') changeImage(-1);
            else if (e.key === 'ArrowRight') changeImage(1);
        }});
        updateButtons();
    </script>
</body>
</html>
'''

out = r'E:\2607compound\results\d2m_europe_1979_01_interactive.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n交互式查看器已生成！")
print(f"文件位置: {out}")
print(f"文件大小: {len(html) / (1024*1024):.1f} MB")
