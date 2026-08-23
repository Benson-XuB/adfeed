"""AdFeed AI — 海外文化与场景痛点字典外挂 (AI-Friendly GEO Core)

12品类 × 5国家 = 60组完整四维数据。每个品类在每个国家含：
- occasions: 本地高频场景
- pain_points: 本地消费者痛点
- slang: 地道口语/搜索黑话
- seasonal: 四季趋势

数据来源：Google Ads Keyword Planner + Amazon Best Sellers + 本地电商语料
"""

from typing import Optional

# ═══════════════════════════════════════════════════════════════
# GPC 段位 → 12 品类规则表（Google Product Taxonomy 全覆盖）
#
# 解析策略：将 GPC 路径拆成段（如 "Apparel & Accessories >
# Clothing > Dresses"），对每个段做最长关键词匹配。
# 最长匹配优先，消除 "Game" 同时出现在 Electronics 和 Toys 的歧义。
# ═══════════════════════════════════════════════════════════════

GPC_SEGMENT_RULES: list[tuple[list[str], str]] = [

    # ── 01 apparel 服装鞋帽 ──
    (["apparel", "clothing", "costume", "uniform", "dress",
      "shirt", "blouse", "pant", "jean", "skirt", "jacket", "coat",
      "sweater", "hoodie", "sweatshirt", "outerwear", "raincoat",
      "windbreaker", "swimwear", "bikini", "swimsuit", "swim",
      "lingerie", "underwear", "bra", "panty", "bodysuit",
      "sock", "hosiery", "tie", "belt", "scarf", "glove", "hat", "cap",
      "sleepwear", "pajama", "robe", "suit", "blazer", "vest",
      "shorts", "t-shirt", "polo", "tank", "romper", "jumpsuit",
      "activewear", "legging", "yoga pant", "workout cloth",
      "cardigan", "pullover", "turtleneck", "thermal",
      "shoe", "sneaker", "boot", "sandal", "heel", "slipper",
      "footwear", "loafer", "flip-flop", "wedge", "mule", "clog",
      "kimono", "sarong", "cover-up", "onesie"],
     "apparel"),

    # ── 02 bags_luggage 箱包 ──
    (["luggage", "suitcase", "baggage", "carry-on", "backpack",
      "handbag", "purse", "wallet", "tote", "clutch", "duffel",
      "weekend bag", "messenger bag", "satchel", "waist pack",
      "fanny pack", "briefcase", "diaper bag", "cosmetic bag",
      "lunch bag", "gym bag", "camera bag", "laptop bag",
      "shopping bag", "drawstring bag", "travel bag"],
     "bags_luggage"),

    # ── 03 jewelry_watches 珠宝手表 ──
    (["jewelry", "watch", "necklace", "ring", "bracelet", "earring",
      "pendant", "cufflink", "anklet", "brooch", "charm",
      "gemstone", "tiara", "chain", "locket", "timepiece",
      "hair accessory", "hair clip", "hair band", "hair pin",
      "headband", "scrunchie", "barrette", "sunglass"],
     "jewelry_watches"),

    # ── 04 electronics 3C 数码 ──
    (["electronic", "cell phone", "mobile phone", "smartphone",
      "phone", "tablet", "laptop", "computer", "desktop", "monitor",
      "printer", "scanner", "camera", "digital camera",
      "headphone", "earbud", "earphone", "speaker", "bluetooth",
      "audio", "charger", "power bank", "power adapter",
      "gps", "drone", "gaming console", "virtual reality",
      "smart watch", "wearable tech", "smart home",
      "storage", "memory card", "usb drive", "cable",
      "keyboard", "mouse", "webcam", "projector", "router",
      "modem", "network", "charg", "adapter", "dock",
      "screen protect", "case", "mount", "holder",
      "battery", "power", "video game", "gaming"],
     "electronics"),

    # ── 05 home_living 家居生活 ──
    (["home", "garden", "furniture", "decor", "bedding", "lighting",
      "rug", "carpet", "curtain", "pillow", "mattress", "sofa",
      "chair", "table", "desk", "shelf", "storage", "organize",
      "clean", "household", "candle", "vase", "frame", "mirror",
      "clock", "basket", "plant", "flower", "improvement",
      "hardware", "tool", "patio", "lawn", "heating", "cooling",
      "fan", "air purifier", "humidifier", "vacuum", "iron",
      "sewing", "laundry", "security", "lock", "safety",
      "fire", "alarm", "smoke", "bath", "towel", "shower curtain",
      "soap", "dispenser", "toilet", "trash", "wall art",
      "poster", "print", "tapestry", "throw blanket", "comforter",
      "sheet", "duvet", "quilt", "bedspread", "nightstand",
      "dresser", "wardrobe", "coat rack", "shoe rack",
      "hook", "hanger", "diy", "paint", "wallpaper", "floor",
      "tile", "plumbing", "electrical", "solar light",
      "outdoor light", "string light", "lamp", "lantern",
      "doormat", "welcome mat", "room divider", "screen",
      "ottoman", "bench", "bookshelf", "bookcase", "cabinet",
      "buffet", "sideboard", "tv stand", "coffee table",
      "end table", "accent", "slipcover", "cushion"],
     "home_living"),

    # ── 06 kitchen_dining 厨房餐饮 ──
    (["kitchen", "cookware", "dinnerware", "drinkware", "bakeware",
      "dining", "cook", "pot", "pan", "cutlery", "flatware",
      "utensil", "bake", "roast", "grill", "food storage",
      "contain", "serveware", "coffee", "tea", "barware",
      "wine glass", "mug", "cup", "plate", "bowl", "dish",
      "measur", "thermos", "tumbler", "water bottle", "flask",
      "lunch box", "bento", "food container", "jar", "canister",
      "spice rack", "condiment", "oil", "vinegar", "cruet",
      "pepper mill", "salt", "knife", "cutting board", "chopping",
      "colander", "strainer", "sieve", "whisk", "spatula",
      "tongs", "ladle", "peeler", "grater", "zester",
      "rolling pin", "pastry", "cake", "muffin", "loaf",
      "casserole", "baking sheet", "parchment", "silicone",
      "oven mitt", "apron", "trivet", "coaster", "placemat",
      "tablecloth", "napkin", "centerpiece", "charger plate",
      "decanter", "corkscrew", "ice bucket", "cocktail",
      "espresso", "french press", "pour over", "tea kettle",
      "teapot", "infuser", "steeper", "matcha", "milk frother"],
     "kitchen_dining"),

    # ── 07 beauty_personal 美妆个护 ──
    (["beauty", "makeup", "cosmetic", "skincare", "fragrance",
      "perfume", "cologne", "hair care", "shampoo", "conditioner",
      "nail", "manicure", "pedicure", "personal care", "shower",
      "deodorant", "shaving", "razor", "oral care", "toothbrush",
      "toothpaste", "skin", "face", "body", "lotion", "cream",
      "serum", "sunscreen", "spf", "spa", "aromatherapy",
      "essential oil", "bath bomb", "bubble bath", "body wash",
      "body scrub", "exfoliat", "toner", "moisturiz", "cleanser",
      "eye cream", "eye shadow", "eyeliner", "mascara", "blush",
      "bronzer", "highlighter", "foundation", "concealer", "powder",
      "lipstick", "lip gloss", "lip balm", "lip liner", "lip",
      "makeup brush", "beauty blender", "sponge", "mirror compact",
      "lash", "eyebrow", "tweezer", "wax", "epilator", "shaver",
      "trimmer", "hair dryer", "straightener", "curling iron",
      "hot brush", "comb", "brush", "hair color", "hair dye",
      "henna", "wig", "extension", "toupee", "cotton swab",
      "cotton pad", "tissue", "wipe", "sanitizer", "hand soap"],
     "beauty_personal"),

    # ── 08 sports_outdoor 运动户外 ──
    (["sport", "outdoor", "camping", "hiking", "trekking",
      "fitness", "exercise", "yoga", "pilates", "cycling", "bike",
      "bicycle", "fishing", "hunting", "ski", "snowboard",
      "surf", "swim", "diving", "snorkel", "climbing",
      "golf", "tennis", "soccer", "football", "basketball",
      "baseball", "softball", "volleyball", "running",
      "jogging", "gym", "workout", "weight", "martial",
      "boxing", "wrestling", "gymnastics", "dance", "ballet",
      "skate", "roller", "scooter", "trampoline", "tent",
      "sleeping bag", "backpacking", "hammock", "cooler",
      "lantern", "flashlight", "headlamp", "compass", "map",
      "binocular", "walking stick", "trekking pole", "rain gear",
      "insect", "mosquito", "bug repellent", "first aid",
      "survival", "emergency", "multi-tool", "pocket knife",
      "paddle", "kayak", "canoe", "wetsuit", "life jacket",
      "archery", "paintball", "airsoft", "dart", "frisbee",
      "kite", "badminton", "table tennis", "ping pong",
      "pickleball", "racquetball", "squash", "lacrosse",
      "field hockey", "cricket", "rugby", "handball"],
     "sports_outdoor"),

    # ── 09 pet_supplies 宠物用品 ──
    (["pet", "dog", "cat", "bird", "fish", "reptile", "small animal",
      "aquarium", "terrarium", "litter", "aquatic", "hamster",
      "guinea pig", "rabbit", "ferret", "turtle", "parrot",
      "chicken", "horse", "livestock", "kennel", "crate",
      "aquarium", "tank", "collar", "leash", "harness",
      "groom", "shampoo", "brush", "nail clipper", "flea",
      "tick", "worm", "vitamin", "supplement", "treat",
      "chew", "toy", "scratch", "climb", "bed",
      "carrier", "cage", "bowl", "feeder", "fountain",
      "training", "clicker", "whistle", "potty", "pee pad",
      "poop bag", "litter box", "litter scoop", "cat tree",
      "scratching post", "catnip", "cat grass"],
     "pet_supplies"),

    # ── 10 toys_kids_baby 玩具母婴 ──
    (["baby", "toddler", "infant", "newborn", "nursery",
      "stroller", "crib", "diaper", "feeding", "breast",
      "pacifier", "teething", "maternity", "pregnancy",
      "board game", "card game", "jigsaw", "building block",
      "construction toy", "educational toy", "learning toy",
      "montessori", "toy", "doll", "action figure", "plush",
      "stuffed animal", "puppet", "play set", "play kitchen",
      "playhouse", "play tent", "ride-on", "push toy",
      "pull toy", "stacking toy", "sorting toy", "shape sorter",
      "musical toy", "bath toy", "car seat", "booster",
      "high chair", "baby carrier", "swaddle", "sleep sack",
      "bottle", "sippy cup", "bib", "burp cloth", "changing pad",
      "changing table", "play mat", "play gym", "mobile",
      "night light", "baby monitor", "safety gate", "corner guard",
      "outlet cover", "cabinet lock", "potty training"],
     "toys_kids_baby"),

    # ── 11 automotive 汽车配件 ──
    (["automotive", "vehicle", "car", "truck", "motorcycle",
      "auto", "tire", "wheel", "engine", "atv", "rv",
      "trailer", "seat cover", "floor mat", "steering wheel",
      "dash", "visor", "sun shade", "phone mount", "car charger",
      "jump starter", "air compressor", "tire inflator",
      "diagnostic", "obd", "scan tool", "code reader",
      "car wash", "detailing", "polish", "wax", "buffing",
      "microfiber", "cleaning", "clay bar", "ceramic coat",
      "car cover", "bike rack", "roof rack", "cargo carrier",
      "hitch", "tow", "winch", "recovery strap",
      "emergency kit", "roadside", "jumper cable", "warning",
      "reflector", "light bar", "led light", "fog light",
      "headlight", "taillight", "turn signal", "side mirror",
      "backup camera", "dash cam", "parking sensor",
      "key fob", "key chain", "remote start", "gps tracker",
      "alarm system", "stereo", "radio", "subwoofer",
      "amplifier", "speaker", "bluetooth kit", "aux cable",
      "usb charger", "power inverter", "fuse",
      "oil filter", "air filter", "cabin filter", "wiper blade"],
     "automotive"),

    # ── 12 office_stationery 办公文具 ──
    (["office", "school", "art", "craft", "stationery",
      "pen", "pencil", "notebook", "paper", "binder", "folder",
      "organizer", "calendar", "planner", "stapler", "tape",
      "glue", "marker", "crayon", "paint", "scissor", "ruler",
      "eraser", "whiteboard", "chalk", "easel", "canvas",
      "sticker", "label", "envelope", "stamp", "ink",
      "toner", "cartridge", "calculator", "clipboard",
      "push pin", "thumbtack", "binder clip", "paper clip",
      "rubber band", "index card", "post-it", "sticky note",
      "journal", "sketchbook", "coloring book", "drawing",
      "calligraphy", "brush pen", "fountain pen", "gel pen",
      "ballpoint", "highlighter", "correction", "washi tape",
      "stamp pad", "embosser", "laminator", "shredder",
      "hole punch", "ring binder", "portfolio", "presentation",
      "report cover", "sheet protector", "divider", "tab",
      "accordion", "file box", "magazine holder", "desk tray",
      "pen holder", "pencil case", "supply caddy", "cart",
      "drawer organizer", "desk pad", "mouse pad", "wrist rest",
      "monitor stand", "laptop stand", "standing desk",
      "dry erase", "bulletin board", "cork board", "magnetic"],
     "office_stationery"),
]


# ═══════════════════════════════════════════════════════════════
# 核心文化矩阵 — 12品类 × 5国
# ═══════════════════════════════════════════════════════════════

