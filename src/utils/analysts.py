"""与分析师配置相关的常量和实用程序。"""

# 导入各个分析师代理函数
from src.agents.aswath_damodaran import aswath_damodaran_agent
from src.agents.ben_graham import ben_graham_agent
from src.agents.bill_ackman import bill_ackman_agent
from src.agents.cathie_wood import cathie_wood_agent
from src.agents.charlie_munger import charlie_munger_agent
from src.agents.fundamentals import fundamentals_analyst_agent
from src.agents.michael_burry import michael_burry_agent
from src.agents.phil_fisher import phil_fisher_agent
from src.agents.peter_lynch import peter_lynch_agent
from src.agents.sentiment import sentiment_analyst_agent
from src.agents.stanley_druckenmiller import stanley_druckenmiller_agent
from src.agents.technicals import technical_analyst_agent
from src.agents.valuation import valuation_analyst_agent
from src.agents.warren_buffett import warren_buffett_agent
from src.agents.rakesh_jhunjhunwala import rakesh_jhunjhunwala_agent

# 定义分析师配置 - 单一事实来源 (Single Source of Truth)
# 键是分析师的唯一标识符 (例如 "aswath_damodaran")
# 值是一个字典，包含:
#   display_name: 在UI中显示的名称
#   description: 分析师的简短描述
#   agent_func: 与此分析师关联的代理函数 (实际执行分析的函数)
#   order: 用于在UI中排序的顺序号
ANALYST_CONFIG = {
    "aswath_damodaran": {
        "display_name": "阿斯瓦特·达莫达兰", # "Aswath Damodaran"
        "description": "估值院长", # "The Dean of Valuation"
        "agent_func": aswath_damodaran_agent,
        "order": 0,
    },
    "ben_graham": {
        "display_name": "本·格雷厄姆", # "Ben Graham"
        "description": "价值投资之父", # "The Father of Value Investing"
        "agent_func": ben_graham_agent,
        "order": 1,
    },
    "bill_ackman": {
        "display_name": "比尔·阿克曼", # "Bill Ackman"
        "description": "激进投资者", # "The Activist Investor"
        "agent_func": bill_ackman_agent,
        "order": 2,
    },
    "cathie_wood": {
        "display_name": "凯茜·伍德", # "Cathie Wood"
        "description": "成长投资女王", # "The Queen of Growth Investing"
        "agent_func": cathie_wood_agent,
        "order": 3,
    },
    "charlie_munger": {
        "display_name": "查理·芒格", # "Charlie Munger"
        "description": "理性思考者", # "The Rational Thinker"
        "agent_func": charlie_munger_agent,
        "order": 4,
    },
    "michael_burry": {
        "display_name": "迈克尔·贝瑞", # "Michael Burry"
        "description": "大空头逆向投资者", # "The Big Short Contrarian"
        "agent_func": michael_burry_agent,
        "order": 5,
    },
    "peter_lynch": {
        "display_name": "彼得·林奇", # "Peter Lynch"
        "description": "十倍股投资者", # "The 10-Bagger Investor"
        "agent_func": peter_lynch_agent,
        "order": 6,
    },
    "phil_fisher": {
        "display_name": "菲利普·费雪", # "Phil Fisher"
        "description": "闲聊法投资者", # "The Scuttlebutt Investor"
        "agent_func": phil_fisher_agent,
        "order": 7,
    },
    "rakesh_jhunjhunwala": {
        "display_name": "拉克什·琼琼瓦拉", # "Rakesh Jhunjhunwala"
        "description": "印度大牛", # "The Big Bull Of India"
        "agent_func": rakesh_jhunjhunwala_agent,
        "order": 8,
    },
    "stanley_druckenmiller": {
        "display_name": "斯坦利·德鲁肯米勒", # "Stanley Druckenmiller"
        "description": "宏观投资者", # "The Macro Investor"
        "agent_func": stanley_druckenmiller_agent,
        "order": 9,
    },
    "warren_buffett": {
        "display_name": "沃伦·巴菲特", # "Warren Buffett"
        "description": "奥马哈先知", # "The Oracle of Omaha"
        "agent_func": warren_buffett_agent,
        "order": 10,
    },
    "technical_analyst": {
        "display_name": "技术分析师", # "Technical Analyst"
        "description": "图表形态专家", # "Chart Pattern Specialist"
        "agent_func": technical_analyst_agent,
        "order": 11,
    },
    "fundamentals_analyst": {
        "display_name": "基本面分析师", # "Fundamentals Analyst"
        "description": "财务报表专家", # "Financial Statement Specialist"
        "agent_func": fundamentals_analyst_agent,
        "order": 12,
    },
    "sentiment_analyst": {
        "display_name": "情绪分析师", # "Sentiment Analyst"
        "description": "市场情绪专家", # "Market Sentiment Specialist"
        "agent_func": sentiment_analyst_agent,
        "order": 13,
    },
    "valuation_analyst": {
        "display_name": "估值分析师", # "Valuation Analyst"
        "description": "公司估值专家", # "Company Valuation Specialist"
        "agent_func": valuation_analyst_agent,
        "order": 14,
    },
}

# 从 ANALYST_CONFIG 派生 ANALYST_ORDER，以实现向后兼容。
# ANALYST_ORDER 是一个元组列表，每个元组包含 (显示名称, 分析师键)，并按 "order" 字段排序。
# 这主要用于在 questionary 等UI库中按特定顺序显示分析师选项。
ANALYST_ORDER = [(config["display_name"], key) for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])]


def get_analyst_nodes():
    """获取分析师键到其 (节点名称, 代理函数) 元组的映射。"""
    # 节点名称通常是 "分析师键_agent" 的形式。
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}


def get_agents_list():
    """获取用于API响应的代理(分析师)列表。"""
    # 返回一个字典列表，每个字典包含分析师的键、显示名称、描述和顺序。
    # 列表按 "order" 字段排序。
    return [
        {
            "key": key,
            "display_name": config["display_name"],
            "description": config["description"],
            "order": config["order"]
        }
        for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])
    ]
