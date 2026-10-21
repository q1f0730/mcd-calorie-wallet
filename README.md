# 卡路里钱包 · Calorie Wallet 🍔🔥

> 身材管控期也想吃麦当劳？把热量当钱花，让 AI 帮你把每一大卡都花在刀刃上。

## 项目介绍

**卡路里钱包**是一个基于麦当劳 MCP 能力开发的 Skill。它不是又一个"根据口味推荐套餐"的推荐器，而是一个**带硬约束的热量预算求解器**：

- 你给 AI 一个**周热量预算**（比如 12000 kcal）和今天的剩余额度
- 它调用麦当劳 MCP 查询**真实菜单、营养数据和价格**
- 在"不超预算"的硬约束下，为你求解一套当日麦麦组合
- 超预算时它不会硬凑，而是明确告诉你：**今天只吃得起一个小汉堡**，或者给出"砍掉薯条换零度可乐"的替代方案

### 核心差异（为什么不是又一个推荐器）

| 普通点餐推荐 | 卡路里钱包 |
|---|---|
| 输入：口味偏好 | 输入：**剩余热量预算 + 偏好 + 忌口** |
| 输出：一堆"猜你喜欢" | 输出：**一套满足热量硬约束的订单方案** |
| 超了超了没人管 | 超预算就降级/替换，给出明细账单 |
| 不关心价格 | 结合价格试算，热量单价（kcal/元）可视化 |

### 一句话示例

```
我：这周还剩 2300 kcal，晚饭想吃麦当劳，别超过 900，无鸡肉。
AI：好。查询门店菜单后给你这套方案（合计 862 kcal / ¥46.5）：
    - 双层吉士汉堡（不含鸡肉）448 kcal
    - 玉米杯 87 kcal
    - 零度可乐 0 kcal
    - 原味板烧鸡腿堡 ❌ 剔除（含鸡肉）
    热量余额预警：吃掉这顿后本周仅剩 1438 kcal，周五前建议早餐吃燕麦。
```

## 安装方法

### 1. 准备麦当劳 MCP Token

按照麦当劳 MCP 官方渠道说明获取你的 MCP Token（形如 `Bearer YOUR_MCP_TOKEN`）。

### 2. 配置 MCP 连接

在支持 MCP 的客户端（如腾讯 WorkBuddy 的自定义连接器）中填入：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

### 3. 安装本项目 Skill

```bash
git clone https://github.com/<你的用户名>/mcd-calorie-wallet.git
cd mcd-calorie-wallet
pip install -r requirements.txt
```

## 使用示例

### 命令行直接使用

```bash
export MCD_MCP_TOKEN=your_token_here
python src/calorie_wallet.py --budget-week 12000 --budget-now 2300 \
  --meal dinner --excludes "鸡肉,花生" --max-price 60
```

### 作为 Skill 接入 AI 对话

把 `SKILL_PROMPT.md` 的内容作为系统提示词，AI 将自动按"预算求解"流程调用 MCP 工具。

## 目标用户

- **减脂期打工人**：想吃麦当劳又怕热量爆炸的人
- **健身人群**：按宏量营养素做饮食规划，需要一个"放纵餐计算器"
- **血糖敏感人群**：需要控制单餐热量与糖分摄入的人
- **所有说"随便，但要健康"的人**

## 项目结构

```
mcd-calorie-wallet/
├── README.md                  # 本文件
├── CONTEST_DECLARATION.md     # 参赛声明（官方原文，未修改）
├── MCP_INTEGRATION.md         # 麦当劳 MCP 集成说明
├── SKILL_PROMPT.md            # Skill 系统提示词
├── mcp-config.example.json    # 脱敏 MCP 配置示例
├── workbuddy.md               # WorkBuddy 对话上下文（WorkBuddy 专项奖励）
├── requirements.txt
├── src/
│   ├── calorie_wallet.py      # 主程序：预算求解引擎
│   ├── mcd_client.py          # 麦当劳 MCP 客户端封装
│   └── nutrition.py           # 营养数据模型与约束求解
├── docs/
│   └── design.md              # 设计思路
└── examples/
    └── session_example.md     # 对话示例
```

## License

MIT
