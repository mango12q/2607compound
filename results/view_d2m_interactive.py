import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button

# 文件路径
path = r'C:\Users\Administrator\.dsh\attachments\v1\files\41\419f1b652a4158fbaa1fbf3ee57538edadc4dff7785d1caf301d2a925fbf103a\d2m_global_1979_01.nc'

print("正在加载数据...")
ds = xr.open_dataset(path, chunks={'valid_time': 1})
d2m = ds['d2m'].values  # (31, 721, 1440)
lat = ds.latitude.values
lon = ds.longitude.values
times = ds.valid_time.values

# 转摄氏度
d2m_c = d2m - 273.15

# 欧洲区域索引
lat_europe_mask = (lat >= 35) & (lat <= 70)
lon_europe_mask = (lon >= -10) & (lon <= 40)
lat_europe = lat[lat_europe_mask]
lon_europe = lon[lon_europe_mask]
d2m_europe = d2m_c[:, np.ix_(lat_europe_mask, lon_europe_mask)][:, :, :]

print(f"数据加载完成: {d2m.shape}")
print(f"时间范围: {times[0]} 到 {times[-1]}")
print(f"全球范围: lat {lat.min():.1f}~{lat.max():.1f}, lon {lon.min():.1f}~{lon.max():.1f}")
print(f"欧洲范围: lat {lat_europe.min():.1f}~{lat_europe.max():.1f}, lon {lon_europe.min():.1f}~{lon_europe.max():.1f}")

# 创建图形
fig = plt.figure(figsize=(18, 10))
fig.canvas.manager.set_window_title('ERA5 d2m 交互式查看器')

# 左图：全球
ax_global = plt.axes([0.08, 0.35, 0.38, 0.55])
im_global = ax_global.pcolormesh(lon, lat, d2m_c[0], cmap='RdYlBu_r', 
                                  shading='auto', vmin=-70, vmax=35)
ax_global.set_title(f'全球 d2m - {times[0]}', fontsize=12)
ax_global.set_xlabel('Longitude')
ax_global.set_ylabel('Latitude')
ax_global.set_xlim(-180, 180)
ax_global.set_ylim(-90, 90)
plt.colorbar(im_global, ax=ax_global, label='d2m (°C)', fraction=0.046)

# 右图：欧洲
ax_europe = plt.axes([0.52, 0.35, 0.38, 0.55])
im_europe = ax_europe.pcolormesh(lon_europe, lat_europe, d2m_europe[0], 
                                  cmap='RdYlBu_r', shading='auto', vmin=-20, vmax=25)
ax_europe.set_title(f'欧洲区域 d2m - {times[0]}', fontsize=12)
ax_europe.set_xlabel('Longitude')
ax_europe.set_ylabel('Latitude')
plt.colorbar(im_europe, ax=ax_europe, label='d2m (°C)', fraction=0.046)

# 底部时间信息
ax_text = plt.axes([0.3, 0.12, 0.4, 0.05])
ax_text.axis('off')
time_text = ax_text.text(0.5, 0.5, str(times[0]), ha='center', va='center', 
                         fontsize=14, transform=ax_text.transAxes)

# 添加滑块
ax_slider = plt.axes([0.25, 0.08, 0.5, 0.03])
slider = Slider(ax_slider, '日期', 0, len(times)-1, valinit=0, valstep=1)

# 更新函数
def update(val):
    idx = int(val)
    t = times[idx]
    
    # 更新全球图
    im_global.set_array(d2m_c[idx].ravel())
    ax_global.set_title(f'全球 d2m - {t}', fontsize=12)
    
    # 更新欧洲图
    im_europe.set_array(d2m_europe[idx].ravel())
    ax_europe.set_title(f'欧洲区域 d2m - {t}', fontsize=12)
    
    # 更新时间文本
    time_text.set_text(str(t))
    
    fig.canvas.draw_idle()

slider.on_changed(update)

# 添加前后按钮
ax_prev = plt.axes([0.15, 0.08, 0.08, 0.03])
ax_next = plt.axes([0.77, 0.08, 0.08, 0.03])
btn_prev = Button(ax_prev, '前一天')
btn_next = Button(ax_next, '后一天')

def prev_day(event):
    idx = max(0, int(slider.val) - 1)
    slider.set_val(idx)

def next_day(event):
    idx = min(len(times)-1, int(slider.val) + 1)
    slider.set_val(idx)

btn_prev.on_clicked(prev_day)
btn_next.on_clicked(next_day)

# 添加键盘控制
def on_key(event):
    if event.key == 'left':
        prev_day(None)
    elif event.key == 'right':
        next_day(None)
    elif event.key == 'home':
        slider.set_val(0)
    elif event.key == 'end':
        slider.set_val(len(times)-1)

fig.canvas.mpl_connect('key_press_event', on_key)

print("\n" + "=" * 60)
print("交互式查看器已启动！")
print("=" * 60)
print("操作说明：")
print("  1. 拖动底部滑块切换日期")
print("  2. 点击 ◀ 前一天 / 后一天 ▶ 按钮")
print("  3. 使用键盘 ← → 方向键翻页")
print("  4. Home 键跳到第一天，End 键跳到最后一天")
print("  5. 鼠标悬停可查看大致数值（颜色条对照）")
print("  6. 关闭窗口退出程序")
print("=" * 60)

plt.show()
