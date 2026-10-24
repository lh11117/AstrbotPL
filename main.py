import os

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import re
import json
from collections import defaultdict
from jinja2 import Template
from html2image import Html2Image
import tempfile
from PIL import Image

def crop_top_until_blank_band(img_path, out_path, bg=(0xf5, 0xf6, 0xf8), band=1000):
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    px = img.load()

    # 记录连续满足“整行都是背景色”的行数
    run = 0
    stop_y = None

    for y in range(h):
        row_is_bg = True
        for x in range(w):
            if px[x, y] != bg:
                row_is_bg = False
                break

        if row_is_bg:
            run += 1
            if run >= band:
                # 连续 band 行都是背景色，裁剪位置取这 band 行的起点
                stop_y = y - band + 1
                break
        else:
            run = 0

    if stop_y is None:
        # 没找到满足条件的连续 band 行，不裁剪（或按需处理）
        # print("未找到连续 %d 行背景色，未裁剪。" % band)
        return

    # 只保留顶部：从 0 到 stop_y（不含 stop_y）
    cropped = img.crop((0, 0, w, stop_y))
    cropped.save(out_path)
    # print("裁剪完成：原高 %d，裁剪后高 %d，保存到 %s" % (h, stop_y, out_path))

def search(keyword):
    # ---------- 1. 读取数据并匹配 ----------
    with open("./result.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    result = defaultdict(lambda: defaultdict(list))
    for city, lines in data.items():
        for line_name, line_info in lines.items():
            stations = line_info.get("stations", [])
            matched = [s for s in stations if keyword in s]
            if matched:
                result[city][line_name] = {
                    "stations": matched,
                    "color": line_info.get("color", "888888"),
                }

    # 转成普通 dict 便于模板渲染
    result = {city: dict(lines) for city, lines in result.items()}

    # ---------- 2. Jinja2 模板 ----------
    html_template = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
    <meta charset="UTF-8">
    <style>
    body {
        font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
        background: #f5f6f8;
        margin: 0;
        padding: 24px;
        color: #222;
    }
    h1 {
        font-size: 22px;
        margin: 0 0 18px;
        color: #1a1a1a;
    }
    .keyword { color: #d0021b; }
    .city {
        background: #fff;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .city-name {
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 12px;
        border-left: 4px solid #d0021b;
        padding-left: 10px;
    }
    .line {
        display: flex;
        align-items: flex-start;
        margin: 8px 0;
    }
    .line-name {
        flex: 0 0 160px;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 4px;
        color: #fff;
        font-size: 13px;
        text-align: center;
    }
    .stations {
        flex: 1;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding-left: 12px;
    }
    .station {
        background: #eef1f5;
        border-radius: 14px;
        padding: 3px 12px;
        font-size: 13px;
    }
    .empty {
        color: #888;
        font-size: 16px;
    }
    </style>
    </head>
    <body>
    <h1>站名包含 <span class="keyword">“{{ keyword }}”</span> 的线路与车站</h1>
    {% if result %}
        {% for city, lines in result.items() %}
        <div class="city">
            <div class="city-name">{{ city }}</div>
            {% for line_name, info in lines.items() %}
            <div class="line">
                <div class="line-name" style="background:#{{ info.color }};">{{ line_name }}</div>
                <div class="stations">
                {% for s in info.stations %}
                    <span class="station">{{ s }}</span>
                {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    {% else %}
        <div class="empty">未找到包含“{{ keyword }}”的站名。</div>
    {% endif %}
    </body>
    </html>
    """

    template = Template(html_template)
    html = template.render(keyword=keyword, result=result)

    f = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
    f.write(html)

    # ---------- 3. html2image 生成图片 ----------
    hti = Html2Image(output_path=".", custom_flags=["--no-sandbox"])

    # 若找不到浏览器，可指定路径，例如：
    # hti = Html2Image(
    #     output_path=".",
    #     browser_executable=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    #     custom_flags=["--no-sandbox"],
    # )
    
    bin=b''
    with tempfile.NamedTemporaryFile(mode='w+b', suffix='.png') as f2, tempfile.NamedTemporaryFile(mode='w+b', suffix='.png') as f3:
        hti.screenshot(
            html_str=html,
            save_as=f2.name,
            size=(1000, 50000)
        )
        os.unlink(f.name)
        crop_top_until_blank_band(f2.name, f3.name)
        f3.seek(0)
        bin=f3.read()
    return bin




@register("metro_search", "YourName", "地铁站名查询器", "1.0.0")
class MetroSearch(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("查询")
    async def find(self, event: AstrMessageEvent, key: str):
        """
        用法：/查询 <站名>
        例：/查询 体育西路
        """
        # 1. 确认是群聊
        if not event.get_group_id():
            yield event.plain_result("这个指令只能在群聊里用哦～")
            return

        data=search(key)

        yield event.chain_result([Image.fromBytes(data)])

        
