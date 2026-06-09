from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from rag.retriever import KnowledgeRetriever
from schemas.profile import StudentProfile

logger = logging.getLogger(__name__)

SAFE_ANSWERS = {
    "hello": "你好！有什么Python问题我可以帮你解答吗？",
    "hi": "嗨！欢迎提问，我会尽力帮助你学习Python。",
    "你好": "你好！我是你的 AI 学习助手，可以帮你解答编程问题、讲解知识点、梳理学习路线。请问有什么可以帮你的？",
    "thank": "不客气！继续加油学习Python吧！",
    "谢谢": "不客气！有任何问题随时问我，祝学习愉快！",
    "bye": "再见！祝学习愉快！",
    "再见": "再见！有问题随时回来找我，祝学习顺利！",
}

BLOCKED_KEYWORDS = ["暴力", "赌博", "色情", "政治", "黑客", "病毒"]

# 按优先级排列的主题关键词 → 回复映射
TOPIC_ANSWERS: list[tuple[list[str], str]] = [
    (
        ["递归", "recursion", "recursive"],
        "## 递归算法\n\n"
        "递归是函数调用自身的编程技巧，核心包含两部分：\n\n"
        "**1. 基线条件（Base Case）**：终止递归的条件，防止无限调用\n"
        "**2. 递归步骤**：将问题分解为更小的子问题，调用自身求解\n\n"
        "```python\n"
        "# 经典示例：阶乘\n"
        "def factorial(n):\n"
        "    if n <= 1:       # 基线条件\n"
        "        return 1\n"
        "    return n * factorial(n - 1)  # 递归步骤\n"
        "```\n\n"
        "**注意事项：**\n"
        "- Python 默认递归深度约 1000 层，可用 `sys.setrecursionlimit()` 调整\n"
        "- 递归效率较低时可用 `functools.lru_cache` 做记忆化优化\n"
        "- 大多数递归都可以改写为迭代，性能更好\n\n"
        "想了解递归的哪方面更多？比如尾递归优化、递归与动态规划的关系？",
    ),
    (
        ["排序", "sort", "冒泡", "快排", "快速排序", "归并", "选择排序", "插入排序"],
        "## 排序算法\n\n"
        "常见排序算法对比：\n\n"
        "| 算法 | 平均时间 | 最坏时间 | 空间 | 稳定性 |\n"
        "|------|---------|---------|------|--------|\n"
        "| 冒泡排序 | O(n²) | O(n²) | O(1) | 稳定 |\n"
        "| 选择排序 | O(n²) | O(n²) | O(1) | 不稳定 |\n"
        "| 插入排序 | O(n²) | O(n²) | O(1) | 稳定 |\n"
        "| 快速排序 | O(n log n) | O(n²) | O(log n) | 不稳定 |\n"
        "| 归并排序 | O(n log n) | O(n log n) | O(n) | 稳定 |\n\n"
        "```python\n"
        "# Python 内置排序（Timsort，O(n log n)）\n"
        "arr = [3, 1, 4, 1, 5, 9]\n"
        "arr.sort()           # 原地排序\n"
        "sorted_arr = sorted(arr)  # 返回新列表\n"
        "```\n\n"
        "实际开发中推荐直接使用 Python 内置的 `sort()`/`sorted()`，底层是 Timsort 算法，效率很高。",
    ),
    (
        ["机器学习", "machine learning", "ml", "深度学习", "deep learning", "神经网络", "ai"],
        "## 机器学习学习路线\n\n"
        "**第一阶段：数学基础**\n"
        "- 线性代数：矩阵运算、特征值分解\n"
        "- 概率统计：贝叶斯定理、概率分布\n"
        "- 微积分：梯度、链式法则\n\n"
        "**第二阶段：经典算法**\n"
        "- 线性回归、逻辑回归\n"
        "- 决策树、随机森林\n"
        "- SVM 支持向量机\n"
        "- K-means 聚类\n\n"
        "**第三阶段：深度学习**\n"
        "- 神经网络基础（前馈、反向传播）\n"
        "- CNN 卷积神经网络（图像识别）\n"
        "- RNN/LSTM（序列建模）\n"
        "- Transformer（NLP 基础）\n\n"
        "**推荐工具：** scikit-learn → PyTorch / TensorFlow\n\n"
        "建议从 Kaggle 入门赛开始实践，边做项目边学理论效果最好。",
    ),
    (
        ["数据结构", "链表", "栈", "队列", "树", "图", "哈希", "堆", "二叉树"],
        "## 常见数据结构\n\n"
        "**线性结构：**\n"
        "- **数组/列表**：随机访问 O(1)，插入删除 O(n)\n"
        "- **链表**：插入删除 O(1)，查找 O(n)\n"
        "- **栈**：后进先出（LIFO），用于括号匹配、递归模拟\n"
        "- **队列**：先进先出（FIFO），用于 BFS、任务调度\n\n"
        "**非线性结构：**\n"
        "- **二叉树**：BST 查找 O(log n)，遍历有前/中/后序\n"
        "- **堆**：优先队列，top-K 问题利器\n"
        "- **图**：DFS/BFS 遍历，最短路径、拓扑排序\n"
        "- **哈希表**：O(1) 查找，Python 的 dict 就是哈希表\n\n"
        "```python\n"
        "# Python 内置数据结构\n"
        "from collections import deque, defaultdict, Counter\n"
        "import heapq\n"
        "```\n\n"
        "学习建议：先理解每种结构的适用场景，再刷题巩固。",
    ),
    (
        ["循环", "for", "while", "迭代", "遍历", "loop", "iterator"],
        "## 循环结构\n\n"
        "**for 循环** — 适合已知迭代次数：\n"
        "```python\n"
        "for i in range(5):        # 0, 1, 2, 3, 4\n"
        "    print(i)\n\n"
        "for item in [1, 2, 3]:    # 遍历列表\n"
        "    print(item)\n\n"
        "for k, v in my_dict.items():  # 遍历字典\n"
        "    print(k, v)\n"
        "```\n\n"
        "**while 循环** — 适合条件驱动：\n"
        "```python\n"
        "count = 0\n"
        "while count < 5:\n"
        "    print(count)\n"
        "    count += 1    # 别忘了更新条件！\n"
        "```\n\n"
        "**控制语句：**\n"
        "- `break`：跳出整个循环\n"
        "- `continue`：跳过本次迭代\n"
        "- `else` 子句：循环正常结束（未被 break）时执行\n\n"
        "**常用技巧：** `enumerate()` 获取索引、`zip()` 并行遍历、列表推导式替代简单循环。",
    ),
    (
        ["函数", "def", "参数", "返回值", "return", "lambda", "闭包", "装饰器"],
        "## 函数\n\n"
        "**基本定义：**\n"
        "```python\n"
        "def greet(name, greeting=\"你好\"):\n"
        "    \"\"\"打招呼函数\"\"\"\n"
        "    return f\"{greeting}, {name}!\"\n"
        "```\n\n"
        "**参数类型：**\n"
        "- 位置参数：`def f(a, b)`\n"
        "- 默认参数：`def f(a, b=10)`\n"
        "- 可变参数：`*args`（元组）、`**kwargs`（字典）\n"
        "- 关键字参数：`f(name=\"Tom\")`\n\n"
        "**进阶特性：**\n"
        "```python\n"
        "# Lambda 匿名函数\n"
        "square = lambda x: x ** 2\n\n"
        "# 装饰器\n"
        "def my_decorator(func):\n"
        "    def wrapper(*args, **kwargs):\n"
        "        print(\"Before\")\n"
        "        result = func(*args, **kwargs)\n"
        "        print(\"After\")\n"
        "        return result\n"
        "    return wrapper\n"
        "```",
    ),
    (
        ["类", "class", "对象", "object", "继承", "多态", "封装", "oop", "面向对象", "__init__", "self"],
        "## 面向对象编程（OOP）\n\n"
        "**基本概念：**\n"
        "```python\n"
        "class Student:\n"
        "    def __init__(self, name, age):\n"
        "        self.name = name      # 实例属性\n"
        "        self.age = age\n\n"
        "    def introduce(self):      # 实例方法\n"
        "        return f\"我叫{self.name}，{self.age}岁\"\n\n"
        "# 继承\n"
        "class GradStudent(Student):\n"
        "    def __init__(self, name, age, research):\n"
        "        super().__init__(name, age)\n"
        "        self.research = research\n"
        "```\n\n"
        "**三大特性：**\n"
        "- **封装**：隐藏内部实现，暴露接口\n"
        "- **继承**：子类复用父类代码\n"
        "- **多态**：同一方法不同表现\n\n"
        "**常用魔术方法：** `__str__`、`__repr__`、`__len__`、`__eq__`、`__lt__`",
    ),
    (
        ["文件", "file", "open", "读写", "read", "write", "csv", "json"],
        "## 文件操作\n\n"
        "```python\n"
        "# 读写文本文件\n"
        "with open('data.txt', 'r', encoding='utf-8') as f:\n"
        "    content = f.read()        # 读全部\n"
        "    # lines = f.readlines()   # 读所有行\n"
        "    # line = f.readline()     # 读一行\n\n"
        "with open('output.txt', 'w', encoding='utf-8') as f:\n"
        "    f.write('Hello World\\n')\n"
        "```\n\n"
        "**常用模式：** `'r'` 读、`'w'` 写（覆盖）、`'a'` 追加、`'rb'`/`'wb'` 二进制\n\n"
        "**处理 JSON：**\n"
        "```python\n"
        "import json\n"
        "data = json.loads(json_string)   # 字符串 → 字典\n"
        "text = json.dumps(data, ensure_ascii=False, indent=2)  # 字典 → 字符串\n"
        "```\n\n"
        "**处理 CSV：**\n"
        "```python\n"
        "import csv\n"
        "with open('data.csv') as f:\n"
        "    reader = csv.DictReader(f)\n"
        "    for row in reader:\n"
        "        print(row['name'])\n"
        "```",
    ),
    (
        ["异常", "error", "try", "except", "raise", "报错", "错误处理", "exception"],
        "## 异常处理\n\n"
        "```python\n"
        "try:\n"
        "    result = 10 / 0\n"
        "except ZeroDivisionError as e:\n"
        "    print(f\"除零错误：{e}\")\n"
        "except (TypeError, ValueError):\n"
        "    print(\"类型或值错误\")\n"
        "except Exception as e:\n"
        "    print(f\"未知错误：{e}\")\n"
        "else:\n"
        "    print(\"没有异常时执行\")\n"
        "finally:\n"
        "    print(\"始终执行（清理资源）\")\n"
        "```\n\n"
        "**常见异常类型：**\n"
        "- `TypeError`：类型错误\n"
        "- `ValueError`：值错误\n"
        "- `KeyError` / `IndexError`：键/索引不存在\n"
        "- `FileNotFoundError`：文件不存在\n"
        "- `AttributeError`：属性不存在\n\n"
        "**最佳实践：** 只捕获预期的异常，避免裸 `except:` 吞掉所有错误。",
    ),
    (
        ["字符串", "string", "str", "split", "join", "replace", "strip", "format", "f-string"],
        "## 字符串操作\n\n"
        "```python\n"
        "s = \"Hello, Python!\"\n\n"
        "# 常用方法\n"
        "s.upper()          # 转大写\n"
        "s.lower()          # 转小写\n"
        "s.strip()          # 去两端空白\n"
        "s.split(\", \")      # 分割 → ['Hello', 'Python!']\n"
        "\", \".join(['a', 'b'])  # 拼接 → 'a, b'\n"
        "s.replace(\"Hello\", \"Hi\")  # 替换\n"
        "s.startswith(\"He\")  # True\n"
        "s.find(\"Python\")    # 7（索引）\n"
        "```\n\n"
        "**格式化方式：**\n"
        "```python\n"
        "name, age = \"Tom\", 20\n"
        "f\"我叫{name}，{age}岁\"      # f-string（推荐）\n"
        "\"我叫{}，{}岁\".format(name, age)  # format\n"
        "\"我叫%s，%d岁\" % (name, age)     # % 格式化（旧式）\n"
        "```",
    ),
    (
        ["列表", "list", "字典", "dict", "元组", "tuple", "集合", "set"],
        "## Python 核心数据结构\n\n"
        "**列表 list** — 有序可变：\n"
        "```python\n"
        "lst = [1, 2, 3]\n"
        "lst.append(4)        # 添加\n"
        "lst.insert(0, 0)     # 插入\n"
        "lst.pop()            # 弹出末尾\n"
        "[x*2 for x in lst]  # 列表推导式\n"
        "```\n\n"
        "**字典 dict** — 键值对：\n"
        "```python\n"
        "d = {'name': 'Tom', 'age': 20}\n"
        "d['email'] = 'a@b.com'  # 添加/修改\n"
        "d.get('phone', '无')    # 安全获取\n"
        "{k: v for k, v in d.items()}  # 字典推导式\n"
        "```\n\n"
        "**元组 tuple** — 有序不可变：`t = (1, 2, 3)`\n"
        "**集合 set** — 无序去重：`s = {1, 2, 3}`，支持交并差运算",
    ),
    (
        ["模块", "import", "包", "package", "pip", "install", "第三方库"],
        "## 模块与包\n\n"
        "```python\n"
        "# 导入方式\n"
        "import math                     # 导入整个模块\n"
        "from os import path             # 导入特定函数\n"
        "import numpy as np              # 别名导入\n"
        "```\n\n"
        "**常用标准库：**\n"
        "- `os` / `pathlib`：文件和路径操作\n"
        "- `json`：JSON 处理\n"
        "- `re`：正则表达式\n"
        "- `datetime`：日期时间\n"
        "- `collections`：高级数据结构\n"
        "- `itertools`：迭代器工具\n\n"
        "**安装第三方库：**\n"
        "```bash\n"
        "pip install requests       # 安装\n"
        "pip install -r requirements.txt  # 批量安装\n"
        "pip list                   # 查看已安装\n"
        "```\n\n"
        "建议使用虚拟环境 `python -m venv .venv` 隔离项目依赖。",
    ),
    (
        ["蓝桥杯", "竞赛", "算法题", "刷题", "leetcode", "oj", "比赛"],
        "## 竞赛与刷题建议\n\n"
        "**蓝桥杯 Python 备赛路线：**\n\n"
        "1. **基础算法**：枚举、模拟、排序、搜索（DFS/BFS）\n"
        "2. **数据结构**：栈、队列、堆、并查集\n"
        "3. **动态规划**：背包问题、区间 DP、树形 DP\n"
        "4. **图论**：最短路（Dijkstra）、最小生成树、拓扑排序\n"
        "5. **数学**：数论基础、组合数学、快速幂\n\n"
        "**刷题技巧：**\n"
        "- 先独立思考 20 分钟，实在没思路再看题解\n"
        "- 做完后一定要看其他人的优秀解法\n"
        "- 注意时间复杂度，Python 中 `sys.stdin` 比 `input()` 快\n"
        "- 善用 `collections`、`heapq`、`bisect` 等标准库\n\n"
        "**推荐平台：** 蓝桥云课、洛谷、LeetCode、Codeforces",
    ),
    (
        ["变量", "类型", "int", "float", "bool", "数据类型", "类型转换"],
        "## 变量与数据类型\n\n"
        "```python\n"
        "# 基本类型\n"
        "x = 10           # int 整数\n"
        "y = 3.14         # float 浮点数\n"
        "name = \"Tom\"      # str 字符串\n"
        "is_ok = True     # bool 布尔值\n"
        "items = [1, 2]   # list 列表\n"
        "info = {'a': 1}  # dict 字典\n"
        "```\n\n"
        "**类型转换：**\n"
        "```python\n"
        "int(\"42\")      # 字符串 → 整数\n"
        "str(3.14)      # 数字 → 字符串\n"
        "float(\"1.5\")   # 字符串 → 浮点数\n"
        "list(\"abc\")    # 字符串 → ['a', 'b', 'c']\n"
        "```\n\n"
        "**类型检查：** `type(x)` 查看类型，`isinstance(x, int)` 判断类型\n\n"
        "Python 是动态类型语言，变量不需要声明类型，但可以用 Type Hint 增加可读性：\n"
        "```python\n"
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
        "```",
    ),
    (
        ["环境", "安装", "python", "配置", "pip", "virtualenv", "venv", "conda", "搭建"],
        "## Python 环境搭建\n\n"
        "**1. 安装 Python**\n"
        "- 从 [python.org](https://www.python.org) 下载最新版（推荐 3.10+）\n"
        "- 安装时勾选 \"Add Python to PATH\"\n\n"
        "**2. 验证安装**\n"
        "```bash\n"
        "python --version\n"
        "pip --version\n"
        "```\n\n"
        "**3. 创建虚拟环境（推荐）**\n"
        "```bash\n"
        "python -m venv .venv         # 创建虚拟环境\n"
        "source .venv/bin/activate    # Linux/Mac 激活\n"
        ".venv\\Scripts\\activate       # Windows 激活\n"
        "pip install -r requirements.txt  # 安装依赖\n"
        "```\n\n"
        "**4. 推荐编辑器**\n"
        "- **VS Code** + Python 插件（免费，轻量）\n"
        "- **PyCharm**（功能强大，社区版免费）\n\n"
        "**5. 常用命令**\n"
        "```bash\n"
        "pip install requests   # 安装包\n"
        "pip freeze > requirements.txt  # 导出依赖\n"
        "```",
    ),
]


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "tutor_agent.md"


