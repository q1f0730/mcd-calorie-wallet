"""卡路里钱包 v2 · 主程序（真实 MCP 数据全链路版）。

升级点（相对 v1）：
1. 全链路真实数据：附近门店 → 实时菜单 → 营养匹配 → 真实计价（calculate-price，分→元）
2. 营养表与菜单名做规范化模糊匹配（去括号/空格/装饰符 + 双向包含），
   匹配不到 kcal 即剔除，绝不凭记忆猜数字
3. calculate-price 真实价格试算 + 热量单价（kcal/元）

用法：
  export MCD_MCP_TOKEN=your_token   # 或写入项目根目录 .env
  python src/calorie_wallet.py --budget-now 2300 --meal-cap 900 --excludes 鸡肉
  python src/calorie_wallet.py --demo   # 离线样例模式
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from nutrition import Item, solve


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="卡路里钱包：热量预算点餐求解器（真实MCP数据）")
    p.add_argument("--budget-now", type=float, default=2300, help="当前剩余周预算 kcal")
    p.add_argument("--meal-cap", type=float, default=900, help="本餐上限 kcal")
    p.add_argument("--excludes", default="", help="忌口关键词，逗号分隔")
    p.add_argument("--city", default="上海市")
    p.add_argument("--keyword", default="南京东路")
    p.add_argument("--store", default="", help="门店编码（不填则自动搜索）")
    p.add_argument("--demo", action="store_true", help="使用内置样例菜单（不调用 MCP）")
    return p.parse_args(argv)


DEMO_MENU = [
    Item("1", "巨无霸", 550, 26.0, ["beef", "bun"], 4.0, "main"),
    Item("2", "双层吉士汉堡", 448, 23.0, ["beef", "bun"], 4.5, "main"),
    Item("3", "麦香鱼", 331, 18.0, ["fish", "bun"], 3.0, "main"),
    Item("4", "原味板烧鸡腿堡", 431, 24.0, ["chicken", "bun"], 3.5, "main"),
    Item("5", "薯条(中)", 323, 13.5, ["fries"], 4.0, "side"),
    Item("6", "玉米杯", 87, 10.5, ["corn"], 2.0, "side"),
    Item("7", "苹果派", 230, 9.0, ["apple"], 2.5, "side"),
    Item("8", "零度可乐", 0, 9.5, ["zero"], 3.0, "drink"),
    Item("9", "鲜煮咖啡", 5, 12.0, ["coffee"], 2.5, "drink"),
]


def norm(name: str) -> str:
    """名称规范化：去空格/括号内容/装饰符，便于营养表模糊匹配。"""
    n = re.sub(r"[（(【\[].*?[)）\]】]", "", name)
    return re.sub(r"[\s·・]+", "", n)


def match_nutrition(meal_name: str, nut_index: dict) -> float | None:
    """菜单名 → 营养表 kcal。精确 → 规范化 → 双向包含 → 剥离套餐后缀；找不到返回 None。"""
    if meal_name in nut_index:
        return nut_index[meal_name]
    n = norm(meal_name)
    if n in nut_index:
        return nut_index[n]
    for key, kcal in nut_index.items():
        nk = norm(key)
        if nk and (nk in n or n in nk):
            return kcal
    # 剥离套餐后缀再试（"巨无霸四件套" → "巨无霸"）
    n2 = re.sub(r"(三|四|二|五)?件套$", "", n)
    if n2 != n and n2 in nut_index:
        return nut_index[n2]
    for key, kcal in nut_index.items():
        nk = norm(key)
        if n2 and nk and (nk in n2 or n2 in nk):
            return kcal
    return None


def categorize(name: str) -> str:
    # 饮品判定优先（"冰""茶"等可能出现在套餐名里，但套餐名含堡/卷必为main）
    if any(w in name for w in ("可乐", "咖啡", "茶", "汁", "奶昔", "奶茶")) and "堡" not in name:
        return "drink"
    if any(w in name for w in ("堡", "麦满分", "卷")):
        return "main"
    return "side"


def extract_json(d: dict | None) -> dict | None:
    """mcd_client 返回 raw 文本时，从中括号配平提取 JSON payload。"""
    if not d:
        return None
    if "raw" not in d:
        return d
    s = d["raw"]
    i = s.find('{"success"')
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[i:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_nutrition(raw: str) -> dict[str, float]:
    """TOON 营养数据 → {餐品名: kcal}。"""
    k = raw.find("[")
    m1 = re.match(r"\[(\d+)\]\{([^}]+)\}:(.*)", raw[k:], re.S)
    if not m1:
        return {}
    fields = m1.group(2).split(",")
    out: dict[str, float] = {}
    for line in m1.group(3).replace("\\n", "\n").splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(fields):
            continue
        d = dict(zip(fields, parts))
        try:
            out[d["productName"]] = float(d["energyKcal"])
        except (ValueError, KeyError):
            continue
    return out


def run_demo(args) -> int:
    plan = solve(DEMO_MENU, args.meal_cap, [x for x in args.excludes.split(",") if x.strip()])
    if plan is None:
        print("❌ 当前条件下无解，请放宽忌口或上限。")
        return 1
    print(plan.bill(args.meal_cap, args.budget_now))
    return 0


def run_real(args) -> int:
    import mcd_client as mcd  # 真实模式才导入

    if not mcd.TOKEN:
        print("错误：未设置 MCD_MCP_TOKEN", file=sys.stderr)
        return 2
    mcd._ensure_session()
    print("✅ mcd-mcp 会话已建立")

    # 1. 门店
    store_code = args.store
    if not store_code:
        stores = extract_json(mcd.call_tool(
            "query-nearby-stores",
            {"beType": 1, "searchType": 2, "city": args.city, "keyword": args.keyword}))
        if not stores or not stores.get("data"):
            print("❌ 未找到门店，请检查城市/关键词", file=sys.stderr)
            return 1
        st = stores["data"][0]
        store_code = st["storeCode"]
        print(f"📍 门店：{st['storeName']}（{st['address']}，{st['distance']}m）")

    # 2. 菜单
    menu = extract_json(mcd.call_tool(
        "query-meals", {"orderType": 1, "beType": 1, "storeCode": store_code}))
    if not menu or not menu.get("data"):
        print("❌ 菜单拉取失败", file=sys.stderr)
        return 1
    meals = [meal for cat in menu["data"]["categories"] for meal in cat["meals"]]
    print(f"📋 在售餐品 {len(meals)} 项")

    # 3. 营养表（全量一次拉取）
    d = mcd.call_tool("list-nutrition-foods", {})
    raw = (d or {}).get("raw", "")
    nut_index = parse_nutrition(raw)
    print(f"🔥 营养表 {len(nut_index)} 项")

    # 4. 批量拉详情拿名称（菜单接口只给 code+tags；详情接口 600次/分钟限流内安全）
    print("🔍 拉取餐品详情（获取名称）...")
    names: dict[str, str] = {}
    for meal in meals:
        code = str(meal.get("code", ""))
        resp = extract_json(mcd.call_tool("query-meal-detail", {
            "orderType": 1, "beType": 1, "storeCode": store_code, "code": code}))
        if resp and resp.get("data") and resp["data"].get("name"):
            names[code] = resp["data"]["name"]

    # 5. 营养匹配 → 候选池（kcal 匹配不到即剔除，绝不猜数字）
    candidates: list[Item] = []
    unmatched = 0
    for code, name in names.items():
        kcal = match_nutrition(name, nut_index)
        if kcal is None:
            unmatched += 1
            continue
        candidates.append(Item(code, name, kcal, 0.0, [], 3.0, categorize(name)))
    print(f"🔗 营养匹配成功 {len(candidates)} 项（缺失剔除 {unmatched} 项）")
    if not candidates:
        print("❌ 无匹配营养数据的餐品，无法求解", file=sys.stderr)
        return 1

    # 6. 求解
    excludes = [x for x in args.excludes.split(",") if x.strip()]
    plan = solve(candidates, args.meal_cap, excludes)
    if plan is None:
        print("❌ 当前条件下无解：主食品类被忌口清空或全部超上限。")
        return 1

    # 7. 真实计价（calculate-price，分→元）
    for it in plan.items:
        resp = extract_json(mcd.call_tool("calculate-price", {
            "orderType": 1, "beType": 1, "storeCode": store_code,
            "items": [{"productCode": it.id, "quantity": 1}]}))
        if resp and resp.get("data") and resp["data"].get("price") is not None:
            it.price = resp["data"]["price"] / 100.0

    # 8. 账单
    print()
    print(plan.bill(args.meal_cap, args.budget_now))
    if excludes:
        print(f"（忌口：{args.excludes}）")
    print("\n（确认下单请回复：确认下单）")
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    return run_demo(args) if args.demo else run_real(args)


if __name__ == "__main__":
    raise SystemExit(main())
