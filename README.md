# Claude Code A股基本面分析 Agent

开箱即用的 Claude Code 投研分析 Agent。无需外部 LLM API — Claude Code 自身就是分析师。

## 安装

```bash
# 1. 克隆项目
git clone <repo-url> claude-stock-agent
cd claude-stock-agent

# 2. 安装依赖
pip install akshare pandas
```

## 使用

在项目目录下启动 Claude Code，然后直接输入：

```
分析 600519
分析一下宁德时代
分析白酒板块
```

Claude Code 会自动：
1. 通过 AKShare 获取真实财务数据
2. 从 5 个维度独立分析（盈利能力、估值、成长性、财务健康、股东回报）
3. 给出综合评分和投资建议
4. 生成暖黄纸质风格 HTML 报告

## 项目结构

```
claude-stock-agent/
├── CLAUDE.md                    # Agent 指令（核心）
├── tools/
│   ├── fetch.py                # 数据获取 CLI（AKShare）
│   └── report.py               # HTML 报告生成器
├── reports/                     # 报告输出目录
├── .claude/settings.local.json  # Claude Code 权限配置
└── requirements.txt
```

## 数据工具

```bash
python tools/fetch.py stock-info 600519      # 基本信息
python tools/fetch.py indicators 600519      # PE/PB/PS/股息率
python tools/fetch.py income 600519          # 利润表
python tools/fetch.py balance 600519         # 资产负债表
python tools/fetch.py cashflow 600519        # 现金流量表
python tools/fetch.py price 600519 --days 60 # 日K行情
python tools/fetch.py dividends 600519       # 分红记录
python tools/fetch.py sector 白酒            # 板块成分股
```

## 免责声明

本工具仅供学习研究使用，不构成任何投资建议。投资有风险，入市需谨慎。