def load_tutor_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是答疑辅导助手，结合RAG知识库检索结果回答学生问题。"


def is_safe_question(question: str) -> bool:
    """检查问题是否安全。"""
    q_lower = question.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in q_lower:
            return False
    return True


def heuristic_answer(question: str) -> str:
    """星火未配置时的规则兜底答疑，覆盖常见编程主题。"""
    q_lower = question.lower()

    # 1. 问候/寒暄
    for keyword, answer in SAFE_ANSWERS.items():
        if keyword in q_lower:
            return answer

    # 2. 按主题关键词匹配（短关键词需匹配完整单词，避免子串误匹配）
    for keywords, answer in TOPIC_ANSWERS:
        for kw in keywords:
            if len(kw) <= 3 and kw.isascii():
                if re.search(r'\b' + re.escape(kw) + r'\b', q_lower):
                    return answer
            elif kw in q_lower or kw in question:
                return answer

    # 3. 上下文感知的默认回复（引用用户问题）
    short_q = question[:80] + ("..." if len(question) > 80 else "")
    return (
        f"关于「{short_q}」这个问题：\n\n"
        "目前我的 AI 模型服务正在配置中，暂时无法给出深度分析，但以下是一些通用建议：\n\n"
        "**1. 明确问题范围** — 试着将大问题拆分成小问题逐个击破\n"
        "**2. 查阅官方文档** — 该领域的官方文档是最权威的参考资料\n"
        "**3. 动手实践** — 通过实际操作验证想法是最有效的学习方式\n"
        "**4. 善用搜索** — 相关论坛和社区上有大量专业问答\n\n"
        "你也可以尝试用更具体的方式提问，比如：\n"
        "- 「xxx 的核心概念是什么？」\n"
        "- 「这个知识点有哪些常见误区？」\n"
        "- 「能否举例说明 xxx 的应用场景？」\n\n"
        "我会尽力为你提供帮助！"
    )


