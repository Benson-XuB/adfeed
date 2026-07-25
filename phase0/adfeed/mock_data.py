"""AdFeed AI — 模拟 1688 商品数据生成器 (增强版)

模拟真实 1688 卖家/ERP 导出的 Excel，内含：
- 50+ 条覆盖 8 大品类的真实模拟数据
- 故意埋入的违禁词（极限词 / 侵权品牌 / 虚假功效）
- 中式英文标题（模拟铺货卖家的脏数据）
- 残缺属性（缺失颜色/材质/尺码）
- SEO 关键词堆砌长标题
- 混合中英文分类名
- 多列名格式（模拟不同 ERP 导出）
"""

import random
import pandas as pd
from pathlib import Path
from typing import Optional

# ============================================================
# 违禁词种子 — 用于随机注入违规内容
# ============================================================
SUPERLATIVE_SEEDS = [
    "Best", "No.1", "Top1", "全球首发", "全网独家", "#1",
    "行业第一", "100% Natural", "Shopify Best Seller",
]
TRADEMARK_SEEDS = [
    "Nike同款", "Adidas风格", "Gucci面料", "LV经典",
    "iPhone原装", "Samsung官方",
]
FALSE_CLAIM_SEEDS = [
    "7天美白", "3天祛痘", "永不掉色", "永久保修",
    "包治百病", "抗癌防辐射",
]