CULTURAL_MATRIX: dict = {

    # ────────────────────────────────────────
    # 🇺🇸 美国
    # ────────────────────────────────────────
    "US": {

        # —— 01 ——
        "apparel": {
            "occasions": [
                "Summer Wedding Guest", "Bridal Shower", "Baby Shower",
                "Business Casual Office", "Weekend Brunch", "Fall Layering",
                "Vacation Resort Wear", "Concert Outfit", "Date Night",
                "Country Club Casual", "Girls Night Out", "Family Photo Shoot",
            ],
            "pain_points": [
                "Tummy Control", "Plus Size Friendly", "Petite Fit",
                "Tall Length", "Curvy Silhouette", "Not See-Through",
                "Sweat-Proof", "Wrinkle-Free Travel", "Nursing Friendly",
                "Maternity Wear", "Chub Rub Prevention", "Back Fat Coverage",
            ],
            "slang": [
                "Comfy-Chic", "Effortless Style", "Day-to-Night",
                "Flattering Fit", "True to Size", "Stretchy & Soft",
                "Slimming Effect", "Hidden Pocket", "Matching Set",
                "Oversized Vibe", "Girly Aesthetic", "Streetwear Fit",
            ],
            "seasonal": {
                "spring": ["Spring Layering", "Pastel Colors", "Easter Brunch", "Denim Jacket Season"],
                "summer": ["Beach Day", "Poolside", "Summer Friday", "Music Festival Fashion"],
                "fall":  ["Pumpkin Patch", "Fall Wedding", "Thanksgiving Dinner", "Sweater Weather"],
                "winter": ["Christmas Party", "NYE Outfit", "Ski Trip", "Holiday Gift"],
            },
            "search_prefix": "Women's"
        },

        # —— 02 ——
        "bags_luggage": {
            "occasions": [
                "Weekend Getaway", "Carry-On Travel", "College Commute",
                "Summer Vacation", "Business Trip", "Gym & Work Dual-Use",
                "Beach Day Tote", "Diaper Bag Duty",
            ],
            "pain_points": [
                "Fits Under Seat", "TSA Approved", "Laptop Compartment",
                "Expandable Capacity", "Won't Tip Over", "Lightweight Carry",
                "Anti-Theft Zipper", "Water Bottle Pocket", "USB Charging Port",
            ],
            "slang": [
                "Personal Item Bag", "Weekender", "Workhorse Tote",
                "Sleek & Professional", "Pack Light Hero", "Daily Commuter",
            ],
            "seasonal": {
                "spring": ["Spring Break Trip", "Weekend Travel Bag"],
                "summer": ["Beach Tote", "Summer Vacation Luggage", "Pool Bag"],
                "fall":  ["Back to School Backpack", "Fall Getaway Duffel"],
                "winter": ["Holiday Travel Set", "Christmas Gift Tote"],
            },
        },

        # —— 03 ——
        "jewelry_watches": {
            "occasions": [
                "Bridal Party Gift", "Valentine Gift", "Anniversary",
                "Birthday Present", "Prom Jewelry", "Everyday Stack",
                "Mother's Day Gift", "Graduation Gift",
            ],
            "pain_points": [
                "Hypoallergenic", "Won't Tarnish", "Waterproof Wear",
                "No Green Skin", "Nickel-Free", "Dainty But Durable",
                "Layered Look Set", "Adjustable Fit",
            ],
            "slang": [
                "Minimalist Gold", "Everyday Staple", "Stackable Rings",
                "Dainty Chain", "Statement Piece", "Personalized Touch",
                "Timeless Elegance", "Chic & Simple",
            ],
            "seasonal": {
                "spring": ["Spring Bling", "Pastel Gemstone", "Mother's Day Jewelry"],
                "summer": ["Beach Jewelry", "Boho Summer Stack", "Anklet Season"],
                "fall":  ["Autumn Warm Tones", "Thanksgiving Gift Set"],
                "winter": ["Christmas Jewelry Gift", "NYE Sparkle", "Valentine's Prep"],
            },
        },

        # —— 04 ——
        "electronics": {
            "occasions": [
                "Back to School", "Work From Home Setup", "Gaming Setup",
                "Road Trip", "Home Theater", "College Dorm Essentials",
                "Daily Commute", "Gym Workout",
            ],
            "pain_points": [
                "Fast Charging", "Long Battery Life", "Noise Cancelling",
                "Waterproof Rating", "Drop Protection", "Anti-Yellowing",
                "Universal Compatibility", "Easy Install", "No Lag",
                "Sweat-Proof for Gym", "Tangle-Free Cable",
            ],
            "slang": [
                "Game-Changer", "Must-Have", "Daily Driver",
                "Bang for the Buck", "Plug and Play", "Sleek Design",
                "Lifesaver", "Setup Upgrade",
            ],
            "seasonal": {
                "spring": ["Spring Tech Refresh", "Travel Gadget Season"],
                "summer": ["Beach-Proof Speaker", "Pool Party Tech", "Waterproof Earbuds"],
                "fall":  ["Back to School Tech", "College Dorm Essentials", "Black Friday Prep"],
                "winter": ["Stocking Stuffer", "Christmas Gift for Him", "Holiday Travel Gadget"],
            },
        },

        # —— 05 ——
        "home_living": {
            "occasions": [
                "Housewarming Gift", "Apartment Essentials", "Dorm Room Decor",
                "Thanksgiving Hosting", "Christmas Decoration", "Home Office Refresh",
                "Nursery Setup", "First Apartment Haul",
            ],
            "pain_points": [
                "Space-Saving", "Easy to Clean", "Pet-Friendly",
                "Renter-Friendly", "No Tools Required", "Cord Management",
                "Washable Cover", "Scratch-Resistant", "Collapsible Storage",
            ],
            "slang": [
                "Aesthetic Vibes", "Cozy Home", "Minimalist Look",
                "Boho Decor", "Farmhouse Style", "Modern Chic",
                "Shelf Styling", "Room Refresh",
            ],
            "seasonal": {
                "spring": ["Spring Cleaning", "Home Refresh", "Patio Season"],
                "summer": ["Outdoor Living", "Backyard Oasis", "Poolside Decor"],
                "fall":  ["Cozy Fall Decor", "Thanksgiving Tablescape", "Hygge Style"],
                "winter": ["Christmas Ornaments", "Holiday Hosting", "Winter Nesting"],
            },
        },

        # —— 06 ——
        "kitchen_dining": {
            "occasions": [
                "Thanksgiving Prep", "Christmas Baking", "Meal Prep Sunday",
                "Dinner Party Host", "Coffee Lover Setup", "Camping Cookout",
            ],
            "pain_points": [
                "Non-Stick Lasts", "Dishwasher Safe", "Space-Saving Stackable",
                "Even Heat Distribution", "No Plastic Taste", "Easy Pour Spout",
                "Airtight Seal", "Stay-Cold Insulation", "Non-Slip Grip",
            ],
            "slang": [
                "Kitchen Essential", "Cooking Game-Changer", "Meal Prep Hero",
                "Aesthetic Serveware", "Barista at Home", "Hosting Must-Have",
            ],
            "seasonal": {
                "spring": ["Spring Brunch Serveware", "Easter Table"],
                "summer": ["BBQ Grill Tools", "Iced Coffee Essentials", "Outdoor Dining"],
                "fall":  ["Thanksgiving Cookware", "Pumpkin Spice Mugs"],
                "winter": ["Christmas Baking Set", "Hot Cocoa Mugs", "Soup Season"],
            },
        },

        # —— 07 ——
        "beauty_personal": {
            "occasions": [
                "Daily Skincare Routine", "Wedding Makeup", "Prom Night",
                "Spa Day at Home", "Self-Care Sunday", "Date Night Glam",
                "Vacation Beauty Kit", "Post-Gym Refresh",
            ],
            "pain_points": [
                "Sensitive Skin", "Acne-Prone", "Anti-Aging",
                "Dark Spot Correction", "Pore Minimizing", "Oil Control",
                "Long-Lasting Wear", "Transfer-Proof", "Cruelty-Free",
            ],
            "slang": [
                "Glow Up", "Glass Skin", "Clean Girl Aesthetic",
                "Holy Grail", "K-Beauty Routine", "Dermatologist-Tested",
                "Skin Barrier Repair", "Dewy Finish",
            ],
            "seasonal": {
                "spring": ["Spring Skincare Reset", "Allergy-Safe Makeup"],
                "summer": ["SPF Protection", "Beach-Proof Makeup", "Sweat-Resistant Foundation"],
                "fall":  ["Fall Skin Barrier Repair", "Autumn Warm Tones Makeup"],
                "winter": ["Winter Hydration Routine", "Holiday Party Glam", "Cracked Skin Rescue"],
            },
        },

        # —— 08 ——
        "sports_outdoor": {
            "occasions": [
                "Weekend Camping Trip", "Daily Yoga Practice", "Marathon Training",
                "Hiking Trail Day", "Beach Volleyball", "Backyard Workout",
                "Lake Day Fishing", "Road Cycling",
            ],
            "pain_points": [
                "Extra Thick Cushion", "Non-Slip Grip", "Quick Dry Material",
                "Lightweight Packable", "Waterproof Storage", "UV Protection",
                "Low Impact Joint Friendly", "Compact Foldable", "Bug Protection",
            ],
            "slang": [
                "Workout Essential", "Trail Ready", "Adventure Proof",
                "Personal Best", "Recovery Must", "Outdoor Obsession",
                "Camping MVP", "Weekend Warrior Gear",
            ],
            "seasonal": {
                "spring": ["Spring Trail Hiking", "Outdoor Yoga Season"],
                "summer": ["Beach Workout", "Camping Trip Gear", "Lake Day Fishing"],
                "fall":  ["Fall Trail Running", "Football Tailgate"],
                "winter": ["Ski Trip Prep", "Winter Camping", "Ice Fishing Gear"],
            },
        },

        # —— 09 ——
        "pet_supplies": {
            "occasions": [
                "New Puppy Essentials", "Dog Park Day", "Pet Travel Trip",
                "Cat Cuddle Time", "Pet Birthday Party", "Apartment Potty Training",
            ],
            "pain_points": [
                "Chew-Proof Material", "Easy Washable Cover", "Non-Slip Bottom",
                "Odor Control", "Shedding Control", "No-Tip Bowl Design",
                "Escape-Proof Harness", "Quiet Nail Grinder", "Cat Scratcher Durable",
            ],
            "slang": [
                "Fur Baby Approved", "Zoomies Proof", "Pawrent Must-Have",
                "Good Boy Gear", "Cat Lady Essential", "Dog Mom Life",
            ],
            "seasonal": {
                "spring": ["Spring Shedding Brush", "Flea & Tick Prevention"],
                "summer": ["Cooling Mat", "Pet Pool Float", "Travel Water Bottle"],
                "fall":  ["Cozy Pet Sweater", "Pumpkin Pet Bandana"],
                "winter": ["Christmas Pet Gift", "Heated Cat Bed", "Snow Booties"],
            },
        },

        # —— 10 ——
        "toys_kids_baby": {
            "occasions": [
                "Birthday Party Gift", "Baby Shower Gift", "Christmas Morning",
                "Rainy Day Activity", "Travel Car Entertainment", "Potty Training Reward",
                "Tummy Time Play", "Preschool Learning",
            ],
            "pain_points": [
                "BPA-Free", "Non-Toxic Material", "Choke-Proof", "Easy to Clean",
                "Quiet Motor", "No Small Parts", "Storage Bag Included",
                "Washable Fabric", "Teething Safe", "Montessori-Aligned",
            ],
            "slang": [
                "Screen-Free Fun", "Busy Toddler", "Playroom Staple",
                "Giftable Set", "Mama Approved", "Open-Ended Play",
                "Fine Motor Skills", "Sensory Exploration",
            ],
            "seasonal": {
                "spring": ["Easter Basket Gift", "Spring Outdoor Toys"],
                "summer": ["Pool Toys", "Travel Car Entertainment", "Backyard Play"],
                "fall":  ["Back to School Supplies", "Halloween Costume Prep"],
                "winter": ["Christmas Gift List", "Indoor Toddler Activity", "Stocking Stuffer"],
            },
        },

        # —— 11 ——
        "automotive": {
            "occasions": [
                "Road Trip Prep", "New Car Setup", "Daily Commute Upgrade",
                "Weekend Detailing", "Rideshare Driver Essential", "Winter Prep",
            ],
            "pain_points": [
                "Dash-Safe Adhesive", "One-Hand Operation", "No Residue Removal",
                "Universal Fit Clip", "Vibration-Proof Mount", "Quick Charge PD",
                "Scratch-Proof Material", "Heat-Resistant Grip",
            ],
            "slang": [
                "Car Setup Must", "Daily Driver Upgrade", "Detailer-Approved",
                "Road Trip Ready", "Clean Car Club", "Interior Game-Changer",
            ],
            "seasonal": {
                "spring": ["Spring Car Cleaning", "All-Season Floor Mats"],
                "summer": ["Sunshade Protector", "Vent Phone Mount", "Car Cooler"],
                "fall":  ["Fall Detail Kit", "Rain-Proof Floor Mats"],
                "winter": ["Ice Scraper", "Heated Seat Cover", "Winter Survival Kit"],
            },
        },

        # —— 12 ——
        "office_stationery": {
            "occasions": [
                "Home Office Setup", "College Dorm Desk", "Bullet Journaling",
                "Teacher Classroom", "Art & Craft Corner", "Small Business Packaging",
            ],
            "pain_points": [
                "Clutter-Free Desk", "Pens That Don't Smear", "Sturdy Binding",
                "Thick Paper No Bleed", "Lay-Flat Design", "Stackable Organizer",
                "Color-Coded System", "Washi Tape Friendly",
            ],
            "slang": [
                "Desk Aesthetic", "Stationery Obsessed", "Planner Girl",
                "Journaling Must", "Worthy of Instagram", "Organized Chaos",
                "Creative Toolkit", "Note-Taking MVP",
            ],
            "seasonal": {
                "spring": ["Spring Desk Refresh", "New Semester Supplies"],
                "summer": ["Summer Journaling", "Bullet Journal Season"],
                "fall":  ["Back to School Haul", "Planner Season", "Teacher Gift"],
                "winter": ["Christmas Card Supplies", "Holiday Gift Wrapping Kit"],
            },
        },

    },

    # ────────────────────────────────────────
    # 🇩🇪 德国
    # ────────────────────────────────────────
    "DE": {

        "apparel": {
            "occasions": [
                "Hochzeitsgast", "Business Meeting", "Sonntagsbrunch",
                "Stadtbummel", "Opernbesuch", "Gartenparty",
                "After-Work Drinks", "Weihnachtsmarkt Besuch",
            ],
            "pain_points": [
                "Bauchweg-Effekt", "Große Größen", "Atmungsaktiv",
                "Bügelfrei", "Pflegeleicht", "Nachhaltig produziert",
                "Bio-Baumwolle", "Fair Trade zertifiziert",
            ],
            "slang": [
                "Lässig-Schick", "Zeitlos Elegant", "Alltagstauglich",
                "Figurschmeichelnd", "Hochwertig verarbeitet", "Made in Europe",
                "Bequem & Chic", "Perfekt für den Alltag",
            ],
            "seasonal": {
                "spring": ["Frühlingslook", "Ostern Outfit", "Leichte Jacke"],
                "summer": ["Strandurlaub", "Sommerfest", "Biergarten tauglich"],
                "fall":   ["Herbstspaziergang", "Oktoberfest-tauglich", "Gemütlicher Pullover"],
                "winter": ["Weihnachtsfeier", "Silvesterparty", "Winterspaziergang"],
            },
            "search_prefix": "Damen"
        },

        "bags_luggage": {
            "occasions": [
                "Wochenendtrip", "Geschäftsreise", "Uni-Pendler",
                "Kurzurlaub", "Städtetrip", "Fahrradtasche",
            ],
            "pain_points": [
                "Handgepäck-tauglich", "Leicht & Robust", "Laptopfach gepolstert",
                "Wasserdicht", "Diebstahlschutz", "Made in Germany Qualität",
            ],
            "slang": [
                "Reise-Begleiter", "Büro-tauglich", "Platzwunder",
                "Praktisch & Schön", "City-tauglich", "Kult-Tasche",
            ],
            "seasonal": {
                "spring": ["Städtetrip Tasche", "Fahrrad Rucksack"],
                "summer": ["Strandtasche", "Reisekoffer Leichtgewicht"],
                "fall":   ["Business Rucksack", "Herbst Kurztrip Tasche"],
                "winter": ["Weihnachtsmarkt Tote", "Winter Reisegepäck"],
            },
        },

        "jewelry_watches": {
            "occasions": [
                "Hochzeitsgast Schmuck", "Geburtstagsgeschenk", "Jahrestag",
                "Taufe Accessoire", "Alltags-Schmuck", "Konfirmation Geschenk",
            ],
            "pain_points": [
                "Nickelfrei", "Allergiegetestet", "Läuft nicht an",
                "Wasserfest", "Mit Zertifikat", "Hautverträglich",
            ],
            "slang": [
                "Dezenter Luxus", "Handgefertigt", "Minimalistisch",
                "Zeitloses Design", "Liebhaberstück", "Filigran",
            ],
            "seasonal": {
                "spring": ["Frühlings-Schmuck", "Kommunion Geschenk"],
                "summer": ["Sommer Schmuck Set", "Leichte Kette"],
                "fall":   ["Herbst-Töne Schmuck", "Business-Uhr"],
                "winter": ["Weihnachtsgeschenk Schmuck", "Silvester Glanz"],
            },
        },

        "electronics": {
            "occasions": [
                "Homeoffice Ausstattung", "Gaming Zimmer", "Studentenwohnheim",
                "Pendler Alltag", "Fitness Studio",
            ],
            "pain_points": [
                "Schnelles Laden", "Lange Akkulaufzeit", "Geräuschunterdrückung",
                "Wasserdicht IPX", "Sturzsicher", "Kompatibel mit USB-C",
            ],
            "slang": [
                "Preis-Leistungs-Sieger", "Testsieger", "Allrounder",
                "Gaming-tauglich", "Made for Germany",
            ],
            "seasonal": {
                "spring": ["Frühjahrsputz Technik", "Gaming Setup Upgrade"],
                "summer": ["Outdoor Lautsprecher", "Urlaubs-Gadgets", "Wasserdichte Technik"],
                "fall":   ["Schulanfang Technik", "Studenten Essentials"],
                "winter": ["Weihnachtsgeschenk Technik", "Nikolaus Gadgets", "Schnäppchen Jagd"],
            },
        },

        "home_living": {
            "occasions": [
                "Einzugsgeschenk", "Wohnungsdeko", "Balkongestaltung",
                "Homeoffice Einrichtung", "Schlafzimmer Update",
            ],
            "pain_points": [
                "Platzsparend", "Leicht zu reinigen", "Ohne Bohren",
                "Mieterfreundlich", "Nachhaltiges Material", "Montagefrei",
            ],
            "slang": [
                "Gemütlich", "Skandinavischer Stil", "Industrial Look",
                "Wohnfühlen", "Deko-Highlight", "Minimalistisch Wohnen",
            ],
            "seasonal": {
                "spring": ["Frühjahrsputz", "Balkonbepflanzung", "Gartenmöbel"],
                "summer": ["Gartenparty", "Grillsaison", "Balkonien Deko"],
                "fall":   ["Herbstdeko", "Gemütlich einrichten", "Kerzenzeit"],
                "winter": ["Weihnachtsdeko", "Adventskranz", "Wintergarten"],
            },
        },

        "kitchen_dining": {
            "occasions": [
                "Grillparty", "Weihnachtsbäckerei", "Meal Prep Sonntag",
                "Kaffeeklatsch", "Brunch mit Freunden", "Fondue Abend",
            ],
            "pain_points": [
                "Spülmaschinenfest", "Antihaft-Beschichtung", "Platzsparend stapelbar",
                "Induktionsgeeignet", "Hitzebeständig", "Ohne Weichmacher",
            ],
            "slang": [
                "Küchen-Highlight", "Koch-Profi", "Barista Zuhause",
                "Servier-Traum", "Gäste-tauglich", "Made in Germany",
            ],
            "seasonal": {
                "spring": ["Oster-Brunch Geschirr", "Spargel-Saison Tools"],
                "summer": ["Grillbesteck Set", "Eiskaffee Gläser", "Outdoor Geschirr"],
                "fall":   ["Pflaumenkuchen Form", "Erntedank Dekoration"],
                "winter": ["Weihnachtsbäckerei", "Glühwein Tassen", "Raclette Set"],
            },
        },

        "beauty_personal": {
            "occasions": [
                "Tägliche Pflegeroutine", "Anti-Aging Pflege", "Wohlfühl-Abend",
                "Festtags Make-up", "After-Work Frische",
            ],
            "pain_points": [
                "Empfindliche Haut", "Unreine Haut", "Faltenvorbeugung",
                "Naturkosmetik", "Ohne Parabene", "Vegan zertifiziert",
                "Mikroplastik-frei", "Dermatest Sehr Gut",
            ],
            "slang": [
                "Apothekenqualität", "Dermatologisch getestet", "Clean Beauty",
                "Natürliche Schönheit", "Hautverträglich", "Bio-Qualität",
            ],
            "seasonal": {
                "spring": ["Frühlingspflege", "Allergie-Hautpflege", "Leichte Textur"],
                "summer": ["Sonnenschutz LSF50", "After-Sun Pflege", "Wasserfest Make-up"],
                "fall":   ["Herbst-Hauterneuerung", "Feuchtigkeitsboost"],
                "winter": ["Winter-Hautschutz", "Reichhaltige Creme", "Weihnachts-Specials"],
            },
        },

        "sports_outdoor": {
            "occasions": [
                "Wanderwochenende", "Fitnessstudio Training", "Joggen im Park",
                "Fahrradtour", "Camping Urlaub", "Yoga zuhause",
            ],
            "pain_points": [
                "Rutschfest", "Atmungsaktiv", "Leicht & Kompakt",
                "Wasserdicht", "Gelenkschonend", "Nachhaltig produziert",
            ],
            "slang": [
                "Outdoor-tauglich", "Trainings-Buddy", "Bergfest",
                "Fitness Must-Have", "Natur Erlebnis", "Aktiv & Frei",
            ],
            "seasonal": {
                "spring": ["Wanderfrühling", "Fahrrad-Saison Start"],
                "summer": ["Camping Ausrüstung", "SUP Board Zubehör", "Badesee Tag"],
                "fall":   ["Herbstwanderung", "Trail Running Schuhe"],
                "winter": ["Ski Zubehör", "Winterwanderung", "Thermo Outdoor"],
            },
        },

        "pet_supplies": {
            "occasions": [
                "Welpe Einzug", "Hundepark Tag", "Katzen Kuschelzeit",
                "Tierarzt Besuch", "Urlaub mit Hund",
            ],
            "pain_points": [
                "Kausicher", "Waschbar bei 60°", "Rutschfest",
                "Geruchsneutral", "Leicht zu reinigen", "Ausbruchsicher",
            ],
            "slang": [
                "Fellnasen-Liebling", "Herrchen-geprüft", "Samtpfoten Paradies",
                "Gassigeh Must-Have", "Tierisch Gut", "Katzen-Wohlfühl",
            ],
            "seasonal": {
                "spring": ["Frühjahrs Fellpflege", "Zecken Schutz"],
                "summer": ["Kühlmatte Hund", "Reise-Trinkflasche Tier"],
                "fall":   ["Hunde Regenmantel", "Gemütliches Katzenbett"],
                "winter": ["Weihnachtsgeschenk Hund", "Winter Pfoten-Schutz"],
            },
        },

        "toys_kids_baby": {
            "occasions": [
                "Geburtstagsgeschenk", "Weihnachtsgeschenk", "Einschulung",
                "Regentag Beschäftigung", "Krabbelgruppe", "Kindergarten Start",
            ],
            "pain_points": [
                "Schadstofffrei", "CE zertifiziert", "Verschluck-sicher",
                "Leise", "Waschbar", "Fördert Motorik", "Nachhaltig Holz",
            ],
            "slang": [
                "Spielerisch Lernen", "Montessori-inspiriert", "Kinderzimmer Held",
                "Mama-geprüft", "Lieblingsspielzeug", "Beschäftigung Wunder",
            ],
            "seasonal": {
                "spring": ["Oster-Geschenk", "Outdoor Spielzeug"],
                "summer": ["Sandkasten Spielzeug", "Wasserspielzeug", "Reisespiele"],
                "fall":   ["Schulstart Geschenk", "Laternenumzug Bastelei"],
                "winter": ["Nikolaus Geschenk", "Weihnachts-Wunschzettel Top"],
            },
        },

        "automotive": {
            "occasions": [
                "Roadtrip Urlaub", "Pendler Alltag", "Autopflege Wochenende",
                "Winter-Vorbereitung", "Neuwagen Ausstattung",
            ],
            "pain_points": [
                "Rüttelfest", "Restlos entfernbar", "Universelle Halterung",
                "Kratzfrei", "Hitzebeständig", "Schnellladung",
            ],
            "slang": [
                "Auto Must-Have", "Fahrer-Liebling", "Pendler-Held",
                "Ordnung im Auto", "TÜV-geprüft", "Deutsche Qualität",
            ],
            "seasonal": {
                "spring": ["Frühjahrs Autopflege", "Pollenfilter tauschen"],
                "summer": ["Sonnenschutz Auto", "Kühlbox fürs Auto", "Urlaubs-Roadtrip"],
                "fall":   ["Regen-Fußmatten", "Herbst Autopflege"],
                "winter": ["Eiskratzer", "Sitzheizung Auflage", "Winterreifen Tasche"],
            },
        },

        "office_stationery": {
            "occasions": [
                "Homeoffice Einrichtung", "Uni Semester Start", "Bullet Journal",
                "Lehrer Geschenk", "Kreativ Ecke", "Steuerunterlagen Ordnung",
            ],
            "pain_points": [
                "Schreibtisch Ordnung", "Tinte trocknet nicht ein", "Papier reißfest",
                "Farbcodiert", "Stapelbar", "Made in Germany",
            ],
            "slang": [
                "Schreibtisch Deko", "Schreibwaren Liebe", "Ordnungssystem",
                "Kreativ mit Stil", "Büro Schönheit", "Planer Herz",
            ],
            "seasonal": {
                "spring": ["Frühjahrs Schreibtisch Update", "Neue Semester Planer"],
                "summer": ["Sommer Journal", "Kreativ-Set Urlaub"],
                "fall":   ["Schulanfang Stationery", "Lehrer Dankeschön"],
                "winter": ["Weihnachtskarten Basteln", "Jahresplaner neu"],
            },
        },

    },

    # ────────────────────────────────────────
    # 🇫🇷 法国
    # ────────────────────────────────────────
    "FR": {

        "apparel": {
            "occasions": [
                "Mariage Champêtre", "Soirée Cocktail", "Brunch Dominical",
                "Tenue de Bureau", "Vacances à la Mer", "Week-end à la Campagne",
                "Apéro entre Amis", "Sortie Culturelle",
            ],
            "pain_points": [
                "Ventre Plat", "Grandes Tailles", "Morphologie en Huit",
                "Anti-Transparence", "Infroissable", "Made in France",
                "Tissu Naturel", "Entretien Facile",
            ],
            "slang": [
                "Chic Décontracté", "Élégance à la Française", "Intemporel",
                "Coupe Flatteuse", "Belle Qualité", "Fabrication Européenne",
                "Look effortless", "Pièce Essentielle",
            ],
            "seasonal": {
                "spring": ["Tenue de Pâques", "Look Printanier", "Veste Légère"],
                "summer": ["Plage", "Festival d'Été", "Rooftop Parisien"],
                "fall":   ["Rentrée Élégante", "Soirée Automnale", "Trench de Saison"],
                "winter": ["Fêtes de Noël", "Saint-Sylvestre", "Ski Chic"],
            },
            "search_prefix": "Femme"
        },

        "bags_luggage": {
            "occasions": [
                "Week-end en Amoureux", "Voyage d'Affaires", "Cours à la Fac",
                "Vacances d'Été", "Escapade Citadine", "Sac de Plage",
            ],
            "pain_points": [
                "Format Cabine", "Compartiment Ordinateur", "Léger et Solide",
                "Étanche", "Fermeture Sécurisée", "Made in France",
            ],
            "slang": [
                "Indispensable Voyage", "Chic et Pratique", "Compagnon de Route",
                "Beau Cuir", "Format Idéal", "Sac Fétiche",
            ],
            "seasonal": {
                "spring": ["Sac Week-end Printanier", "Cartable Universitaire"],
                "summer": ["Sac de Plage Tendance", "Valise Vacances Légère"],
                "fall":   ["Sacoche Rentrée", "Bagage Week-end Automne"],
                "winter": ["Sac Week-end Noël", "Valise Sports d'Hiver"],
            },
        },

        "jewelry_watches": {
            "occasions": [
                "Cadeau de Saint-Valentin", "Mariage Bijoux", "Anniversaire",
                "Bijou du Quotidien", "Fête des Mères", "Baptême",
            ],
            "pain_points": [
                "Sans Nickel", "Ne Noircit Pas", "Hypoallergénique",
                "Résistant à l'Eau", "Fait Main", "Garanti Qualité",
            ],
            "slang": [
                "Bijou Minimaliste", "Élégance Discrète", "Fait à la Main",
                "Pièce Unique", "Qualité Joaillerie", "Raffiné et Simple",
            ],
            "seasonal": {
                "spring": ["Bijou Printanier", "Fête des Mères Bijou"],
                "summer": ["Bijou Plage", "Chaîne de Cheville Tendance"],
                "fall":   ["Bijou Tons Chauds", "Montre Classique"],
                "winter": ["Bijou pour Noël", "Éclat du Nouvel An"],
            },
        },

        "electronics": {
            "occasions": [
                "Télétravail", "Setup Gaming", "Rentrée Étudiante",
                "Trajet Quotidien", "Sport & Musique",
            ],
            "pain_points": [
                "Charge Rapide", "Longue Autonomie", "Suppression de Bruit",
                "Étanche IPX", "Anti-Chute", "Compatible USB-C",
            ],
            "slang": [
                "Rapport Qualité-Prix", "Incontournable", "Compact Efficace",
                "Design Épuré", "Indispensable Quotidien",
            ],
            "seasonal": {
                "spring": ["Nettoyage de Printemps Tech", "Upgrade Setup"],
                "summer": ["Enceinte Plage", "Gadgets Vacances", "Écouteurs Étanches"],
                "fall":   ["Rentrée Tech", "Essentiels Bureau Étudiant"],
                "winter": ["Idée Cadeau Noël High-Tech", "Soldes d'Hiver"],
            },
        },

        "home_living": {
            "occasions": [
                "Cadeau de Crémaillère", "Déco Appartement", "Chambre Cocooning",
                "Bureau à Domicile", "Salon Conviviale",
            ],
            "pain_points": [
                "Gain de Place", "Facile à Nettoyer", "Sans Percage",
                "Look Déco", "Multi-Usage", "Naturel et Durable",
            ],
            "slang": [
                "Look Scandinave", "Style Bohème", "Déco Chic",
                "Ambiance Cosy", "Fait avec Goût", "Esprit Maison",
            ],
            "seasonal": {
                "spring": ["Nettoyage de Printemps Déco", "Jardinage Urbain"],
                "summer": ["Terrasse Conviviale", "Barbecue Jardin", "Déco Estivale"],
                "fall":   ["Déco Automnale Cosy", "Rentrée Maison"],
                "winter": ["Déco Noël Française", "Cocooning Hiver"],
            },
        },

        "kitchen_dining": {
            "occasions": [
                "Dîner entre Amis", "Brunch du Dimanche", "Apéro Maison",
                "Cuisine du Quotidien", "Pâtisserie Maison", "Pique-nique Chic",
            ],
            "pain_points": [
                "Lave-Vaisselle", "Anti-Adhésif Durable", "Empilable",
                "Compatible Induction", "Sans BPA", "Facile à Tenir",
            ],
            "slang": [
                "Essentiel Cuisine", "Art de Recevoir", "Fait Maison",
                "Ustensile de Chef", "Belle Table", "Plaisir Gourmand",
            ],
            "seasonal": {
                "spring": ["Brunch de Pâques", "Service à Thé"],
                "summer": ["Vaisselle Pique-nique", "Verres à Pastis", "Barbecue Accessoires"],
                "fall":   ["Plat à Gratin", "Service Raclette"],
                "winter": ["Service à Fondue", "Bûche de Noël Moule", "Marché de Noël Tasse"],
            },
        },

        "beauty_personal": {
            "occasions": [
                "Routine Beauté Quotidienne", "Soin Anti-Âge", "Maquillage de Fête",
                "Moment Détente Spa", "Soin Cheveux Maison",
            ],
            "pain_points": [
                "Peau Sensible", "Anti-Rides", "Naturel Bio",
                "Sans Paraben", "Testé Dermatologiquement", "Vegan",
                "Fabriqué en France", "Sans Alcool",
            ],
            "slang": [
                "Pharmacie Française", "Clean Beauty", "Soin Luxe Abordable",
                "Peau Parfaite", "Beauté au Naturel", "Routine Minimaliste",
            ],
            "seasonal": {
                "spring": ["Soin Printanier", "Peau Éclatante", "Démaquillage Doux"],
                "summer": ["Protection Solaire SPF50", "Soin Après-Soleil", "Eau Thermale"],
                "fall":   ["Réparation Cutanée", "Hydratation Intense"],
                "winter": ["Protection Hiver", "Soin Mains Sèches", "Baume Lèvres"],
            },
        },

        "sports_outdoor": {
            "occasions": [
                "Randonnée Week-end", "Jogging Matinal", "Cyclisme Route",
                "Camping Nature", "Ski Alpin", "Yoga Maison",
            ],
            "pain_points": [
                "Antidérapant", "Respirant", "Compact Pliable",
                "Imperméable", "Léger", "Résistant au Vent",
            ],
            "slang": [
                "Prêt pour l'Aventure", "Esprit Outdoor", "Nature & Sport",
                "Équipement Fiable", "Sportif Urbain", "Performance & Confort",
            ],
            "seasonal": {
                "spring": ["Rando Printemps", "Saison Vélo", "Running Extérieur"],
                "summer": ["Camping Sauvage", "Randonnée Montagne", "Baignade Lac"],
                "fall":   ["Trail Automnal", "Rando Champignons"],
                "winter": ["Ski Accessoires", "Raquettes Neige", "Veste Polaire"],
            },
        },

        "pet_supplies": {
            "occasions": [
                "Arrivée Chaton", "Promenade Quotidienne", "Voyage avec Animal",
                "Anniversaire Chien", "Toilettage Maison",
            ],
            "pain_points": [
                "Résistant aux Griffes", "Lavable en Machine", "Antidérapant",
                "Anti-Odeur", "Compact", "Certifié Sans Danger",
            ],
            "slang": [
                "Pour Mon Compagnon", "Bonheur Animal", "Accessoire Indispensable",
                "Qualité Préférence", "Confort Félin",
            ],
            "seasonal": {
                "spring": ["Brosse Anti-Poil", "Anti-Puces Printemps"],
                "summer": ["Tapis Rafraîchissant", "Gourde Voyage Animaux"],
                "fall":   ["Manteau Chien Automne", "Panier Douillet"],
                "winter": ["Cadeau Noël Animal", "Protection Pattes Neige"],
            },
        },

        "toys_kids_baby": {
            "occasions": [
                "Cadeau d'Anniversaire", "Noël Enfant", "Rentrée Scolaire",
                "Activité Mercredi", "Décoration Chambre Bébé", "Éveil Sensoriel",
            ],
            "pain_points": [
                "Sans BPA", "Normes CE", "Sans Danger",
                "Silencieux", "Lavable", "Bois Durable", "Éducatif Montessori",
            ],
            "slang": [
                "Apprendre en Jouant", "Fait Main", "Qualité Enfants",
                "Indispensable Crèche", "Jeu d'Éveil", "Créatif et Ludique",
            ],
            "seasonal": {
                "spring": ["Jeu d'Extérieur Printemps", "Chasse aux Œufs"],
                "summer": ["Jeu de Plage Enfant", "Jeu de Voyage Voiture"],
                "fall":   ["Rentrée Scolaire Cadeau", "Activité Intérieure"],
                "winter": ["Cadeau de Noël Enfant", "Jeu Calme Hiver"],
            },
        },

        "automotive": {
            "occasions": [
                "Départ en Vacances", "Trajet Quotidien", "Nettoyage Auto",
                "Préparation Hiver", "Nouvelle Voiture",
            ],
            "pain_points": [
                "Fixation Solide", "Sans Résidu", "Universel",
                "Anti-Rayures", "Résistant Chaleur", "Charge Rapide Voiture",
            ],
            "slang": [
                "Accessoire Indispensable", "Confort de Conduite", "Voiture Bien Équipée",
                "Pratique et Solide", "Qualité Pro",
            ],
            "seasonal": {
                "spring": ["Nettoyage Printemps Auto", "Tapis Toutes Saisons"],
                "summer": ["Pare-Soleil Voiture", "Glacière Voiture", "Support Téléphone Ventouse"],
                "fall":   ["Tapis Caoutchouc Pluie", "Nettoyage Intérieur"],
                "winter": ["Grattoir Givre", "Protection Siège Chauffante"],
            },
        },

        "office_stationery": {
            "occasions": [
                "Bureau à Domicile", "Fac Remise à Niveau", "Carnet de Notes",
                "Cadeau Professeur", "Coin Créatif", "Correspondance",
            ],
            "pain_points": [
                "Papier Épais", "Encre Qui Ne Bavent Pas", "Reliure Solide",
                "Stylo Confortable", "Rangement Modulable", "Esthétique Bureau",
            ],
            "slang": [
                "Belle Papeterie", "Organisation Parfaite", "Élégance Bureau",
                "Fait Main avec Soin", "Art de la Correspondance",
            ],
            "seasonal": {
                "spring": ["Nouvel Agenda", "Rangement Bureau Printemps"],
                "summer": ["Carnet de Voyage", "Aquarelle Été"],
                "fall":   ["Rentrée Papeterie", "Cadeau Maîtresse"],
                "winter": ["Cartes de Vœux", "Papier Cadeau Noël"],
            },
        },

    },

    # ────────────────────────────────────────
    # 🇪🇸 西班牙
    # ────────────────────────────────────────
    "ES": {

        "apparel": {
            "occasions": [
                "Boda de Verano", "Fiesta Nocturna", "Brunch de Domingo",
                "Look de Oficina", "Vacaciones en la Playa", "Cena con Amigos",
                "Tarde de Tapeo", "Paseo por la Ciudad",
            ],
            "pain_points": [
                "Reduce Vientre", "Tallas Grandes", "No Transparenta",
                "Fresco y Ligero", "No Se Arruga", "Tejido Natural",
                "Lavable a Máquina", "Hecho en España",
            ],
            "slang": [
                "Estilo Ibicenco", "Look Chic", "Cómodo y Elegante",
                "Favorecedor", "Hecho en España", "Estilo Mediterráneo",
                "Mono Ideal", "Vestido Comodín",
            ],
            "seasonal": {
                "spring": ["Look Primaveral", "Feria de Abril", "Estilo Flamenco"],
                "summer": ["Playa", "Chiringuito", "Vacaciones Costa"],
                "fall":   ["Look Otoñal", "Vuelta a la Oficina"],
                "winter": ["Cena de Navidad", "Nochevieja Brillante", "Rebajas Look"],
            },
            "search_prefix": "Mujer"
        },

        "bags_luggage": {
            "occasions": [
                "Escapada Fin de Semana", "Viaje de Negocios", "Universidad",
                "Vacaciones Verano", "Salida Nocturna", "Bolso de Playa",
            ],
            "pain_points": [
                "Medida Cabina", "Compartimento Portátil", "Ligera y Resistente",
                "Impermeable", "Cierre Seguro", "Piel Vegana",
            ],
            "slang": [
                "Bolso Todoterreno", "Práctico y Bonito", "Viaje Ligero",
                "Calidad-Precio Top", "Comodidad de Viaje",
            ],
            "seasonal": {
                "spring": ["Mochila Primavera", "Bolso Finde"],
                "summer": ["Bolso Playa Grande", "Maleta Verano Ligera"],
                "fall":   ["Bandolera Otoño", "Maleta Fin de Semana"],
                "winter": ["Bolso Navidad", "Maleta Ski"],
            },
        },

        "jewelry_watches": {
            "occasions": [
                "Regalo San Valentín", "Pedida de Mano", "Cumpleaños",
                "Joya Diaria", "Día de la Madre", "Comunión Invitada",
            ],
            "pain_points": [
                "Sin Níquel", "No Se Oxida", "Hipoalergénica",
                "Resistente al Agua", "Hecha a Mano", "Ajustable",
            ],
            "slang": [
                "Joya Minimalista", "Brillo Especial", "Artesanal",
                "Elegancia Discreta", "Toque Personal", "Para Toda la Vida",
            ],
            "seasonal": {
                "spring": ["Joya Primaveral", "Regalo Día de la Madre"],
                "summer": ["Pulsera Tobillo Playa", "Collar Veraniego"],
                "fall":   ["Tono Otoñal", "Reloj Clásico"],
                "winter": ["Regalo Navidad Joya", "Brillo Nochevieja"],
            },
        },

        "electronics": {
            "occasions": [
                "Teletrabajo", "Universidad", "Gym & Música",
                "Viaje en Coche", "Casa Conectada",
            ],
            "pain_points": [
                "Carga Rápida", "Batería Larga", "Resistente al Agua",
                "Anticaídas", "Compatibilidad Universal", "Calidad Sonido",
            ],
            "slang": [
                "Buena Relación Calidad-Precio", "Compacto Potente",
                "Imprescindible Diario", "Top Ventas",
            ],
            "seasonal": {
                "spring": ["Limpieza Tech", "Upgrade Gaming"],
                "summer": ["Altavoz Playa", "Gadgets Verano", "Auriculares Sumergibles"],
                "fall":   ["Vuelta al Cole Tech", "Esenciales Universidad"],
                "winter": ["Regalo Reyes Tech", "Rebajas Enero Tecnología"],
            },
        },

        "home_living": {
            "occasions": [
                "Regalo de Inauguración", "Decoración Hogar", "Terraza Chill",
                "Dormitorio Relax", "Salón Familiar",
            ],
            "pain_points": [
                "Pequeño Espacio", "Resistente", "Fácil Limpiar",
                "Sin Taladro", "Natural", "Plegable",
            ],
            "slang": [
                "Estilo Mediterráneo", "Minimalista Cálido", "Hogar con Alma",
                "Rincón Especial", "Decoración Bonita",
            ],
            "seasonal": {
                "spring": ["Limpieza Primavera Hogar", "Terraza y Jardín"],
                "summer": ["Barbacoa Decoración", "Chill Out Terraza"],
                "fall":   ["Decoración Otoñal", "Vuelta al Hogar"],
                "winter": ["Decoración Navideña", "Nochebuena Mesa"],
            },
        },

        "kitchen_dining": {
            "occasions": [
                "Comida Familiar", "Cena con Amigos", "Desayuno Tranquilo",
                "Tapas en Casa", "Barbacoa Domingo", "Cocina Diaria",
            ],
            "pain_points": [
                "Apto Lavavajillas", "Antiadherente Real", "Apilable",
                "Compatible Inducción", "Sin Tóxicos", "Fácil Agarre",
            ],
            "slang": [
                "Imprescindible Cocina", "Arte de Cocinar", "Mesa Bonita",
                "Hecho para Durar", "Calidad de Chef",
            ],
            "seasonal": {
                "spring": ["Vajilla Primavera", "Accesorios Terraza"],
                "summer": ["Parrilla Barbacoa", "Vasos Tinto Verano", "Gazpacho Set"],
                "fall":   ["Cazuela Barro", "Set Cocido"],
                "winter": ["Chocolatera Invierno", "Turrón Set Navidad"],
            },
        },

        "beauty_personal": {
            "occasions": [
                "Rutina Diaria", "Cuidado Facial", "Maquillaje Fiesta",
                "Spa en Casa", "Cuidado Capilar",
            ],
            "pain_points": [
                "Piel Sensible", "Antiedad", "Protección Solar",
                "Ingredientes Naturales", "Sin Parabenos", "No Testado en Animales",
            ],
            "slang": [
                "Cosmética Natural", "Farmacia Calidad", "Lujo Asequible",
                "Piel Radiante", "Belleza Mediterránea", "Esencial Diario",
            ],
            "seasonal": {
                "spring": ["Cuidado Primaveral", "Renovación Piel", "Protección Solar Ligera"],
                "summer": ["Protección Solar SPF50", "After Sun Refrescante", "Textura Gel"],
                "fall":   ["Reparación Otoñal", "Hidratación Profunda"],
                "winter": ["Protección Frío", "Crema Manos Intensiva", "Bálsamo Labios"],
            },
        },

        "sports_outdoor": {
            "occasions": [
                "Senderismo Montaña", "Correr al Aire Libre", "Gimnasio Diario",
                "Acampada Fin de Semana", "Ciclismo Ruta", "Yoga en Casa",
            ],
            "pain_points": [
                "Antideslizante", "Transpirable", "Compacto",
                "Resistente Agua", "Ligero", "Acolchado Cómodo",
            ],
            "slang": [
                "Listo para Aventura", "Aire Libre Calidad", "Esencial Deporte",
                "Confort y Rendimiento", "Senderista Feliz",
            ],
            "seasonal": {
                "spring": ["Ruta Primavera", "Ciclismo Temporada"],
                "summer": ["Acampada Playa", "Senderismo Verano"],
                "fall":   ["Trail Otoño", "Running Fresco"],
                "winter": ["Esquí Accesorio", "Ropa Térmica Montaña"],
            },
        },

        "pet_supplies": {
            "occasions": [
                "Llegada Cachorro", "Paseo Diario", "Viaje con Mascota",
                "Cumple Perruno", "Mimos en Casa",
            ],
            "pain_points": [
                "Resistente Mordiscos", "Lavable", "Antideslizante",
                "Antiolor", "Seguro", "Compacto",
            ],
            "slang": [
                "Para Mi Compañero", "Calidad Perruna", "Accesorio Imprescindible",
                "Mascota Feliz", "Práctico y Bonito",
            ],
            "seasonal": {
                "spring": ["Cepillo Muda", "Antipulgas"],
                "summer": ["Colchoneta Fresca", "Bebedero Viaje"],
                "fall":   ["Abrigo Perro Ligero", "Cama Otoño"],
                "winter": ["Regalo Navidad Mascota", "Protección Patitas Nieve"],
            },
        },

        "toys_kids_baby": {
            "occasions": [
                "Regalo Cumpleaños", "Reyes Magos", "Vuelta al Cole",
                "Tarde de Juegos", "Decoración Habitación Bebé", "Estimulación Temprana",
            ],
            "pain_points": [
                "Sin BPA", "Certificado CE", "Seguro",
                "Silencioso", "Lavable", "Educativo", "Madera Sostenible",
            ],
            "slang": [
                "Aprender Jugando", "Hecho con Cariño", "Calidad Infantil",
                "Juego Creativo", "Ideal para Peques",
            ],
            "seasonal": {
                "spring": ["Juego Parque", "Pascua Infantil"],
                "summer": ["Juguete Piscina", "Juego Viaje Coche"],
                "fall":   ["Vuelta al Cole Regalo", "Manualidades Otoño"],
                "winter": ["Regalo Reyes", "Juego Interior"],
            },
        },

        "automotive": {
            "occasions": [
                "Viaje Carretera", "Trayecto Diario", "Limpieza Coche",
                "Preparación Invierno", "Coche Nuevo",
            ],
            "pain_points": [
                "Sujeción Firme", "Sin Residuos", "Universal",
                "Antirrayas", "Resistente Calor", "Carga Rápida Coche",
            ],
            "slang": [
                "Accesorio Coche Top", "Viaje Cómodo", "Conducción Placentera",
                "Práctico y Seguro", "Calidad Garantizada",
            ],
            "seasonal": {
                "spring": ["Limpieza Primavera Coche", "Ambientador Natural"],
                "summer": ["Parasol Coche", "Nevera Portátil Coche"],
                "fall":   ["Alfombrilla Lluvia", "Limpiaparabrisas Nuevo"],
                "winter": ["Rascador Hielo", "Manta Coche"],
            },
        },

        "office_stationery": {
            "occasions": [
                "Oficina en Casa", "Vuelta a la Universidad", "Agenda Nueva",
                "Regalo Profe", "Rincón Creativo",
            ],
            "pain_points": [
                "Papel Grueso", "Tinta No Traspasa", "Encuadernación Firme",
                "Bolígrafo Cómodo", "Organizador Modular", "Bonito Escritorio",
            ],
            "slang": [
                "Papelería Bonita", "Organización Perfecta", "Escritorio Chic",
                "Artesanía con Estilo", "Material de Calidad",
            ],
            "seasonal": {
                "spring": ["Agenda Nueva Primavera", "Orden Escritorio"],
                "summer": ["Cuaderno Viaje", "Acuarelas Verano"],
                "fall":   ["Vuelta al Cole Material", "Regalo Maestro"],
                "winter": ["Postales Navideñas", "Papel Regalo Bonito"],
            },
        },

    },

    # ────────────────────────────────────────
    # 🇮🇹 意大利
    # ────────────────────────────────────────
    "IT": {

        "apparel": {
            "occasions": [
                "Matrimonio Estivo", "Aperitivo Serale", "Cena Elegante",
                "Look da Ufficio", "Vacanze al Mare", "Passeggiata in Centro",
                "Festa di Compleanno", "Serata Teatro",
            ],
            "pain_points": [
                "Effetto Pancia Piatta", "Taglie Comode", "Non Si Vede Sotto",
                "Tessuto Fresco", "Antipiega", "Lavabile in Lavatrice",
                "Made in Italy", "Tessuto Naturale",
            ],
            "slang": [
                "Stile Italiano", "Chic e Comodo", "Eleganza Senza Tempo",
                "Taglio Perfetto", "Fatto a Mano", "Qualità Sartoriale",
                "Look Impeccabile", "Versatile ed Elegante",
            ],
            "seasonal": {
                "spring": ["Look Primaverile", "Pasqua Elegante"],
                "summer": ["Mare", "Costiera Amalfitana", "Ferragosto Look"],
                "fall":   ["Look Autunnale", "Vendemmia Stile"],
                "winter": ["Cena di Natale", "Capodanno Chic", "Settimana Bianca Moda"],
            },
            "search_prefix": "Donna"
        },

        "bags_luggage": {
            "occasions": [
                "Weekend Fuori Porta", "Viaggio di Lavoro", "Lezioni Università",
                "Vacanze Estive", "Aperitivo Serale", "Borsa Mare",
            ],
            "pain_points": [
                "Misure Cabina", "Tasca Portatile", "Leggera e Robusta",
                "Impermeabile", "Chiusura Sicura", "Pelle Italiana",
            ],
            "slang": [
                "Borsa Perfetta", "Pratica ed Elegante", "Compagna di Viaggio",
                "Qualità Artigianale", "Design Funzionale",
            ],
            "seasonal": {
                "spring": ["Zaino Primavera", "Borsa Weekend"],
                "summer": ["Borsa Mare Grande", "Valigia Estate Leggera"],
                "fall":   ["Tracolla Autunno", "Valigia Cabina"],
                "winter": ["Borsa Regalo Natale", "Borsa Sci"],
            },
        },

        "jewelry_watches": {
            "occasions": [
                "Regalo San Valentino", "Anniversario Matrimonio", "Compleanno",
                "Gioiello Quotidiano", "Festa della Mamma", "Cresima Regalo",
            ],
            "pain_points": [
                "Senza Nichel", "Non Annerisce", "Ipoallergenico",
                "Resistente Acqua", "Fatto a Mano Italia", "Regolabile",
            ],
            "slang": [
                "Gioiello Minimal", "Eleganza Italiana", "Fatto con Amore",
                "Pezzo Unico", "Raffinato e Delicato",
            ],
            "seasonal": {
                "spring": ["Gioiello Primaverile", "Regalo Mamma"],
                "summer": ["Cavigliera Mare", "Collana Estate Leggera"],
                "fall":   ["Toni Autunnali Gioiello", "Orologio Classico"],
                "winter": ["Regalo Natale Gioiello", "Brillantezza Capodanno"],
            },
        },

        "electronics": {
            "occasions": [
                "Smart Working", "Università", "Palestra & Musica",
                "Viaggio in Auto", "Casa Domotica",
            ],
            "pain_points": [
                "Ricarica Rapida", "Batteria Duratura", "Cancellazione Rumore",
                "Impermeabile IPX", "Anti-Caduta", "Qualità Audio",
            ],
            "slang": [
                "Ottimo Rapporto Qualità-Prezzo", "Compatto Potente",
                "Indispensabile Quotidiano", "Design Elegante",
            ],
            "seasonal": {
                "spring": ["Upgrade Tecnologico", "Pulizie Primavera Tech"],
                "summer": ["Casse Bluetooth Spiaggia", "Gadget Vacanze"],
                "fall":   ["Rientro Universitario Tech", "Essenziali Studio"],
                "winter": ["Regalo di Natale Tech", "Saldi Invernali Tecnologia"],
            },
        },

        "home_living": {
            "occasions": [
                "Regalo per la Casa", "Arredamento Appartamento", "Terrazzo Vista",
                "Camera da Letto Relax", "Salotto Accogliente",
            ],
            "pain_points": [
                "Piccoli Spazi", "Design Salvaspazio", "Facile Pulire",
                "Senza Trapano", "Materiale Naturale", "Pieghevole",
            ],
            "slang": [
                "Design Italiano", "Stile Minimal Caldo", "Casa con Anima",
                "Arredamento di Gusto", "Atmosfera Accogliente",
            ],
            "seasonal": {
                "spring": ["Pulizie Primavera Casa", "Giardinaggio Balcone"],
                "summer": ["Grigliata Terrazzo", "Arredamento Esterno"],
                "fall":   ["Decorazione Autunnale", "Casa Accogliente"],
                "winter": ["Decorazione Natalizia", "Natale in Casa Calda"],
            },
        },

        "kitchen_dining": {
            "occasions": [
                "Pranzo della Domenica", "Cena tra Amici", "Colazione Lenta",
                "Aperitivo in Casa", "Cucina Quotidiana", "Dolci Fatti in Casa",
            ],
            "pain_points": [
                "Lavabile in Lavastoviglie", "Antiadrente Professionale", "Impilabile",
                "Adatto Induzione", "Senza Sostanze Nocive", "Impugnatura Comoda",
            ],
            "slang": [
                "Essenziale in Cucina", "Qualità da Chef", "Tavola Bella",
                "Fatto per Durare", "Stile Italiano ai Fornelli",
            ],
            "seasonal": {
                "spring": ["Piatti Pasquali", "Servizio Colazione"],
                "summer": ["Griglia Barbecue", "Bicchieri Aperitivo"],
                "fall":   ["Pentola Ragù", "Tegame Funghi"],
                "winter": ["Set Cioccolata Calda", "Servizio Panettone"],
            },
        },

        "beauty_personal": {
            "occasions": [
                "Routine Bellezza Quotidiana", "Trattamento Viso", "Trucco Serata",
                "Benessere a Casa", "Cura Capelli",
            ],
            "pain_points": [
                "Pelle Sensibile", "Antirughe", "Ingredienti Naturali",
                "Senza Parabeni", "Non Testato Animali", "Dermatologicamente Testato",
                "Made in Italy", "Profumazione Delicata",
            ],
            "slang": [
                "Bellezza Italiana", "Farmacia Qualità", "Lusso Accessibile",
                "Pelle Perfetta", "Benessere Naturale",
            ],
            "seasonal": {
                "spring": ["Cura Primaverile", "Pelle Luminosa", "Detersione Delicata"],
                "summer": ["Protezione Solare SPF50", "Doposole Lenitivo"],
                "fall":   ["Riparazione Autunnale", "Idratazione Intensa"],
                "winter": ["Protezione Inverno", "Mani Secche Cura Intensiva"],
            },
        },

        "sports_outdoor": {
            "occasions": [
                "Trekking Montagna", "Corsa Mattutina", "Palestra Serale",
                "Campeggio Weekend", "Ciclismo Strada", "Yoga Mattino",
            ],
            "pain_points": [
                "Antiscivolo", "Traspirante", "Compatto",
                "Impermeabile", "Leggero", "Imbottitura Comfort",
            ],
            "slang": [
                "Pronto per Avventura", "Sport e Natura", "Accessorio Fidato",
                "Qualità Outdoor", "Performance & Stile",
            ],
            "seasonal": {
                "spring": ["Sentiero Primavera", "Stagione Bici"],
                "summer": ["Campeggio Mare", "Trekking Estate"],
                "fall":   ["Trail Autunno", "Corsa Fresca"],
                "winter": ["Accessori Sci", "Abbigliamento Termico Montagna"],
            },
        },

        "pet_supplies": {
            "occasions": [
                "Arrivo Cucciolo", "Passeggiata Giornaliera", "Viaggio con Pet",
                "Compleanno Cane", "Coccole a Casa",
            ],
            "pain_points": [
                "Resistente Morsi", "Lavabile", "Antiscivolo",
                "Anti-Odore", "Sicuro", "Design Compatto",
            ],
            "slang": [
                "Per il Mio Amico", "Qualità Animale", "Accessorio Irrinunciabile",
                "Pratico e Bello", "Felicità a Quattro Zampe",
            ],
            "seasonal": {
                "spring": ["Spazzola Muta", "Antiparassitario"],
                "summer": ["Tappetino Rinfrescante", "Boraccia Viaggio"],
                "fall":   ["Cappottino Leggero", "Cuccia Autunno"],
                "winter": ["Regalo Natale Pet", "Protezione Zampette Neve"],
            },
        },

        "toys_kids_baby": {
            "occasions": [
                "Regalo Compleanno", "Natale Bambini", "Rientro a Scuola",
                "Pomeriggio Giochi", "Cametta Neonato", "Apprendimento Precoce",
            ],
            "pain_points": [
                "Senza BPA", "Certificato CE", "Sicuro",
                "Silenzioso", "Lavabile", "Educativo Montessori", "Legno Sostenibile",
            ],
            "slang": [
                "Imparare Giocando", "Fatto con Amore", "Qualità Per Bambini",
                "Creativo e Divertente", "Essenziale Infanzia",
            ],
            "seasonal": {
                "spring": ["Gioco Parco", "Pasqua Bambini"],
                "summer": ["Giochi Mare", "Gioco Viaggio Auto"],
                "fall":   ["Rientro Scuola Regalo", "Lavoretti Autunnali"],
                "winter": ["Regalo di Natale", "Gioco da Interno"],
            },
        },

        "automotive": {
            "occasions": [
                "Viaggio in Auto", "Tragitto Quotidiano", "Pulizia Auto",
                "Preparazione Invernale", "Auto Nuova Accessori",
            ],
            "pain_points": [
                "Fissaggio Saldo", "Senza Residui", "Universale",
                "Antigraffio", "Resistente Calore", "Ricarica Rapida Auto",
            ],
            "slang": [
                "Accessorio Auto Indispensabile", "Guida Comfort", "Qualità Garantita",
                "Pratico e Affidabile", "Stile Italiano in Auto",
            ],
            "seasonal": {
                "spring": ["Pulizia Primavera Auto", "Profumatore Naturale"],
                "summer": ["Tendina Parasole", "Frigo Portatile Auto"],
                "fall":   ["Tappetino Pioggia", "Pulizia Interni"],
                "winter": ["Raschietto Ghiaccio", "Coprisedile Riscaldante"],
            },
        },

        "office_stationery": {
            "occasions": [
                "Ufficio in Casa", "Università Iscrizione", "Agenda Nuova",
                "Regalo Insegnante", "Angolo Creativo",
            ],
            "pain_points": [
                "Carta Spessa", "Inchiostro Non Sbava", "Rilegatura Robusta",
                "Penna Comoda", "Organizer Modulare", "Bella Scrivania",
            ],
            "slang": [
                "Cancelleria Bella", "Organizzazione Perfetta", "Scrivania Chic",
                "Artigianato di Qualità", "Stile Italiano in Ufficio",
            ],
            "seasonal": {
                "spring": ["Agenda Nuova Primavera", "Ordine Scrivania"],
                "summer": ["Quaderno Viaggio", "Acquerelli Estate"],
                "fall":   ["Rientro Scuola Cancelleria", "Regalo Maestra"],
                "winter": ["Biglietti Natalizi", "Carta Regalo Bella"],
            },
        },

    },

}