class TutorAgent(BaseAgent):
    """答疑辅导Agent：结合RAG知识库和星火大模型回答学生问题。"""

    name = "tutor"

    def __init__(self) -> None:
        self.spark = get_spark_client()
        self.retriever = KnowledgeRetriever()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        question = self._extract_question(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None

        # 从上游节点提取知识树和学习路径
        knowledge_tree = state.get("knowledge_tree", {})
        learning_path = state.get("learning_path", {})

        # 用户选择的模型
        model_id = state.get("model") or None

        # 提取对话历史（排除当前问题本身）
        conversation_history = self._extract_conversation_history(state, question)

        if not question.strip():
            return {"messages": [{"role": "assistant", "content": "我没有收到你的问题，请重新输入。"}]}

        if not is_safe_question(question):
            return {"messages": [{"role": "assistant", "content": "抱歉，我无法回答涉及敏感内容的问题。请换个话题。"}]}

        answer = await self._generate_answer(
            question, profile, knowledge_tree, learning_path, conversation_history,
            model=model_id,
        )

        return {
            "messages": [{"role": "assistant", "content": answer}],
        }

    async def run_stream(self, state: dict[str, Any]) -> AsyncIterator[str]:
        """流式输出：逐 token 返回回答内容，减少用户等待时间。"""
        question = self._extract_question(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None
        knowledge_tree = state.get("knowledge_tree", {})
        learning_path = state.get("learning_path", {})
        model_id = state.get("model") or None
        conversation_history = self._extract_conversation_history(state, question)

        if not question.strip():
            yield "我没有收到你的问题，请重新输入。"
            return

        if not is_safe_question(question):
            yield "抱歉，我无法回答涉及敏感内容的问题。请换个话题。"
            return

        if not self.spark.configured:
            yield heuristic_answer(question)
            return

        try:
            docs = await self.retriever.query(question, k=5)
            async for token in self._generate_with_spark_stream(
                question, docs, profile, knowledge_tree, learning_path, conversation_history,
                model=model_id,
            ):
                yield token
        except Exception as exc:
            logger.warning("星火流式答疑失败，使用规则兜底: %s", exc)
            yield heuristic_answer(question)

    async def _generate_with_spark_stream(
        self,
        question: str,
        docs: list[dict[str, Any]],
        profile: StudentProfile | None,
        knowledge_tree: dict[str, Any] | None = None,
        learning_path: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """流式调用星火大模型，逐 token 返回回答。"""
        system_prompt = load_tutor_prompt()

        context_parts: list[str] = []

        if profile:
            profile_lines = ["【学生画像】"]
            profile_lines.append(f"- 知识水平：{profile.knowledge_level}")
            profile_lines.append(f"- 学习风格：{profile.learning_style}")
            if profile.major:
                profile_lines.append(f"- 专业：{profile.major}")
            if profile.goal and profile.goal != "unknown":
                profile_lines.append(f"- 学习目标：{profile.goal}")
            if profile.weakness:
                profile_lines.append(f"- 薄弱点：{profile.weakness}")
            if profile.learning_goal_text:
                profile_lines.append(f"- 目标详情：{profile.learning_goal_text}")
            if profile.learning_base:
                profile_lines.append(f"- 学习基础：{profile.learning_base}")
            context_parts.append("\n".join(profile_lines))

        if docs:
            rag_lines = ["【知识库参考内容】"]
            for i, doc in enumerate(docs[:5], 1):
                content = doc.get("content", "").strip()
                if content:
                    truncated = content[:800] + ("..." if len(content) > 800 else "")
                    rag_lines.append(f"[片段{i}] {truncated}")
            if len(rag_lines) > 1:
                context_parts.append("\n".join(rag_lines))

        if knowledge_tree and knowledge_tree.get("nodes"):
            tree_lines = ["【知识结构】"]
            tree_lines.append(f"主题：{knowledge_tree.get('topic', '未知')}")
            for node in knowledge_tree.get("nodes", [])[:8]:
                title = node.get("title", "")
                children = node.get("children", [])
                if children:
                    tree_lines.append(f"- {title}：{', '.join(str(c) for c in children[:5])}")
                else:
                    tree_lines.append(f"- {title}")
            context_parts.append("\n".join(tree_lines))

        if learning_path and learning_path.get("steps"):
            path_lines = ["【学习路径】"]
            path_lines.append(f"路径名称：{learning_path.get('path_name', '未知')}")
            focus = learning_path.get("focus_areas", [])
            if focus:
                path_lines.append(f"重点方向：{', '.join(focus)}")
            context_parts.append("\n".join(path_lines))

        context_block = "\n\n".join(context_parts) if context_parts else ""

        user_prompt_parts = []
        if context_block:
            user_prompt_parts.append(context_block)
            user_prompt_parts.append("---")

        user_prompt_parts.append(f"【用户问题】\n{question}")

        level_desc = profile.knowledge_level if profile else "intermediate"
        user_prompt_parts.append(f"\n请根据以上信息，以{level_desc}水平来回答用户问题。")

        user_prompt = "\n\n".join(user_prompt_parts)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_prompt})

        async for token in self.spark.chat_stream(
            messages, temperature=0.3, max_tokens=4096, model=model,
        ):
            yield token

    def _extract_question(self, state: dict[str, Any]) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return state.get("user_input", "")

    def _extract_conversation_history(
        self, state: dict[str, Any], current_question: str
    ) -> list[dict[str, str]]:
        """提取对话历史，用于多轮对话上下文理解。"""
        messages = state.get("messages", [])
        history: list[dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "")
            content = str(msg.get("content", "")).strip()
            # 跳过空消息和当前问题
            if not content or content == current_question:
                continue
            # 只保留 user 和 assistant 消息（排除内部节点的 system 消息）
            if role in ("user", "assistant") and not msg.get("node"):
                history.append({"role": role, "content": content})
        # 最多保留最近 10 条对话（5轮）
        return history[-10:]

    async def _generate_answer(
        self,
        question: str,
        profile: StudentProfile | None,
        knowledge_tree: dict[str, Any] | None = None,
        learning_path: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        model: str | None = None,
    ) -> str:
        if self.spark.configured:
            try:
                # 增加 RAG 检索数量，获取更多上下文
                docs = await self.retriever.query(question, k=5)
                return await self._generate_with_spark(
                    question, docs, profile, knowledge_tree, learning_path, conversation_history,
                    model=model,
                )
            except Exception as exc:
                logger.warning("星火答疑失败，使用规则兜底: %s", exc)

        return heuristic_answer(question)

    async def _generate_with_spark(
        self,
        question: str,
        docs: list[dict[str, Any]],
        profile: StudentProfile | None,
        knowledge_tree: dict[str, Any] | None = None,
        learning_path: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        model: str | None = None,
    ) -> str:
        system_prompt = load_tutor_prompt()

        # 构建完整的上下文信息
        context_parts: list[str] = []

        # 1. 学生画像信息
        if profile:
            profile_lines = ["【学生画像】"]
            profile_lines.append(f"- 知识水平：{profile.knowledge_level}")
            profile_lines.append(f"- 学习风格：{profile.learning_style}")
            if profile.major:
                profile_lines.append(f"- 专业：{profile.major}")
            if profile.goal and profile.goal != "unknown":
                profile_lines.append(f"- 学习目标：{profile.goal}")
            if profile.weakness:
                profile_lines.append(f"- 薄弱点：{profile.weakness}")
            if profile.learning_goal_text:
                profile_lines.append(f"- 目标详情：{profile.learning_goal_text}")
            if profile.learning_base:
                profile_lines.append(f"- 学习基础：{profile.learning_base}")
            context_parts.append("\n".join(profile_lines))

        # 2. RAG 知识库检索结果（增加上下文长度，不再截断到 300 字）
        if docs:
            rag_lines = ["【知识库参考内容】"]
            for i, doc in enumerate(docs[:5], 1):
                content = doc.get("content", "").strip()
                if content:
                    # 每个片段保留最多 800 字符，比之前 300 字符大幅增加
                    truncated = content[:800] + ("..." if len(content) > 800 else "")
                    rag_lines.append(f"[片段{i}] {truncated}")
            if len(rag_lines) > 1:
                context_parts.append("\n".join(rag_lines))

        # 3. 知识树结构（来自 knowledge agent 的上游分析）
        if knowledge_tree and knowledge_tree.get("nodes"):
            tree_lines = ["【知识结构】"]
            tree_lines.append(f"主题：{knowledge_tree.get('topic', '未知')}")
            for node in knowledge_tree.get("nodes", [])[:8]:
                title = node.get("title", "")
                children = node.get("children", [])
                if children:
                    tree_lines.append(f"- {title}：{', '.join(str(c) for c in children[:5])}")
                else:
                    tree_lines.append(f"- {title}")
            context_parts.append("\n".join(tree_lines))

        # 4. 学习路径（来自 planner agent 的上游分析）
        if learning_path and learning_path.get("steps"):
            path_lines = ["【学习路径】"]
            path_lines.append(f"路径名称：{learning_path.get('path_name', '未知')}")
            focus = learning_path.get("focus_areas", [])
            if focus:
                path_lines.append(f"重点方向：{', '.join(focus)}")
            context_parts.append("\n".join(path_lines))

        context_block = "\n\n".join(context_parts) if context_parts else ""

        # 构建用户消息：上下文 + 问题
        user_prompt_parts = []
        if context_block:
            user_prompt_parts.append(context_block)
            user_prompt_parts.append("---")

        user_prompt_parts.append(f"【用户问题】\n{question}")

        level_desc = profile.knowledge_level if profile else "intermediate"
        user_prompt_parts.append(f"\n请根据以上信息，以{level_desc}水平来回答用户问题。")

        user_prompt = "\n\n".join(user_prompt_parts)

        # 构建消息列表：system + 对话历史 + 当前问题
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # 注入对话历史（多轮对话支持）
        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_prompt})

        # 使用更高的 max_tokens 和适中 temperature 提升回答质量
        return await self.spark.chat(messages, temperature=0.3, max_tokens=4096, model=model)