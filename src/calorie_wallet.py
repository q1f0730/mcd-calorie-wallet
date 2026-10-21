"""卡路里钱包 · 主程序。

用法：
  export MCD_MCP_TOKEN=your_token
  python src/calorie_wallet.py --budget-now 2300 --meal-cap 900 \
      --excludes 鸡肉,花生 --demo   # demo 模式用内置样例菜单跑求解器

不带 --demo 时走真实 MCP 查询。
"""
from __future__ import annotations

import argparse
import sys

from nutrition import Item, solve


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="卡路里钱包：热量预算点餐求解器")
    p.add_argument("--budget-week", type=float, default=12000, help="本周总预算 kcal")
    p.add_argument("--budget-now", type=float, required=True, help="当前剩余预算 kcal")
    p.add_argument("--meal-cap", type=float, default=900, help="本餐上限 kcal")
    p.add_argument("--excludes", default="", help="忌口关键词，逗号分隔")
    p.add_argument("--store", default="", help="门店编号（真实模式）")
    p.add_argument("--demo", action="store_true", help="使用内置样例菜单（不调用 MCP）")
    return p.parse_args(argv)


DEMO_MENU = [
    Item("1", "巨无霸", 550, 26.0, ["beef", "bun"], 4.0, "main"),
    Item("2", "双层吉士汉堡", 448, 23.0, ["beef", "bun"], 4.5, "main"),
    Item("3", "麦香鱼", 331, 18.0, ["fish", "bun"], 3.0, "main"),
    Item("4", "原味板烧鸡腿堡", 431, 24.0, ["chicken", "bun"], 3.5, "main"),
    Item("5", "麦辣鸡翅(2块)", 240, 15.0, ["chicken", "spicy"], 3.0, "side"),
    Item("6", "薯条(中)", 323, 13.5, ["fries"], 4.0, "side"),
    Item("7", "玉米杯", 87, 10.5, ["corn"], 2.0, "side"),
    Item("8", "苹果派", 230, 9.0, ["apple", "dessert"], 2.5, "dessert"),
    Item("9", "零度可乐", 0, 9.5, ["drink", "zero"], 3.0, "drink"),
    Item("10", "鲜煮咖啡", 5, 12.0, ["drink", "coffee"], 2.5, "drink"),
    Item("11", "可口可乐(中)", 180, 10.5, ["drink"], 2.0, "drink"),
    Item("12", "圆筒冰淇淋", 200, 8.0, ["icecream", "dessert"], 3.5, "dessert"),
]


def main(argv=None) -> int:
    args = parse_args(argv)
    excludes = [x for x in args.excludes.split(",") if x.strip()]

    if args.demo:
        items = DEMO_MENU
        source = "内置样例菜单（demo）"
    else:
        import mcd_client as mcd  # noqa: PLC0415 真实模式才导入

        if not mcd.TOKEN:
            print("错误：未设置 MCD_MCP_TOKEN 环境变量", file=sys.stderr)
            return 2
        tools = mcd.list_tools()
        print(f"已连接 mcd-mcp，发现 {len(tools)} 个工具（只读体检通过）")
        raw = mcd.get_menu(args.store)
        items = []
        for r in raw:
            pid = str(r.get("id") or r.get("productId") or "")
            nut = mcd.get_nutrition(pid) or {}
            kcal = nut.get("kcal") or nut.get("energy") or nut.get("energyKcal")
            price = r.get("price") or nut.get("price")
            if kcal is None or price is None:
                continue  # 营养/价格数据缺失，剔除
            items.append(
                Item(pid, r.get("name", pid), float(kcal), float(price),
                     tags=r.get("tags", []) or [])
            )
        source = f"门店 {args.store} 实时菜单"

    plan = solve(items, args.meal_cap, excludes)
    if plan is None:
        print("❌ 当前条件下无解：主食品类被忌口清空或全部超上限，请放宽条件。")
        return 1

    print(f"来源：{source}｜忌口：{excludes or '无'}\n")
    print(plan.bill(args.meal_cap, args.budget_now))
    week_left = args.budget_now - plan.kcal
    if week_left < args.meal_cap:
        print("⚠️ 预警：吃掉这顿后，剩余额度已不足一个标准正餐，建议后续几餐清淡。")
    print("\n（确认下单请回复：确认下单）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
