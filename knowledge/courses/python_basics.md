# Python 程序设计基础

## 第一章 Python 简介

Python 是一种解释型、面向对象的高级编程语言，语法简洁，适合初学者与科研、Web、数据分析等场景。

## 第二章 变量与数据类型

- 整型 `int`、浮点 `float`、字符串 `str`、布尔 `bool`
- 类型转换：`int()`, `float()`, `str()`
- 输入输出：`input()`, `print()`

## 第三章 条件与分支

使用 `if / elif / else` 实现分支逻辑。注意缩进必须使用 4 个空格。

```python
score = 85
if score >= 90:
    print("优秀")
elif score >= 60:
    print("及格")
else:
    print("不及格")
```

## 第四章 循环结构

### for 循环

遍历序列：`for i in range(5):`

### while 循环

在条件为真时重复执行，注意避免死循环。

### 常见易错点

- `range` 左闭右开
- 循环中修改列表需小心索引越界

## 第五章 函数

函数使用 `def` 定义，可带参数与返回值。作用域分为局部变量与全局变量。

```python
def add(a, b):
    return a + b
```

## 第六章 面向对象（简介）

类与对象、构造函数 `__init__`、实例方法与属性，为后续软件工程课程打基础。