# ═══════════════════════════════════════════════════════════════
# 全量中文关键词 → 品类 key 映射（1688 跨境卖家真实筛选）
# ═══════════════════════════════════════════════════════════════

CATEGORY_TO_CULTURAL_KEY: dict[str, str] = {

    # ── 01 apparel 服装鞋帽配饰（非珠宝非包） ──
    "t恤": "apparel", "T恤": "apparel", "衬衫": "apparel", "连衣裙": "apparel",
    "裙子": "apparel", "半身裙": "apparel", "外套": "apparel", "羽绒服": "apparel",
    "裤子": "apparel", "短裤": "apparel", "牛仔裤": "apparel", "卫衣": "apparel",
    "毛衣": "apparel", "风衣": "apparel", "西服": "apparel", "西装": "apparel",
    "泳衣": "apparel", "睡衣": "apparel", "内衣": "apparel", "文胸": "apparel",
    "袜子": "apparel", "围巾": "apparel", "帽子": "apparel", "手套": "apparel",
    "运动服": "apparel", "瑜伽服": "apparel", "健身服": "apparel",
    "鞋": "apparel", "运动鞋": "apparel", "靴子": "apparel", "凉鞋": "apparel",
    "高跟鞋": "apparel", "拖鞋": "apparel", "帆布鞋": "apparel", "篮球鞋": "apparel",
    "跑步鞋": "apparel", "皮鞋": "apparel", "布鞋": "apparel", "雪地靴": "apparel",
    "短靴": "apparel", "长靴": "apparel", "家居服": "apparel", "浴袍": "apparel",
    "打底衫": "apparel", "马甲": "apparel", "背心": "apparel", "吊带": "apparel",
    "polo": "apparel", "POLO": "apparel", "夹克": "apparel", "棉衣": "apparel",
    "棉服": "apparel", "雪纺": "apparel", "蕾丝": "apparel", "针织": "apparel",
    "雪纺衫": "apparel", "民族风": "apparel", "汉服": "apparel",

    # ── 02 bags_luggage 箱包 ──
    "包": "bags_luggage", "手提包": "bags_luggage", "背包": "bags_luggage",
    "钱包": "bags_luggage", "行李": "bags_luggage", "行李箱": "bags_luggage",
    "双肩包": "bags_luggage", "单肩包": "bags_luggage", "斜挎包": "bags_luggage",
    "腰包": "bags_luggage", "卡包": "bags_luggage", "化妆包": "bags_luggage",
    "电脑包": "bags_luggage", "公文包": "bags_luggage", "旅行包": "bags_luggage",
    "书包": "bags_luggage", "帆布包": "bags_luggage", "托特包": "bags_luggage",
    "链条包": "bags_luggage", "胸包": "bags_luggage", "妈咪包": "bags_luggage",
    "洗漱包": "bags_luggage", "登机": "bags_luggage",

    # ── 03 jewelry_watches 珠宝手表发饰 ──
    "项链": "jewelry_watches", "戒指": "jewelry_watches", "耳环": "jewelry_watches",
    "手链": "jewelry_watches", "手镯": "jewelry_watches", "发饰": "jewelry_watches",
    "发夹": "jewelry_watches", "发箍": "jewelry_watches", "发圈": "jewelry_watches",
    "手表": "jewelry_watches", "墨镜": "jewelry_watches", "太阳镜": "jewelry_watches",
    "珠宝": "jewelry_watches", "饰品": "jewelry_watches", "首饰": "jewelry_watches",
    "胸针": "jewelry_watches", "袖扣": "jewelry_watches", "脚链": "jewelry_watches",
    "吊坠": "jewelry_watches", "串珠": "jewelry_watches", "钛钢": "jewelry_watches",
    "银饰": "jewelry_watches", "18k": "jewelry_watches", "镀金": "jewelry_watches",
    "珍珠": "jewelry_watches", "耳钉": "jewelry_watches", "锁骨链": "jewelry_watches",

    # ── 04 electronics 3C 数码 ──
    "手机壳": "electronics", "手机支架": "electronics", "充电器": "electronics",
    "数据线": "electronics", "耳机": "electronics", "蓝牙耳机": "electronics",
    "音箱": "electronics", "智能手表": "electronics", "平板": "electronics",
    "电脑": "electronics", "键盘": "electronics", "鼠标": "electronics",
    "摄像头": "electronics", "相机": "electronics", "投影仪": "electronics",
    "3c": "electronics", "数码": "electronics", "充电宝": "electronics",
    "自拍杆": "electronics", "贴膜": "electronics", "屏幕保护": "electronics",
    "转换头": "electronics", "转换器": "electronics", "读卡器": "electronics",
    "存储卡": "electronics", "u盘": "electronics", "U盘": "electronics",
    "硬盘": "electronics", "路由器": "electronics", "电源": "electronics",
    "充电头": "electronics", "无线充电": "electronics", "蓝牙": "electronics",
    "手环": "electronics", "智能手环": "electronics", "运动相机": "electronics",
    "录音笔": "electronics", "翻译机": "electronics", "麦克风": "electronics",

    # ── 05 home_living 家居生活 ──
    "台灯": "home_living", "灯具": "home_living", "窗帘": "home_living",
    "地毯": "home_living", "地垫": "home_living", "门垫": "home_living",
    "收纳": "home_living", "收纳箱": "home_living", "衣架": "home_living",
    "沙发": "home_living", "桌子": "home_living", "椅子": "home_living",
    "花盆": "home_living", "花瓶": "home_living", "墙贴": "home_living",
    "相框": "home_living", "挂画": "home_living", "香薰": "home_living",
    "蜡烛": "home_living", "床上用品": "home_living", "枕头": "home_living",
    "被子": "home_living", "床单": "home_living", "四件套": "home_living",
    "蚊帐": "home_living", "挂钟": "home_living", "时钟": "home_living",
    "镜子": "home_living", "置物架": "home_living", "鞋架": "home_living",
    "书架": "home_living", "衣柜": "home_living", "鞋柜": "home_living",
    "抽屉": "home_living", "挂钩": "home_living", "粘钩": "home_living",
    "浴室": "home_living", "毛巾": "home_living", "浴巾": "home_living",
    "浴帘": "home_living", "皂盒": "home_living", "牙刷架": "home_living",
    "纸巾盒": "home_living", "垃圾桶": "home_living", "抱枕": "home_living",
    "靠垫": "home_living", "沙发套": "home_living", "桌布": "home_living",
    "餐垫": "home_living", "照片墙": "home_living",

    # ── 06 kitchen_dining 厨房餐饮 ──
    "杯子": "kitchen_dining", "咖啡杯": "kitchen_dining", "马克杯": "kitchen_dining",
    "水壶": "kitchen_dining", "保温杯": "kitchen_dining", "饭盒": "kitchen_dining",
    "便当": "kitchen_dining", "保鲜盒": "kitchen_dining", "碗": "kitchen_dining",
    "盘": "kitchen_dining", "筷子": "kitchen_dining", "刀叉": "kitchen_dining",
    "勺子": "kitchen_dining", "锅": "kitchen_dining", "炒锅": "kitchen_dining",
    "不粘锅": "kitchen_dining", "汤锅": "kitchen_dining", "蒸锅": "kitchen_dining",
    "平底锅": "kitchen_dining", "铲": "kitchen_dining", "刀具": "kitchen_dining",
    "切菜": "kitchen_dining", "砧板": "kitchen_dining", "菜板": "kitchen_dining",
    "烤箱": "kitchen_dining", "烘焙": "kitchen_dining", "烤盘": "kitchen_dining",
    "烤架": "kitchen_dining", "硅胶": "kitchen_dining", "调料": "kitchen_dining",
    "调味": "kitchen_dining", "油壶": "kitchen_dining", "密封罐": "kitchen_dining",
    "开瓶器": "kitchen_dining", "榨汁": "kitchen_dining", "搅拌": "kitchen_dining",
    "打蛋器": "kitchen_dining", "量杯": "kitchen_dining", "围裙": "kitchen_dining",
    "酒具": "kitchen_dining", "茶具": "kitchen_dining", "咖啡": "kitchen_dining",
    "餐盒": "kitchen_dining",

    # ── 07 beauty_personal 美妆个护 ──
    "精华": "beauty_personal", "面膜": "beauty_personal", "护肤品": "beauty_personal",
    "化妆刷": "beauty_personal", "口红": "beauty_personal", "粉底": "beauty_personal",
    "眼影": "beauty_personal", "洗发水": "beauty_personal", "香水": "beauty_personal",
    "美甲": "beauty_personal", "面霜": "beauty_personal", "乳液": "beauty_personal",
    "眼霜": "beauty_personal", "爽肤水": "beauty_personal", "洁面": "beauty_personal",
    "卸妆": "beauty_personal", "防晒": "beauty_personal", "隔离": "beauty_personal",
    "bb": "beauty_personal", "BB": "beauty_personal", "cc": "beauty_personal",
    "眉笔": "beauty_personal", "眼线": "beauty_personal", "睫毛": "beauty_personal",
    "腮红": "beauty_personal", "高光": "beauty_personal", "修容": "beauty_personal",
    "散粉": "beauty_personal", "气垫": "beauty_personal", "沐浴": "beauty_personal",
    "身体乳": "beauty_personal", "手霜": "beauty_personal", "护手": "beauty_personal",
    "唇膏": "beauty_personal", "润唇": "beauty_personal", "护发": "beauty_personal",
    "发膜": "beauty_personal", "精油": "beauty_personal", "洗脸": "beauty_personal",
    "美容仪": "beauty_personal", "脱毛": "beauty_personal", "剃须": "beauty_personal",
    "指甲": "beauty_personal", "指甲油": "beauty_personal", "甲油胶": "beauty_personal",
    "化妆镜": "beauty_personal", "粉扑": "beauty_personal", "美妆蛋": "beauty_personal",
    "沐浴露": "beauty_personal", "洗发": "beauty_personal",

    # ── 08 sports_outdoor 运动户外 ──
    "运动": "sports_outdoor", "瑜伽": "sports_outdoor", "户外": "sports_outdoor",
    "露营": "sports_outdoor", "帐篷": "sports_outdoor", "登山": "sports_outdoor",
    "徒步": "sports_outdoor", "骑行": "sports_outdoor", "跑步": "sports_outdoor",
    "健身": "sports_outdoor", "钓鱼": "sports_outdoor", "渔具": "sports_outdoor",
    "游泳": "sports_outdoor", "滑雪": "sports_outdoor", "滑板": "sports_outdoor",
    "跳绳": "sports_outdoor", "哑铃": "sports_outdoor", "护膝": "sports_outdoor",
    "护腕": "sports_outdoor", "球类": "sports_outdoor", "乒乓球": "sports_outdoor",
    "羽毛球": "sports_outdoor", "网球": "sports_outdoor", "篮球": "sports_outdoor",
    "足球": "sports_outdoor", "排球": "sports_outdoor", "防潮垫": "sports_outdoor",
    "睡袋": "sports_outdoor", "头灯": "sports_outdoor", "手电": "sports_outdoor",
    "手电筒": "sports_outdoor", "登山杖": "sports_outdoor", "望远镜": "sports_outdoor",
    "指南针": "sports_outdoor", "野餐": "sports_outdoor", "烧烤": "sports_outdoor",
    "冲浪": "sports_outdoor", "潜水": "sports_outdoor", "攀岩": "sports_outdoor",
    "拳击": "sports_outdoor", "高尔夫": "sports_outdoor", "锻炼": "sports_outdoor",

    # ── 09 pet_supplies 宠物用品 ──
    "宠物": "pet_supplies", "猫": "pet_supplies", "狗": "pet_supplies",
    "猫窝": "pet_supplies", "狗窝": "pet_supplies", "猫砂": "pet_supplies",
    "猫砂盆": "pet_supplies", "食盆": "pet_supplies", "饮水机": "pet_supplies",
    "项圈": "pet_supplies", "牵引绳": "pet_supplies", "胸背": "pet_supplies",
    "逗猫": "pet_supplies", "磨牙": "pet_supplies", "零食": "pet_supplies",
    "罐头": "pet_supplies", "剃毛": "pet_supplies", "梳子": "pet_supplies",
    "指甲剪": "pet_supplies", "尿垫": "pet_supplies", "笼子": "pet_supplies",
    "航空箱": "pet_supplies", "狗绳": "pet_supplies", "猫抓板": "pet_supplies",
    "猫爬架": "pet_supplies", "狗狗": "pet_supplies",

    # ── 10 toys_kids_baby 玩具母婴儿童 ──
    "玩具": "toys_kids_baby", "积木": "toys_kids_baby", "拼图": "toys_kids_baby",
    "遥控": "toys_kids_baby", "娃娃": "toys_kids_baby", "模型": "toys_kids_baby",
    "乐高": "toys_kids_baby", "变形": "toys_kids_baby", "奥特曼": "toys_kids_baby",
    "恐龙": "toys_kids_baby", "儿童": "toys_kids_baby", "婴儿": "toys_kids_baby",
    "宝宝": "toys_kids_baby", "奶瓶": "toys_kids_baby", "奶粉": "toys_kids_baby",
    "尿布": "toys_kids_baby", "推车": "toys_kids_baby", "安全座椅": "toys_kids_baby",
    "餐椅": "toys_kids_baby", "围栏": "toys_kids_baby", "爬行": "toys_kids_baby",
    "早教": "toys_kids_baby", "文具": "toys_kids_baby", "铅笔": "toys_kids_baby",
    "橡皮": "toys_kids_baby", "尺子": "toys_kids_baby", "本子": "toys_kids_baby",
    "文具盒": "toys_kids_baby", "彩笔": "toys_kids_baby", "水彩": "toys_kids_baby",
    "画板": "toys_kids_baby", "橡皮泥": "toys_kids_baby", "黏土": "toys_kids_baby",
    "泡泡": "toys_kids_baby", "书包": "toys_kids_baby", "母婴": "toys_kids_baby",
    "孕": "toys_kids_baby", "新生儿": "toys_kids_baby", "益智": "toys_kids_baby",
    "毛绒": "toys_kids_baby", "玩偶": "toys_kids_baby",

    # ── 11 automotive 汽车配件 ──
    "汽车": "automotive", "车载": "automotive", "坐垫": "automotive",
    "座套": "automotive", "脚垫": "automotive", "方向盘": "automotive",
    "车充": "automotive", "行车记录仪": "automotive", "倒车": "automotive",
    "清洁": "automotive", "洗车": "automotive", "蜡": "automotive",
    "摆件": "automotive", "遮阳": "automotive", "钥匙套": "automotive",
    "车贴": "automotive", "反光": "automotive", "安全锤": "automotive",
    "车载支架": "automotive", "车载充电": "automotive",

    # ── 12 office_stationery 办公文具 ──
    "办公": "office_stationery", "文件": "office_stationery", "文件夹": "office_stationery",
    "桌面": "office_stationery", "订书机": "office_stationery", "胶带": "office_stationery",
    "便签": "office_stationery", "计算器": "office_stationery", "印章": "office_stationery",
    "标签": "office_stationery", "打印": "office_stationery", "白板": "office_stationery",
    "黑板": "office_stationery", "画架": "office_stationery", "绘画": "office_stationery",
    "颜料": "office_stationery", "笔记本": "office_stationery", "笔": "office_stationery",

    # 兜底
    "default": "home_living",
}


