"""极简 DAP2 客户端（只用 requests 直连 `.dds` / `.das` / `.dods`）。

为什么不用 pydap / netCDF4：
  · netCDF-C 4.9.3 在本机走 schannel，证书吊销检查失败 ⇒ 所有 OPeNDAP 都 `OSError: [Errno -68]`。
  · pydap 3.5.11 能连，但实测**每个文件 open 86–123 s**，且并发时频繁 `ChunkedEncodingError:
    Response ended prematurely`，退避后 6 个进程聚合只有 ~33 kB/s。
  · 直接 `curl`/`requests` 拉 `.dods` 约束：单流 57 kB/s，**6 路并发聚合 481 kB/s**（2026-10-27 实测）。

协议要点（DAP2/DODS）：
  · `GET <url>.dds`  → 文本 DDS，含每个变量的类型与维度长度；
  · `GET <url>.dods?VAR[i0:1:i1][j0:1:j1]…` → 文本 DDS（约束后的形状）+ `\\nData:\\n` + XDR 大端二进制；
  · 二进制按 DDS 中数组出现顺序排列：先被测变量，再其 MAPS（坐标），然后是其它变量。
    **方括号必须百分号编码**（%5B…%5D），否则 Tomcat 直接 400。
"""
from __future__ import annotations

import re

import numpy as np
import requests

_DTYPE = {
    "Byte": ">u1", "UInt16": ">u2", "Int16": ">i2", "UInt32": ">u4", "Int32": ">i4",
    "Float32": ">f4", "Float64": ">f8", "Float": ">f4",
}

_ARRAY_RE = re.compile(r"(?P<type>Byte|UInt16|Int16|UInt32|Int32|Float32|Float64|Float)\s+"
                       r"(?P<name>[A-Za-z0-9_\-\.]+)\s*((\[[^\]]*\])+)\s*;")
_DIM_RE = re.compile(r"\[\s*([A-Za-z0-9_\-\.]+)\s*=\s*(\d+)\s*\]")
_ATTR_RE = re.compile(r"(?P<name>[A-Za-z0-9_\-\.]+)\s*\{(?P<body>[^}]*)\}")


class DAP2File:
    """一个远程 netCDF 文件的 DAP2 视图：解析 DDS/DAS，按约束取数。"""

    def __init__(self, url, session=None, timeout=(30, 900)):
        self.url = url.rstrip("/")
        self.s = session or requests.Session()
        self.timeout = timeout
        self.dds = self._text(".dds")
        self.das = self._text(".das")
        self.arrays = {}   # name -> (dtype, (dims...), (lens...))
        for m in _ARRAY_RE.finditer(self.dds):
            dims, lens = [], []
            for d in _DIM_RE.finditer(m.group(3)):
                dims.append(d.group(1))
                lens.append(int(d.group(2)))
            self.arrays[m.group("name")] = (_DTYPE[m.group("type")], tuple(dims), tuple(lens))

    # ── 元数据 ─────────────────────────────────────────
    def _text(self, suffix):
        r = self.s.get(self.url + suffix, timeout=self.timeout)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text

    def shape(self, var):
        return self.arrays[var][2]

    def dims(self, var):
        return self.arrays[var][1]

    def attr(self, var, attr):
        """从 DAS 里取变量/全局属性字符串（去引号）。"""
        m = _ATTR_RE.search(self.das, 0)
        for blk in _ATTR_RE.finditer(self.das):
            if blk.group("name") != var:
                continue
            a = re.search(rf"\b{attr}\s+\"([^\"]*)\"", blk.group("body"))
            if a:
                return a.group(1)
        # 退化：全文搜第一处 `attr "…"`
        a = re.search(rf"\b{attr}\s+\"([^\"]*)\"", self.das if m is None else self.das)
        return a.group(1) if a else None

    # ── 取数 ───────────────────────────────────────────
    def get(self, var, slices):
        """slices = [(start, stop), ...]（左闭右开，对应 DAP2 的 [start:1:stop-1]）。"""
        shp = self.shape(var)
        if len(slices) != len(shp):
            raise ValueError(f"{var} 需要 {len(shp)} 维约束, 收到 {len(slices)}")
        expr = var + "".join(f"[{a}:1:{b-1}]" for a, b in slices)
        url = self.url + ".dods?" + expr.replace("[", "%5B").replace("]", "%5D")
        r = self.s.get(url, timeout=self.timeout)
        r.raise_for_status()
        raw = r.content
        # 头 = 约束后的 DDS + "\nData:\n"
        k = raw.find(b"Data:\n")
        if k < 0:
            k = raw.find(b"Data:")
            if k < 0:
                raise RuntimeError(f"响应里没有 Data: 段 (前 200 字节: {raw[:200]!r})")
            body = k + 5
        else:
            body = k + 6
        if raw[body:body + 1] == b"\n":
            body += 1
        dds = raw[:k].decode("utf-8", "replace")
        specs = []
        for m in _ARRAY_RE.finditer(dds):
            dims, lens = [], []
            for d in _DIM_RE.finditer(m.group(3)):
                dims.append(d.group(1))
                lens.append(int(d.group(2)))
            specs.append((m.group("name"), _DTYPE[m.group("type")], tuple(lens)))
        out, off = {}, body
        for name, dt, lens in specs:
            # ★ 2026-10-27 实测：TDS 的 DAP2 响应里**每个数组/坐标前各有 8 字节头**
            #   （整段 Grid = 数组 + 3 个 MAPS ⇒ 多出 32 字节）。不跳过就会整体错位。
            off += 8
            n = int(np.prod(lens)) if lens else 1
            nbytes = n * np.dtype(dt).itemsize
            out[name] = np.frombuffer(raw, dtype=dt, count=n, offset=off).reshape(lens or ())
            off += nbytes
        if var not in out:
            raise RuntimeError(f"约束响应里没有 {var}: {list(out)}")
        return out


def decode_time(values, units, calendar="standard"):
    """把 `days since …` 数值转成 numpy datetime64[ns]（借 xarray 的 CF 解码器）。"""
    import xarray as xr
    from xarray.coding.times import decode_cf_datetime
    return decode_cf_datetime(np.asarray(values, dtype="float64"), units, calendar)