# ============================================================
# 商品池 — 50+ 条，覆盖 8 大品类
# ============================================================
PRODUCT_POOL = [
    # ── 服饰 (8条) ──
    {
        "title": "夏季韩版宽松T恤女短袖纯棉ins风",
        "description": "2024新款韩版宽松短袖t恤女夏季纯棉半袖体恤ins潮牌百搭",
        "category": "女装>T恤", "price": 39.90, "material": "纯棉", "color": "白色",
    },
    {
        "title": "No.1 爆款运动鞋女透气网面轻便跑步鞋",
        "description": "No.1爆款运动鞋女款夏季透气网面轻便跑步鞋百搭",
        "category": "鞋类>运动鞋", "price": 129.00, "material": "网面+橡胶", "color": "粉色",
    },
    {
        "title": "男士商务休闲长袖衬衫纯色免烫修身",
        "description": "春秋季男士长袖衬衫商务正装纯色修身免烫抗皱",
        "category": "男装>衬衫", "price": 79.00, "material": "棉涤混纺", "color": "蓝色",
    },
    {
        "title": "全球首发冬季加厚羽绒服女中长款连帽Best Seller",
        "description": "全球首发2024冬季新款羽绒服女中长款加厚连帽保暖",
        "category": "女装>外套", "price": 259.00, "material": "白鸭绒", "color": "黑色",
    },
    {
        "title": "Top quality denim jacket men vintage washed",
        "description": "Top quality denim jacket men vintage washed casual coat",
        "category": "Apparel > Jackets", "price": 159.00, "material": "牛仔布", "color": "蓝色",
    },
    {
        "title": "女士高腰阔腿裤垂感宽松直筒拖地裤显瘦",
        "description": "秋冬季女士高腰阔腿裤垂感西装裤宽松直筒拖地裤百搭显瘦",
        "category": "女装>裤子", "price": 89.00, "material": "聚酯纤维", "color": "黑色",
    },
    {
        "title": "Adidas风格运动套装男春秋季卫衣长裤两件套",
        "description": "Adidas风格运动套装男士春秋季连帽卫衣长裤两件套休闲",
        "category": "男装>套装", "price": 139.00, "material": "棉+聚酯", "color": "灰色",
    },
    {
        "title": "hot sale summer beach dress floral print boho",
        "description": "Hot sale summer beach dress women floral print boho style loose",
        "category": "Women Clothing", "price": 69.00, "material": "雪纺", "color": "碎花",
    },

    # ── 电子/数码 (8条) ──
    {
        "title": "无线蓝牙耳机降噪运动长续航适用苹果安卓",
        "description": "无线蓝牙耳机真无线降噪运动跑步长续航适用苹果华为小米",
        "category": "数码>耳机", "price": 69.00, "material": "ABS+硅胶", "color": "白色",
    },
    {
        "title": "手机支架桌面懒人通用万向调节合金材质",
        "description": "手机支架桌面懒人支架通用万向调节合金材质稳固不晃",
        "category": "手机配件>支架", "price": 19.90, "material": "铝合金", "color": "银色",
    },
    {
        "title": "车载充电器快充双USB接口点烟器适用所有车型",
        "description": "车载充电器快充双USB接口点烟器充电头适用所有车型12V24V",
        "category": "汽车用品>充电器", "price": 25.00, "material": "ABS+电子元件", "color": "黑色",
    },
    {
        "title": "智能手表运动健康监测心率血氧防水男女通用",
        "description": "智能手表运动健康监测心率血氧计步多功能防水男女通用",
        "category": "数码>智能穿戴", "price": 159.00, "material": "金属+硅胶", "color": "黑色",
    },
    {
        "title": "100% Natural Wood Phone Case Handmade for iPhone Samsung",
        "description": "100% Natural real wood phone case handmade eco friendly",
        "category": "Phone Cases", "price": 49.00, "material": "天然木材", "color": "原木色",
    },
    {
        "title": "便携蓝牙音箱低音炮户外防水无线小钢炮",
        "description": "便携蓝牙音箱低音炮户外防水无线迷你小钢炮重低音",
        "category": "数码>音箱", "price": 79.00, "material": "ABS+金属网", "color": "黑色",
    },
    {
        "title": "type c usb cable fast charging 3A 1m 2m nylon braided",
        "description": "Type c usb cable fast charging 3A 1m 2m data sync nylon braided",
        "category": "Electronics > Cables", "price": 9.90, "material": "尼龙编织", "color": "黑色",
    },
    {
        "title": "iPhone原装同款无线充电器15W快充磁吸",
        "description": "iPhone原装同款无线充电器15W快充磁吸适用苹果14/15/16",
        "category": "手机配件>充电器", "price": 39.00, "material": "ABS+线圈", "color": "白色",
    },

    # ── 家居/家纺 (8条) ──
    {
        "title": "北欧简约台灯LED护眼学习卧室床头灯",
        "description": "北欧简约风格台灯LED护眼学习卧室床头书桌阅读灯",
        "category": "家居>灯具", "price": 59.00, "material": "金属+亚克力", "color": "白色",
    },
    {
        "title": "陶瓷咖啡杯套装情侣款北欧简约马克杯带勺",
        "description": "陶瓷咖啡杯套装情侣款一对北欧简约马克杯带勺子礼盒装",
        "category": "Home > Kitchen", "price": 35.00, "material": "陶瓷", "color": "白色",
    },
    {
        "title": "可折叠收纳箱大容量塑料储物箱衣服整理箱",
        "description": "可折叠收纳箱大容量加厚塑料储物箱衣服玩具整理箱家用",
        "category": "家居>收纳用品", "price": 29.90, "material": "PP塑料", "color": "灰色",
    },
    {
        "title": "门垫入户地垫吸水防滑厨房卫生间门口脚垫",
        "description": "门垫入户地垫吸水防滑厨房卫生间门口脚垫可裁剪",
        "category": "家居>地垫", "price": 25.00, "material": "化纤", "color": "棕色",
    },
    {
        "title": "memory foam pillow ergonomic neck support for sleep",
        "description": "Memory foam pillow ergonomic design neck support for side back sleeper",
        "category": "Home Textiles", "price": 89.00, "material": "记忆棉", "color": "白色",
    },
    {
        "title": "不锈钢保温壶大容量2L家用热水瓶暖水壶",
        "description": "不锈钢保温壶大容量2L家用热水瓶暖水壶24小时保温",
        "category": "家居>厨房用品", "price": 79.00, "material": "304不锈钢", "color": "银色",
    },
    {
        "title": "北欧风挂钟客厅静音简约现代创意时钟",
        "description": "北欧风挂钟客厅静音简约现代创意时钟12英寸免打孔",
        "category": "家居>装饰", "price": 49.00, "material": "ABS+玻璃", "color": "白色",
    },
    {
        "title": "luxury velvet sofa cushion cover 45x45cm euro",
        "description": "Luxury velvet sofa cushion cover 45x45cm european style decorative",
        "category": "Home Decor", "price": 29.90, "material": "天鹅绒", "color": "深蓝色",
    },

    # ── 美妆/个护 (7条) ──
    {
        "title": "面部精华液玻尿酸补水保湿抗皱紧致淡化细纹",
        "description": "面部精华液玻尿酸补水保湿抗皱紧致淡化细纹提亮肤色",
        "category": "美妆>护肤", "price": 79.00, "material": "液体", "color": "透明",
    },
    {
        "title": "天然芦荟胶保湿舒缓晒后修复祛痘淡化痘印300ml",
        "description": "天然芦荟胶保湿舒缓补水晒后修复祛痘淡化痘印正品300ml",
        "category": "美妆>护肤", "price": 19.90, "material": "芦荟提取物", "color": "绿色",
    },
    {
        "title": "电动牙刷成人声波震动IPX7防水USB充电",
        "description": "电动牙刷成人声波震动5档模式IPX7防水USB充电配4刷头",
        "category": "个护>口腔护理", "price": 99.00, "material": "ABS+尼龙刷毛", "color": "白色",
    },
    {
        "title": "Makeup Brush Set 12Pcs Professional Synthetic",
        "description": "Professional makeup brush set 12pcs synthetic hair foundation powder eyeshadow",
        "category": "Beauty > Tools", "price": 45.00, "material": "人造纤维", "color": "粉色",
    },
    {
        "title": "生发洗发水生姜何首乌防脱育发固发男女通用7天见效",
        "description": "生发洗发水生姜何首乌配方防脱发育发固发男女通用500ml",
        "category": "个护>洗发", "price": 39.00, "material": "液体", "color": "棕色",
    },
    {
        "title": "organic tea tree essential oil 10ml pure natural",
        "description": "Organic tea tree essential oil 10ml pure natural aromatherapy",
        "category": "Beauty > Skincare", "price": 29.00, "material": "茶树精油", "color": "",
    },
    {
        "title": "口红持久保湿不脱色不沾杯哑光雾面唇釉",
        "description": "口红持久保湿不脱色不沾杯哑光雾面唇釉学生款",
        "category": "美妆>唇部", "price": 29.90, "material": "", "color": "豆沙色",
    },

    # ── 箱包/配饰 (5条) ──
    {
        "title": "双肩包女大容量旅行背包防盗USB充电口",
        "description": "双肩包女大容量旅行背包防盗USB充电口15.6寸电脑",
        "category": "箱包>双肩包", "price": 89.00, "material": "牛津布", "color": "黑色",
    },
    {
        "title": "Gucci面料质感真皮女士单肩包斜挎包",
        "description": "Gucci面料质感真皮女士单肩包斜挎包链条小方包",
        "category": "箱包>女包", "price": 159.00, "material": "PU皮革", "color": "酒红色",
    },
    {
        "title": "墨镜男偏光太阳镜潮流驾驶镜防紫外线",
        "description": "墨镜男偏光太阳镜潮流驾驶镜防紫外线高清",
        "category": "配饰>太阳镜", "price": 49.00, "material": "金属+树脂", "color": "黑色",
    },
    {
        "title": "腰带男士真皮自动扣商务休闲百搭裤带",
        "description": "腰带男士真皮自动扣商务休闲百搭裤带不卡扣",
        "category": "配饰>腰带", "price": 39.00, "material": "头层牛皮", "color": "黑色",
    },
    {
        "title": "silk scarf women luxury brand square 90x90cm",
        "description": "Silk scarf women luxury brand square 90x90cm hair neck wrap",
        "category": "Accessories > Scarves", "price": 55.00, "material": "桑蚕丝", "color": "花色",
    },

    # ── 母婴/玩具 (5条) ──
    {
        "title": "儿童益智积木拼装大颗粒1-3岁宝宝早教玩具",
        "description": "儿童益智积木拼装大颗粒1-3岁宝宝早教开发智力",
        "category": "母婴>玩具", "price": 59.00, "material": "ABS塑料", "color": "彩色",
    },
    {
        "title": "婴儿纯棉连体衣新生儿哈衣爬服春秋长袖",
        "description": "婴儿纯棉连体衣新生儿哈衣爬服春秋长袖0-12个月",
        "category": "母婴>婴儿服", "price": 29.90, "material": "纯棉", "color": "粉色",
    },
    {
        "title": "遥控汽车玩具男孩赛车漂移充电高速",
        "description": "遥控汽车玩具男孩赛车漂移充电高速四驱越野车",
        "category": "玩具>遥控车", "price": 89.00, "material": "ABS+电子元件", "color": "红色",
    },
    {
        "title": "宝宝爬行垫加厚XPE折叠地垫客厅家用",
        "description": "宝宝爬行垫加厚XPE折叠地垫客厅家用双面图案",
        "category": "母婴>爬行垫", "price": 69.00, "material": "XPE", "color": "",
    },
    {
        "title": "plush stuffed animal teddy bear 40cm soft",
        "description": "Plush stuffed animal teddy bear 40cm soft cotton cute gift",
        "category": "Toys > Plush", "price": 39.00, "material": "短毛绒", "color": "棕色",
    },

    # ── 运动/户外 (5条) ──
    {
        "title": "瑜伽垫加厚防滑NBR初学者健身垫舞蹈垫",
        "description": "瑜伽垫加厚防滑NBR材质初学者健身舞蹈运动垫",
        "category": "运动>瑜伽", "price": 49.00, "material": "NBR", "color": "紫色",
    },
    {
        "title": "登山杖折叠超轻铝合金户外徒步拐杖",
        "description": "登山杖折叠超轻铝合金户外徒步登山拐杖四节伸缩",
        "category": "户外>登山", "price": 69.00, "material": "铝合金", "color": "黑色",
    },
    {
        "title": "fitness resistance bands set 5pcs exercise elastic",
        "description": "Fitness resistance bands set 5pcs exercise elastic yoga pull up",
        "category": "Sports > Fitness", "price": 19.90, "material": "天然乳胶", "color": "彩色",
    },
    {
        "title": "露营帐篷3-4人全自动速开防雨防风",
        "description": "露营帐篷3-4人全自动速开防雨防风户外野营",
        "category": "户外>露营", "price": 199.00, "material": "牛津布+玻璃纤维", "color": "绿色",
    },
    {
        "title": "跳绳成人健身减脂专业版轴承计数",
        "description": "跳绳成人健身减脂专业版轴承计数负重钢丝绳",
        "category": "运动>跳绳", "price": 29.90, "material": "钢丝+硅胶", "color": "黑色",
    },

    # ── 厨房/餐具 (4条) ──
    {
        "title": "不粘锅炒锅32cm麦饭石家用燃气电磁炉通用",
        "description": "不粘锅炒锅32cm麦饭石家用燃气电磁炉通用少油烟",
        "category": "厨房>锅具", "price": 89.00, "material": "麦饭石涂层", "color": "",
    },
    {
        "title": "硅胶铲勺套装不粘锅专用耐高温厨房烹饪",
        "description": "硅胶铲勺套装不粘锅专用耐高温厨房烹饪烘焙6件套",
        "category": "厨房>厨具", "price": 39.00, "material": "食品级硅胶", "color": "灰色",
    },
    {
        "title": "stainless steel kitchen knife set 5pcs chef",
        "description": "Stainless steel kitchen knife set 5pcs chef knife block",
        "category": "Kitchen > Tools", "price": 129.00, "material": "不锈钢", "color": "",
    },
    {
        "title": "便携榨汁杯电动果汁机USB充电随行杯",
        "description": "便携榨汁杯电动果汁机USB充电随行杯迷你料理机",
        "category": "厨房>小家电", "price": 69.00, "material": "ABS+玻璃", "color": "绿色",
    },
]