# ═══════════════════════════════════════════════════════════════
# L1 解析引擎 — GPC 最长匹配优先 + 中文关键词兜底
# ═══════════════════════════════════════════════════════════════

def resolve_category_by_gpc(gpc_path: str) -> Optional[str]:
    """纯 GPC 路径 → 12 品类 key。

    策略：将 "Apparel & Accessories > Clothing > Dresses" 拆成段，
    对每段做最长关键词匹配。最长匹配优先，消除 "Game" 的歧义：
    "Video Game Console" → match "video game"(len=10) → electronics，
    而非 match "game"(len=4) → toys_kids_baby。
    """
    if not gpc_path:
        return None

    segments = [s.strip().lower() for s in gpc_path.split(">")]
    best_len = 0
    best_cat = None

    for segment in segments:
        for keywords, cat_key in GPC_SEGMENT_RULES:
            for kw in sorted(keywords, key=len, reverse=True):
                if kw in segment:
                    if len(kw) > best_len:
                        best_len = len(kw)
                        best_cat = cat_key
                    break

    return best_cat


def _resolve_by_keywords(cn_category: str) -> Optional[str]:
    """中文关键词 → 品类 key（1688 特化兜底）

    关键规则：具体词优先于通配词。"跑步鞋" 应命中 sports_outdoor 而非 apparel（避免被 "鞋" 通配）。
    """
    if not cn_category:
        return None
    cn_lower = cn_category.lower().strip()

    # ── 优先精确匹配（存在歧义的长词，放在通配映射之前） ──
    _specific_overrides = {
        "跑步鞋": "sports_outdoor", "运动鞋": "sports_outdoor",
        "篮球鞋": "sports_outdoor", "足球鞋": "sports_outdoor",
        "登山鞋": "sports_outdoor", "徒步鞋": "sports_outdoor",
        "训练鞋": "sports_outdoor", "跑鞋": "sports_outdoor",
        "健步鞋": "sports_outdoor", "户外鞋": "sports_outdoor",
        "瑜伽": "sports_outdoor", "健身": "sports_outdoor",
        "运动": "sports_outdoor",
        "上衣": "apparel", "卫衣": "apparel",
        # guess_category_from_title 产出的中文品类字面值 → cultural_key
        "美容个护": "beauty_personal", "护肤品": "beauty_personal", "彩妆": "beauty_personal",
        "珠宝饰品": "jewelry_watches",
        "母婴玩具": "toys_kids_baby", "母婴": "toys_kids_baby",
        "宠物用品": "pet_supplies",
        "厨房餐饮": "kitchen_dining",
        "办公文具": "office_stationery",
        "服装鞋帽": "apparel",
        "箱包": "bags_luggage",
        "运动户外": "sports_outdoor",
        "家居生活": "home_living",
        "3C数码": "electronics",
        "汽车用品": "automotive",
    }
    for keyphrase, cultural_key in _specific_overrides.items():
        if keyphrase and keyphrase in cn_lower:
            return cultural_key

    for keyphrase, cultural_key in CATEGORY_TO_CULTURAL_KEY.items():
        if keyphrase and keyphrase in cn_lower:
            return cultural_key
    return None


