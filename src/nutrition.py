"""营养数据模型与热量预算约束求解。

核心思想：把"点餐"建模成一个受热量硬约束的背包问题——
每个候选商品有一个 kcal 体积、一个用户偏好收益值，
在不超预算上限的前提下最大化收益（偏好满足度）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product


@dataclass
class Item:
    """一个候选餐品（来自麦当劳 MCP 实时数据）。"""

    id: str
    name: str
    kcal: float
    price: float
    tags: list[str] = field(default_factory=list)   # 如 ["beef", "drink", "set"]
    preference: float = 1.0                         # 用户偏好收益 0~5
    category: str = "other"                         # main / side / drink / dessert


@dataclass
class Plan:
    """一次求解结果：一组商品 + 账单。"""

    items: list[Item] = field(default_factory=list)

    @property
    def kcal(self) -> float:
        return sum(i.kcal for i in self.items)

    @property
    def price(self) -> float:
        return round(sum(i.price for i in self.items), 2)

    @property
    def kcal_per_yuan(self) -> float:
        return round(self.kcal / self.price, 1) if self.price else 0.0

    def bill(self, meal_cap: float, week_remaining: float) -> str:
        lines = ["🍔 卡路里钱包 · 确认单", "─" * 30]
        for i in self.items:
            lines.append(f"  {i.name:<12}{i.kcal:>7.0f} kcal  ¥{i.price:.1f}")
        lines.append("─" * 30)
        lines.append(f"  合计{self.kcal:>12.0f} kcal  ¥{self.price:.1f}")
        ok = "✅" if self.kcal <= meal_cap else "❌ 超出本餐上限"
        lines.append(f"  本餐上限 {meal_cap:.0f} kcal {ok}  缓冲 {meal_cap - self.kcal:.0f} kcal")
        lines.append(f"  本周余额：{week_remaining:.0f} → {week_remaining - self.kcal:.0f} kcal")
        lines.append(f"  热量单价：{self.kcal_per_yuan} kcal/元")
        return "\n".join(lines)


def solve(
    items: list[Item],
    meal_cap: float,
    excludes: list[str] | None = None,
    require_categories: tuple[str, ...] = ("main",),
) -> Plan | None:
    """在 meal_cap 硬约束下求收益最大的组合。

    规则：
    - 命中忌口关键词的商品直接剔除；
    - 营养数据缺失（kcal<=0 且非明确 0 卡饮品）剔除；
    - 必须包含 require_categories 中每一类至少一件；
    - 剩余空间用偏好收益/kcal 比值最高的商品填满；
    - main 最多 1 件，其余类别最多 2 件。
    """
    excludes = [e.strip().lower() for e in (excludes or []) if e.strip()]
    # 扩展匹配词：如"鸡肉"也能拦住"麦辣鸡翅"（去掉尾部类目词后的核心字）
    expand = set(excludes)
    for e in excludes:
        if e.endswith("肉"):
            expand.add(e[:-1])

    pool: list[Item] = []
    for it in items:
        name_and_tags = (it.name + " " + " ".join(it.tags)).lower()
        if any(e in name_and_tags for e in expand):
            continue
        if it.kcal <= 0 and it.category != "drink":
            continue  # 营养数据缺失（0 卡饮品除外）
        pool.append(it)

    by_cat: dict[str, list[Item]] = {}
    for it in pool:
        by_cat.setdefault(it.category, []).append(it)

    required = tuple(dict.fromkeys(require_categories))
    for cat in required:
        if cat not in by_cat:
            return None  # 硬约束无解，上层应提示用户放宽条件

    seed_groups = [by_cat[cat] for cat in required]
    seed_options = product(*seed_groups) if seed_groups else [()]
    ranked = sorted(pool, key=lambda i: i.preference / max(i.kcal, 1), reverse=True)

    best: Plan | None = None
    for seed in seed_options:
        seed_items: list[Item] = []
        for item in seed:
            if item not in seed_items:
                seed_items.append(item)

        plan = Plan(items=seed_items)
        if plan.kcal > meal_cap:
            continue

        for extra in ranked:
            if extra in plan.items:
                continue
            if plan.kcal + extra.kcal > meal_cap:
                continue

            cat = extra.category
            limit = 1 if cat == "main" else 2
            if sum(1 for i in plan.items if i.category == cat) >= limit:
                continue
            plan.items.append(extra)

        # 先满足硬约束，再沿用原行为：尽量利用本餐热量额度。
        if best is None or plan.kcal > best.kcal:
            best = plan

    return best