def _maybe_inject_violation(title: str, description: str) -> tuple[str, str]:
    """随机注入违禁词（约25%概率）"""
    if random.random() < 0.25:
        seed = random.choice(SUPERLATIVE_SEEDS)
        title = f"{seed} {title}"
    if random.random() < 0.15:
        seed = random.choice(TRADEMARK_SEEDS + FALSE_CLAIM_SEEDS)
        description = f"{seed} {description}"
    return title, description


def _format_title_noise(title: str) -> str:
    """注入 1688 特有的标题噪音 — emoji / 年份前缀"""
    rolls = random.random()
    if rolls < 0.12:
        title = f"🔹{title}"
    elif rolls < 0.20:
        yr = random.choice(["2024", "2025", "2026"])
        title = f"{yr}新款 {title}"
    return title


def generate(seed: int = 42, count: int = 50) -> pd.DataFrame:
    """生成模拟 1688 商品数据

    Args:
        seed: 随机种子（相同种子生成相同数据）
        count: 目标数量

    Returns:
        DataFrame: columns = [SKU, 标题, 描述, 分类, 价格, 材质, 颜色, 尺码, 品牌, 图片链接, 库存]
    """
    random.seed(seed)

    # 循环取值，支持 count > pool size
    pool = list(PRODUCT_POOL)
    while len(pool) < count:
        pool += list(PRODUCT_POOL)

    selected = random.sample(pool, count)

    rows = []
    for i, p in enumerate(selected, 1):
        title, desc = _maybe_inject_violation(p["title"], p["description"])
        title = _format_title_noise(title)

        # 随机使一些属性缺失（模拟脏数据）
        material = p.get("material", "") if random.random() > 0.10 else ""
        color = p.get("color", "") if random.random() > 0.08 else ""
        size = (
            random.choice(["S", "M", "L", "XL", "均码", "One Size"])
            if random.random() > 0.25 else ""
        )

        rows.append({
            "SKU": f"SKU{i:04d}",
            "标题": title,
            "描述": desc,
            "分类": p["category"],
            "价格": p["price"] * random.uniform(0.85, 1.20),
            "材质": material,
            "颜色": color,
            "尺码": size,
            "品牌": "" if random.random() > 0.30 else random.choice(
                ["自主品牌", "OEM", "厂牌直供", "无品牌"]
            ),
            "图片链接": f"https://example.com/images/sku{i:04d}.jpg",
            "库存": random.randint(50, 5000),
        })

    return pd.DataFrame(rows)


def save(df: pd.DataFrame, path: Optional[Path] = None):
    """保存为 Excel"""
    if path is None:
        from adfeed.config import MOCK_OUTPUT_FILE
        path = MOCK_OUTPUT_FILE
    path = Path(path)
    df.to_excel(path, index=False, engine="openpyxl")
    violation_count = sum(
        1 for t in df["标题"]
        if any(kw.lower() in t.lower() for kw in SUPERLATIVE_SEEDS)
    )
    print(f"[MockData] 已生成 {len(df)} 条模拟 1688 数据")
    print(f"   含违禁词: {violation_count} 条 | 缺失材质: {df['材质'].eq('').sum()} 条 | 缺失颜色: {df['颜色'].eq('').sum()} 条")
    print(f"   输出: {path}")