def resolve_category(cn_category: str = "", gpc_path: str = "") -> str:
    """品类解析主入口：GPC 优先 → 中文关键词兜底 → home_living"""

    # L1: GPC 万类目全覆盖（Google Taxonomy 6000+ 类目）
    if gpc_path:
        cat_key = resolve_category_by_gpc(gpc_path)
        if cat_key:
            return cat_key

    # L2: 中文关键词兜底（1688 卖家真实筛选词）
    cat_key = _resolve_by_keywords(cn_category)
    if cat_key:
        return cat_key

    return "home_living"


# ═══════════════════════════════════════════════════════════════
# L0 标题关键词推断品类（代发卖家无分类/无 GPC 时的兜底）
# ═══════════════════════════════════════════════════════════════

# 标题 → 中文品类字面值（非 cultural_key，后者由 resolve_category 内部 L2 做）
_TITLE_CATEGORY_HINTS: list[tuple[list[str], str]] = [
    # 优先级从高到低排列 — 具体词在前，通配词在后
    # 英文服饰（Shopify 标题常见）
    (["jeans", "denim", "dress", "dresses", "skirt", "socks", "sock",
      "t-shirt", "tshirt", "blouse", "hoodie", "sweater", "cardigan",
      "legging", "jumpsuit", "romper", "camisole", "pants", "trousers",
      "shorts", "jacket", "coat", "blazer", "vest", "swimsuit", "bikini",
      "underwear", "bra", "panty", "hosiery", "tights"], "服装鞋帽"),
    (["手机壳", "手机套", "iPhone", "Samsung", "数据线", "充电器", "充电宝",
      "蓝牙耳机", "无线耳机", "平板壳", "键盘", "鼠标", "投影仪", "自拍杆",
      "手机支架", "贴膜", "屏幕保护", "转换器", "读卡器", "U盘", "u盘",
      "硬盘", "路由器", "智能手环", "手环", "麦克风", "摄像头", "录音笔"], "3C数码"),
    (["t恤", "T恤", "连衣裙", "衬衫", "卫衣", "外套", "羽绒服", "牛仔裤",
      "短裤", "裙子", "半身裙", "风衣", "西服", "西装", "毛衣", "棉衣",
      "夹克", "马甲", "背心", "吊带", "打底衫", "雪纺衫", "针织衫",
      "运动服", "瑜伽服", "健身服", "泳衣", "睡衣", "家居服", "内衣",
      "文胸", "袜子", "围巾", "帽子", "手套", "浴袍",
      "女装", "男装", "童装", "大码", "女上衣", "男上衣",
      "运动鞋", "跑鞋", "篮球鞋", "凉鞋", "拖鞋", "靴子", "帆布鞋",
      "高跟鞋", "皮鞋", "布鞋", "雪地靴", "短靴", "长靴", "健步鞋",
      "鞋", "女鞋", "男鞋"], "服装鞋帽"),
    (["脏衣篓", "收纳筐", "收纳箱", "收纳盒", "收纳袋", "置物架",
      "衣架", "挂钩", "粘钩", "鞋架", "书架", "衣柜", "鞋柜",
      "台灯", "灯具", "窗帘", "地毯", "地垫", "门垫",
      "花盆", "花瓶", "墙贴", "相框", "挂画", "装饰画", "画框",
      "香薰", "蜡烛", "床上用品", "枕头", "被子", "床单", "四件套",
      "蚊帐", "挂钟", "时钟", "镜子", "抽屉", "垃圾桶",
      "抱枕", "靠垫", "沙发套", "桌布", "餐垫", "照片墙",
      "毛巾", "浴巾", "浴帘", "皂盒", "牙刷架", "纸巾盒",
      "沙发", "桌子", "椅子", "凳子", "茶几", "床头柜",
      "衣帽架", "屏风", "隔断", "装饰", "装饰画", "摆件", "风铃",
      "小推车", "推车", "挂篮", "收纳"], "家居生活"),
    (["杯子", "咖啡杯", "马克杯", "水壶", "保温杯", "饭盒", "便当",
      "保鲜盒", "碗", "盘", "筷子", "刀叉", "勺子", "锅", "炒锅",
      "煎锅", "蒸锅", "砧板", "菜板", "刀具", "削皮器", "开瓶器",
      "围裙", "手套", "厨房", "餐具", "茶具", "茶壶", "茶杯",
      "滤网", "漏勺", "冰格", "制冰", "调味瓶", "油壶", "密封罐",
      "保温", "焖烧", "煲汤", "砂锅", "不粘锅", "不粘"], "厨房餐饮"),
    (["面膜", "精华", "乳液", "面霜", "爽肤水", "化妆品", "口红",
      "粉底", "眼影", "腮红", "卸妆", "洁面", "防晒", "隔离",
      "美妆", "化妆刷", "粉扑", "美甲", "指甲", "纹身", "纹绣",
      "眼线", "睫毛", "眉笔", "遮瑕", "bb霜", "CC霜", "气垫",
      "洗发", "护发", "沐浴", "身体乳", "护手霜", "香皂", "香氛",
      "脱毛", "剃须", "鼻毛", "修眉", "修容", "高光",
      "美容仪", "洁面仪", "导入仪", "射频"], "美容个护"),
    (["狗", "猫", "宠物", "狗窝", "猫窝", "猫砂", "狗粮", "猫粮",
      "猫抓板", "逗猫棒", "狗绳", "狗链", "猫爬架", "宠物衣服",
      "宠物零食", "饮水机", "宠物包", "外出包", "拾便", "尿垫",
      "鸟笼", "鱼缸", "仓鼠", "兔笼", "宠物垫", "宠物床",
      "猫砂盆", "牵引绳", "胸背带", "磨牙棒", "狗玩具", "猫玩具"], "宠物用品"),
    (["帐篷", "睡袋", "登山", "徒步", "骑行", "跑步", "健身",
      "瑜伽", "哑铃", "跳绳", "泳镜", "泳帽", "浮潜", "潜水",
      "滑雪", "滑板", "冲浪", "户外", "露营", "野餐", "烧烤架",
      "折叠椅", "折叠凳", "箱", "野营", "炉具", "登山杖", "望远镜",
      "鱼竿", "渔具", "球", "球拍", "护具", "护膝", "护腕",
      "骑行服", "骑行手套", "骑行头盔", "运动", "登山包", "户外包"], "运动户外"),
    (["包", "手提包", "背包", "钱包", "行李箱", "双肩包", "单肩包",
      "斜挎包", "腰包", "卡包", "化妆包", "电脑包", "公文包",
      "旅行包", "书包", "帆布包", "托特包", "链条包", "胸包",
      "妈咪包", "洗漱包", "行李", "登机箱"], "箱包"),
    (["项链", "戒指", "耳环", "手链", "手镯", "手表", "墨镜",
      "太阳镜", "饰品", "首饰", "珠宝", "发饰", "发夹", "发箍",
      "发圈", "胸针", "袖扣", "脚链", "吊坠", "串珠", "银饰",
      "珍珠", "耳钉", "锁骨链", "18k", "镀金", "钛钢"], "珠宝手表"),
    (["玩具", "积木", "拼图", "娃娃", "遥控", "早教", "儿童",
      "婴儿", "宝宝", "幼儿", "奶瓶", "奶嘴", "尿布", "推车",
      "安全座椅", "爬行垫", "围栏", "餐椅", "婴儿床", "摇篮",
      "学步", "安抚", "磨牙", "咬胶", "牙胶", "辅食", "水杯",
      "童车", "滑板车", "平衡车", "扭扭车", "摇摇马"], "母婴玩具"),
    (["汽车", "车用", "车载", "车内", "座垫", "坐垫", "方向盘套",
      "脚垫", "车衣", "遮阳挡", "手机支架", "行车记录仪", "倒车影像",
      "车载充电器", "香水", "挂件", "摆件", "车标", "改装配件",
      "雨刮", "蜡", "洗车", "清洁", "轮胎", "轮毂"], "汽车用品"),
    (["笔", "笔记本", "便签", "贴纸", "胶带", "文件夹", "档案盒",
      "订书机", "计算器", "印章", "印台", "尺子", "圆规",
      "文具", "办公", "书桌", "台灯", "办公椅", "文件柜",
      "会议", "白板", "黑板", "粉笔", "墨水", "墨盒", "打印纸"], "办公文具"),
]


def guess_category_from_title(title: str) -> str:
    """从商品标题关键词快速推断大品类（中文品类字面值）。

    用于代发卖家场景：Excel 里只有标题，无分类/无 GPC。
    返回的品类字面值会被 resolve_category 的 L2 中文关键词兜底匹配到 cultural_key。
    """
    if not title:
        return ""
    cn_lower = title.lower().strip()
    for keywords, category_name in _TITLE_CATEGORY_HINTS:
        for kw in keywords:
            if kw.lower() in cn_lower:
                return category_name
    return ""


# ═══════════════════════════════════════════════════════════════
# L2 自动语境富化 — GPC 叶节点精准子品类注入
# ═══════════════════════════════════════════════════════════════

def _extract_gpc_leaf(gpc_path: str) -> str:
    """从 GPC 路径中提取最具体的叶节点名称。

    "Apparel & Accessories > Clothing > Dresses > Midi Dresses"
    → "Midi Dresses"
    """
    if not gpc_path:
        return ""
    parts = [s.strip() for s in gpc_path.split(">")]
    return parts[-1] if parts else ""


def get_context(country: str, cn_category: str = "", gpc_path: str = "",
                season: str = "summer") -> str:
    """根据国家 + 品类 + 季节，生成注入 AI Prompt 的文化上下文字符串。

    数据来源（按优先级）：
    1. 预置 60 组四维文化数据（occasions / pain_points / slang / seasonal）
    2. GPC 叶节点精准子品类 → 告诉 AI 具体在卖什么（如 "Midi Dresses"）
    """
    country_upper = country.upper()
    if country_upper not in CULTURAL_MATRIX:
        return ""

    cat_key = resolve_category(cn_category, gpc_path)
    country_data = CULTURAL_MATRIX[country_upper]

    if cat_key not in country_data:
        return ""

    cat_data = country_data[cat_key]
    seasonal = cat_data.get("seasonal", {}).get(season, [])
    occasions = list(cat_data.get("occasions", [])[:3])
    pain_points = list(cat_data.get("pain_points", [])[:3])
    slang = list(cat_data.get("slang", [])[:2])

    # 袜子/内衣等基础服饰：不要用礼服/婚礼场景词
    leaf = _extract_gpc_leaf(gpc_path)
    leaf_l = (leaf or "").lower()
    path_l = (gpc_path or "").lower()
    basic_apparel = any(
        k in leaf_l or k in path_l
        for k in ("sock", "hosiery", "underwear", "bra", "panty", "brief", "tights")
    )
    outerwear = any(
        k in leaf_l or k in path_l
        for k in ("outerwear", "jacket", "coat", "vest")
    )
    is_dress = "dress" in leaf_l or "bridal" in leaf_l
    is_shape = any(k in leaf_l or k in path_l for k in (
        "dress", "pant", "jean", "skirt", "jumpsuit", "romper", "legging",
    ))

    if basic_apparel:
        occasions = [
            "Everyday Comfort",
            "Daily Essentials",
            "Travel Packing",
        ]
        pain_points = [
            "Breathable Soft",
            "No-Show Fit",
            "All-Day Comfort",
        ][:3]
        slang = ["True to Size", "Soft & Stretchy"][:2]

    elif outerwear:
        # 外套：禁塑身话术 + 禁 brunch 堆砌
        occasions = ["Everyday Casual", "Layering", "Streetwear"]
        pain_points = [p for p in pain_points if "tummy" not in p.lower() and "slimming" not in p.lower()]
        if not pain_points:
            pain_points = ["Lightweight Layer", "Easy Layering", "True to Size"]
        slang = [s for s in slang if "slimming" not in s.lower()][:2] or ["Streetwear Fit", "Effortless Style"]
        seasonal = [s for s in seasonal if "friday" not in s.lower() and "brunch" not in s.lower()][:2]

    # 连衣裙/礼服以外的服饰：过滤婚礼场景（避免袜子/牛仔裤套 Wedding Guest）
    elif cat_key == "apparel" and not is_dress:
        blocked = ("wedding", "bridal", "baby shower", "country club", "opera")
        occasions = [o for o in occasions if not any(b in o.lower() for b in blocked)]
        if not occasions:
            occasions = ["Everyday Wear", "Business Casual Office", "Weekend Casual"]
        # 非裙/裤/连体：去掉 tummy
        if not is_shape:
            pain_points = [p for p in pain_points if "tummy" not in p.lower() and "slimming" not in p.lower()]
            if not pain_points:
                pain_points = ["True to Size", "Soft Stretch", "Easy Care"]

    # 提示模型：最多 1 个场景词，优先品类名词
    parts = []
    if occasions:
        parts.append(f"Target occasions (pick AT MOST ONE, optional): {', '.join(occasions[:3])}")
    if pain_points:
        parts.append(f"Customer pain points (only if relevant to this subcategory): {', '.join(pain_points[:3])}")
    if slang:
        parts.append(f"Local consumer slang: {', '.join(slang)}")
    if seasonal:
        parts.append(f"Seasonal trends ({season}): {', '.join(seasonal[:2])}")

    # L2: GPC 叶节点补充 — 告诉 AI 具体子品类
    if leaf and len(leaf) >= 3:
        parts.append(f"Product subcategory: {leaf}")
        parts.append(
            "RULE: Core category noun first. Do NOT use Tummy Control unless subcategory is "
            "Dress/Pants/Jumpsuit/Skirt. Prefer Everyday/Casual over Brunch/Summer Friday for tops and outerwear."
        )

    return "\n".join(parts)


def get_search_prefix(country: str, cn_category: str = "", gpc_path: str = "") -> str:
    """获取本地化性别/目标人群前缀"""
    country_upper = country.upper()
    if country_upper not in CULTURAL_MATRIX:
        return ""
    cat_key = resolve_category(cn_category, gpc_path)
    country_data = CULTURAL_MATRIX[country_upper]
    if cat_key in country_data:
        return country_data[cat_key].get("search_prefix", "")
    return ""


def country_name_local(country: str) -> str:
    names = {"US": "United States", "DE": "Deutschland", "FR": "France",
             "ES": "España", "IT": "Italia"}
    return names.get(country.upper(), country.upper())


def season_for_date(month: int = None) -> str:
    from datetime import datetime
    m = month or datetime.now().month
    if 3 <= m <= 5:   return "spring"
    elif 6 <= m <= 8: return "summer"
    elif 9 <= m <= 11: return "fall"
    return "winter"
