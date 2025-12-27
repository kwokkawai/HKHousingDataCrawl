# 香港住宅房产数据爬虫项目

## 项目概述

本项目旨在开发一个用于爬取香港住宅房产数据的程序，通过系统化的可行性测试和效率评估，确定最优的爬取策略。项目使用 Crawl4AI 框架进行网页爬取，支持异步处理和多种数据提取策略。

### 目标网站

本项目针对以下三个香港主要房产网站进行数据爬取：

1. **中原地产** (hk.centanet.com)

   - 香港最大的地产代理之一
   - URL: https://hk.centanet.com/findproperty/list/buy

2. **28Hse.com** (www.28hse.com)

   - 香港知名房产信息平台
   - URL: https://www.28hse.com/buy/apartment（買樓）或 https://www.28hse.com/rent/apartment（租樓）

3. **利嘉阁** (www.ricacorp.com)
   - 香港主要地产代理公司
   - URL: https://www.ricacorp.com/zh-hk

## 技术栈

- **Python 3.8+**
- **Crawl4AI**: 强大的网页爬取框架，支持 JavaScript 渲染
- **Playwright**: 浏览器自动化（Crawl4AI 依赖）
- **asyncio**: 异步处理，提高爬取效率
- **BeautifulSoup4**: HTML 解析（可选，用于数据提取）
- **JSON/CSV**: 数据存储格式
- **matplotlib**: 结果可视化（可选）
- **psutil**: 系统监控（可选，用于效率测试）

## 项目结构

```
code/
├── README.md                    # 项目文档
├── requirements.txt             # Python依赖包列表
├── check_dependencies.py        # 依赖检查脚本
│
├── sites_config.py              # 网站配置文件
├── data_models.py               # 数据模型定义
│
├── feasibility_test.py          # 可行性测试程序
├── efficiency_test.py           # 效率测试程序
├── visualize_results.py         # 结果可视化脚本
│
├── centanet_explorer.py        # 中原地产页面结构探索脚本
├── centanet_crawler.py         # 中原地产爬虫（已实现）
├── 28hse_explorer.py           # 28Hse.com 页面结构探索脚本
├── 28hse_crawler.py            # 28Hse.com 爬虫（已实现）
├── ricacorp_explorer.py        # 利嘉阁页面结构探索脚本
├── ricacorp_crawler.py         # 利嘉阁爬虫（已实现）
│
├── results/                     # 测试结果目录
│   ├── feasibility_report.json  # 可行性测试报告
│   ├── efficiency_report.json   # 效率测试报告
│   ├── comprehensive_report.txt # 综合报告
│   └── test_results_charts.png # 可视化图表
│
├── exploration/                 # 页面结构探索结果
│   ├── centanet_list_page.html # 中原地产列表页HTML
│   ├── centanet_list_page.md   # 中原地产列表页Markdown
│   └── centanet_analysis_summary.json # 分析摘要
│
├── data/                        # 爬取的数据目录
│   ├── centanet/                # 中原地产数据
│   │   ├── properties_*.json    # JSON格式数据
│   │   ├── properties_*.csv     # CSV格式数据
│   │   └── failed_urls_*.txt   # 失败的URL列表
│   ├── 28hse/                   # 28Hse.com 数据
│   │   ├── properties_*.json    # JSON格式数据
│   │   ├── properties_*.csv     # CSV格式数据
│   │   └── failed_urls_*.txt   # 失败的URL列表
│   └── ricacorp/                # 利嘉阁数据
│       ├── properties_*.json    # JSON格式数据
│       ├── properties_*.csv     # CSV格式数据
│       └── failed_urls_*.txt   # 失败的URL列表
│
└── samples/                     # Crawl4AI示例代码
    ├── c4ai.py                  # Crawl4AI 基础示例
    ├── sample_crawl4ai.py       # 综合示例
    ├── deep_crawl_example.py    # 深度爬取示例
    └── multi_level_crawl_sample.py # 多级爬取示例
```

## 安装和配置

### 1. 环境要求

- Python 3.8 或更高版本
- pip 包管理器

### 2. 安装依赖

#### 方法一：使用 requirements.txt（推荐）

```bash
# 激活虚拟环境（如果使用）
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装所有依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器（必需！）
playwright install
# 或使用 Python 模块方式
python -m playwright install
```

#### 方法二：手动安装

```bash
# 激活虚拟环境（如果使用）
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装核心依赖（必需）
pip install crawl4ai

# 安装可选依赖
pip install psutil          # 用于内存监控（效率测试）
pip install matplotlib      # 用于结果可视化

# 安装 Playwright 浏览器（必需！）
playwright install
# 或使用 Python 模块方式
python -m playwright install
```

#### 重要：安装 Playwright 浏览器

**Crawl4AI 依赖 Playwright 来运行浏览器**，安装 Python 包后 必须单独安装浏览器：

```bash
# 方式1：使用 playwright 命令（如果已添加到 PATH）
playwright install

# 方式2：使用 Python 模块方式（推荐）
python -m playwright install

# 方式3：在虚拟环境中使用
./venv/bin/python -m playwright install
```

**注意**：

- 首次安装 Playwright 浏览器需要下载约 300-500MB 的浏览器文件
- 如果遇到权限问题，可能需要使用 `sudo`（Linux/Mac）或管理员权限（Windows）
- 安装完成后，浏览器文件会存储在系统缓存目录中

#### 验证依赖安装

运行依赖检查脚本验证所有依赖是否正确安装：

```bash
python check_dependencies.py
```

该脚本会检查：

- ✓ 必需依赖：crawl4ai（核心爬虫框架）
- ○ 可选依赖：psutil（内存监控）、matplotlib（可视化）

**注意**：依赖检查脚本不会验证 Playwright 浏览器是否已安装。如果测试时遇到 "Executable doesn't exist" 错误，请运行 `playwright install`。

### 3. 配置说明

编辑 `sites_config.py` 文件，根据实际情况调整各网站的配置参数，包括：

- URL 模式
- CSS 选择器
- 请求头设置
- 反爬虫策略

## 使用方法

### 可行性测试

运行可行性测试程序，检查目标网站的爬取可行性：

```bash
python feasibility_test.py
```

测试将检查：

- 网站可访问性
- 反爬虫机制（验证码、IP 限制等）
- 页面结构可解析性
- JavaScript 渲染需求
- 数据提取难度
- 分页机制
- 请求频率限制

测试结果将保存到 `results/feasibility_report.json`

### 效率测试

运行效率测试程序，评估爬取性能：

```bash
python efficiency_test.py
```

测试将评估：

- 单页爬取时间
- 并发性能
- 数据提取速度
- 内存使用情况
- 成功率
- 错误处理能力

测试结果将保存到 `results/efficiency_report.json`

### 结果可视化

生成测试结果的可视化报告：

```bash
python visualize_results.py
```

将生成对比图表和总结报告。

### 爬取房产数据

#### 1. 探索页面结构（可选）

在开始爬取之前，可以先运行探索脚本了解页面结构：

```bash
# 探索中原地产页面结构
python centanet_explorer.py

# 探索 28Hse.com 页面结构
python 28hse_explorer.py

# 探索利嘉阁页面结构
python ricacorp_explorer.py
```

该脚本会：

- 访问目标网站
- 分析页面 HTML 结构
- 查找价格、面积、链接等关键信息
- 保存 HTML 和 Markdown 文件到 `exploration/` 目录
- 生成分析摘要报告

#### 2. 爬取房产数据

##### 2.1 爬取中原地产数据

运行爬虫程序爬取房产数据：

```bash
# 基本用法（默认：2页，最多50个房产）
python centanet_crawler.py

# 自定义参数
python centanet_crawler.py --max-pages 20 --max-properties 120

# 按类别和地区筛选
python centanet_crawler.py --category buy --region 新界西
python centanet_crawler.py --category transaction --region 九龍
```

##### 2.2 爬取 28Hse.com 数据

运行 28Hse.com 爬虫程序：

```bash
# 基本用法（默认：2页，最多50个房产，只爬取apartment类型）
python 28hse_crawler.py

# 自定义参数
python 28hse_crawler.py --max-pages 10 --max-properties 100

# 按类别筛选（buy/買樓 或 rent/租樓）
python 28hse_crawler.py --category buy --max-pages 5
python 28hse_crawler.py --category rent --max-pages 5

# 按地区筛选（港島、九龍、新界、離島）
python 28hse_crawler.py --region 九龍 --max-pages 5
python 28hse_crawler.py --region 新界 --max-pages 5

# 组合使用：爬取新界地区的買樓数据
python 28hse_crawler.py --category buy --region 新界 --max-pages 5
```

##### 2.3 爬取利嘉阁数据

运行利嘉阁爬虫程序：

```bash
# 基本用法（默认：2页，最多50个房产）
python ricacorp_crawler.py

# 自定义参数
python ricacorp_crawler.py --max-pages 10 --max-properties 100

# 按类别和地区筛选（目前支持类别和地区筛选）
python ricacorp_crawler.py --category buy --region 新界西 --max-pages 5
```

**中原地产爬虫功能**：

- ✅ **AJAX 分页支持**：自动处理 JavaScript 驱动的分页，通过模拟点击分页按钮实现翻页
- ✅ **多策略数据提取**：采用多种方法提取数据，提高成功率
  - 从 JavaScript `__NUXT__` 对象中提取面包屑路径（最可靠）
  - 从 HTML 元素中提取
  - 从正则表达式匹配中提取
  - 从 URL 中推断
- ✅ **完整字段提取**：提取房产的所有关键信息
  - 基本信息：标题、价格、面积、月供
  - 位置信息：区域、地区、街道、地址
  - 层级导航：类别、大区、二级区域、子区域、屋苑名称、完整面包屑路径
  - 房产属性：房型、卧室数、浴室数、楼层、楼龄、朝向
  - 其他信息：描述、图片、设施、发布日期等
- ✅ **类别和地区筛选**：支持按类别（買樓/租樓/成交）和地区（港島/九龍/新界東/新界西）筛选
- ✅ **并发爬取**：支持异步并发爬取详情页，提高效率
- ✅ **自动保存**：自动保存为 JSON 和 CSV 格式
- ✅ **错误处理**：记录失败的 URL，支持断点续传

**28Hse.com 爬虫功能**：

- ✅ **Apartment 类型筛选**：只爬取住宅（apartment）类型，自动排除写字楼、商铺、车位等其他类型
- ✅ **列表页地址提取**：从列表页提取地址信息，补充详情页的 address 字段
- ✅ **多策略数据提取**：采用多种方法提取数据，提高成功率
  - 从 HTML 面包屑导航元素中提取
  - 从页面文本中通过正则表达式提取
  - 从 URL 中推断类别信息
- ✅ **完整字段提取**：提取房产的所有关键信息
  - 基本信息：标题、价格、面积
  - 位置信息：区域、地区、街道、地址（支持从列表页和详情页提取）
  - 层级导航：类别（住宅售盤/住宅租盤）、大区（港島/九龍/新界/離島）、二级区域、屋苑名称、完整面包屑路径
  - 房产属性：房型、卧室数、楼层、朝向
  - 其他信息：描述、图片等
- ✅ **类别和地区筛选**：支持按类别（buy/買樓、rent/租樓）和地区（港島、九龍、新界、離島）筛选
- ✅ **字段映射优化**：正确解析 28hse 特有的 breadcrumb 格式，准确映射 category、region、district_level2、estate_name 等字段
- ✅ **并发爬取**：支持异步并发爬取详情页，提高效率
- ✅ **自动保存**：自动保存为 JSON 和 CSV 格式
- ✅ **错误处理**：完善的错误处理和重试机制，记录失败的 URL

**利嘉阁爬虫功能**：

- ✅ **列表页爬取**：支持爬取利嘉阁的房产列表页
- ✅ **详情页爬取**：并发爬取详情页，提高效率
- ✅ **URL 规范化**：自动规范化 URL，确保 URL 格式一致（去除百分号编码）
- ✅ **多策略数据提取**：采用多种方法提取数据，提高成功率
  - 从 HTML 面包屑导航元素提取（优先）
  - 从 URL slug 推断（备用）
- ✅ **完整字段提取**：提取房产的所有关键信息
  - 基本信息：标题、价格、面积
  - 位置信息：区域、地区、街道、地址
  - 层级导航：类别（二手真盤源）、大区（港島/九龍/新界東/新界西）、二级区域、屋苑名称、完整面包屑路径
  - 房产属性：房型、卧室数、楼层、朝向
  - 其他信息：描述、图片等
- ✅ **面包屑去重优化**：自动去除重复的面包屑项（例如：屯門南 > 屯門南），过滤纯「X座」格式的项（例如：j座、J座），因为它们通常已经包含在上一项中（例如：旭麟閣 (J座)）
- ✅ **字段映射优化**：正确解析利嘉阁特有的 breadcrumb 格式（主頁 > 二手真盤源 > 新界西 > 屯門 > 屯門南 > 兆麟苑 > 旭麟閣 (J座)），准确映射 category、region、district、district_level2、estate_name 等字段
- ✅ **URL 过滤**：严格过滤无效 URL（例如：`/property/list/`、`buy;postTags=...`），只提取有效的详情页 URL
- ✅ **并发爬取**：支持异步并发爬取详情页，提高效率
- ✅ **自动保存**：自动保存为 JSON 和 CSV 格式
- ✅ **错误处理**：完善的错误处理和重试机制，记录失败 URL

**输出文件**：

**中原地产**：
- `data/centanet/properties_YYYYMMDD_HHMMSS.json` - JSON 格式数据
- `data/centanet/properties_YYYYMMDD_HHMMSS.csv` - CSV 格式数据
- `data/centanet/failed_urls_YYYYMMDD_HHMMSS.txt` - 失败的 URL 列表

**28Hse.com**：
- `data/28hse/properties_YYYYMMDD_HHMMSS.json` - JSON 格式数据
- `data/28hse/properties_YYYYMMDD_HHMMSS.csv` - CSV 格式数据
- `data/28hse/failed_urls_YYYYMMDD_HHMMSS.txt` - 失败的 URL 列表

**利嘉阁**：
- `data/ricacorp/properties_YYYYMMDD_HHMMSS.json` - JSON 格式数据
- `data/ricacorp/properties_YYYYMMDD_HHMMSS.csv` - CSV 格式数据
- `data/ricacorp/failed_urls_YYYYMMDD_HHMMSS.txt` - 失败的 URL 列表

**命令行参数**：

**中原地产爬虫**：
```bash
python centanet_crawler.py [选项]

选项：
  --max-pages N          最大爬取页数（默认：2）
  --max-properties N     最大爬取房产数量（默认：50）
  --category CATEGORY    类别筛选：buy/買樓, rent/租樓, transaction/成交
  --region REGION        地区筛选：港島, 九龍, 新界東, 新界西 等
```

**28Hse.com 爬虫**：
```bash
python 28hse_crawler.py [选项]

选项：
  --max-pages N          最大爬取页数（默认：2）
  --max-properties N     最大爬取房产数量（默认：50）
  --category CATEGORY    类别筛选：buy/買樓, rent/租樓
  --region REGION        地区筛选：港島, 九龍, 新界, 離島 等
```

**利嘉阁爬虫**：
```bash
python ricacorp_crawler.py [选项]

选项：
  --max-pages N          最大爬取页数（默认：2）
  --max-properties N     最大爬取房产数量（默认：50）
  --category CATEGORY    类别筛选（可选）
  --region REGION        地区筛选（可选）
```

**示例**：

**中原地产**：
```bash
# 爬取前10页，最多100个房产
python centanet_crawler.py --max-pages 10 --max-properties 100

# 只爬取新界西的買樓数据
python centanet_crawler.py --category buy --region 新界西 --max-pages 5

# 爬取九龍的成交记录
python centanet_crawler.py --category transaction --region 九龍 --max-pages 20
```

**28Hse.com**：
```bash
# 爬取前10页，最多100个房产
python 28hse_crawler.py --max-pages 10 --max-properties 100

# 只爬取九龍地区的買樓数据
python 28hse_crawler.py --category buy --region 九龍 --max-pages 5

# 爬取新界地区的租樓数据
python 28hse_crawler.py --category rent --region 新界 --max-pages 5
```

**利嘉阁**：
```bash
# 爬取前10页，最多100个房产
python ricacorp_crawler.py --max-pages 10 --max-properties 100

# 只爬取新界西的房产数据
python ricacorp_crawler.py --region 新界西 --max-pages 5
```

#### 3. 查看爬取结果

爬取完成后，可以查看保存的数据文件：

```bash
# 查看中原地产JSON数据
cat data/centanet/properties_*.json | python -m json.tool | head -50

# 查看28Hse.com JSON数据
cat data/28hse/properties_*.json | python -m json.tool | head -50

# 查看利嘉阁 JSON数据
cat data/ricacorp/properties_*.json | python -m json.tool | head -50

# 查看CSV数据（如果安装了pandas）
python -c "import pandas as pd; df = pd.read_csv('data/centanet/properties_*.csv'); print(df.head())"
python -c "import pandas as pd; df = pd.read_csv('data/28hse/properties_*.csv'); print(df.head())"
python -c "import pandas as pd; df = pd.read_csv('data/ricacorp/properties_*.csv'); print(df.head())"
```

## 可行性测试说明

可行性测试程序会为每个网站生成一个评分报告，包括：

- **可访问性评分** (0-10): 网站是否可正常访问
- **反爬虫难度** (0-10): 反爬虫机制的复杂程度（分数越高越难）
- **数据提取难度** (0-10): 提取关键数据的难易程度（分数越高越难）
- **综合可行性评分** (0-10): 整体爬取可行性（分数越高越可行）

### 关键字段提取

爬虫会提取以下关键字段：

**基本信息**：

- `property_id`: 房产唯一标识符
- `url`: 详情页 URL
- `title`: 房产标题（如"瓏門 1 期 2 座 低層 H 室"）
- `source`: 数据来源（固定为"centanet"）

**价格信息**：

- `price`: 价格（港币，浮点数）
- `price_display`: 价格显示文本（如"998 萬"）
- `monthly_mortgage_payment`: 月供（如"$30,885"）

**面积信息**：

- `area`: 面积（平方英尺，浮点数）
- `area_display`: 面积显示文本

**位置信息**：

- `district`: 区域（如"屯門"）
- `area_name`: 地区名称
- `street`: 街道
- `address`: 完整地址

**层级导航信息（面包屑）**：

- `category`: 类别（如"買樓"、"租樓"、"成交"）
- `region`: 大区（如"新界西"、"港島"、"九龍"）
- `district_level2`: 二级区域（如"屯門市中心"、"荃灣 | 麗城"）
- `sub_district`: 子区域（如"屯門新墟"、"荃灣西"）
- `estate_name`: 屋苑名称（如"瓏門"、"海之戀"）
- `breadcrumb`: 完整面包屑路径（用">"分隔，如"主頁 > 買樓 > 新界西 > 屯門 > 屯門市中心 > 瓏門"）

**房产属性**：

- `property_type`: 房型（如"2 房"）
- `bedrooms`: 卧室数
- `bathrooms`: 浴室数
- `floor`: 楼层
- `building_age`: 楼龄
- `orientation`: 朝向

**其他信息**：

- `description`: 详细描述
- `images`: 图片 URL 列表
- `facilities`: 设施列表
- `post_date`: 发布日期
- `update_date`: 更新时间
- `crawl_date`: 爬取时间

## 效率评估指标

效率测试会评估以下指标：

1. **响应时间**

   - 平均响应时间
   - 最小/最大响应时间
   - 响应时间分布

2. **并发性能**

   - 并发爬取速度
   - 并发成功率
   - 资源利用率

3. **数据提取效率**

   - 提取时间
   - 提取成功率
   - 数据完整性

4. **资源使用**

   - 内存占用
   - CPU 使用率
   - 网络带宽

5. **稳定性**
   - 成功率
   - 错误率
   - 重试次数

## 注意事项

### 法律和道德

1. **遵守 robots.txt**: 尊重网站的 robots.txt 文件
2. **合理请求频率**: 避免对目标网站造成过大负担
3. **数据使用**: 仅用于个人学习或研究目的
4. **版权尊重**: 遵守数据版权和使用条款

### 技术注意事项

1. **反爬虫应对**: 某些网站可能有反爬虫机制，需要适当处理
2. **JavaScript 渲染**: 部分网站需要 JavaScript 渲染，Crawl4AI 支持此功能
3. **数据更新**: 网站结构可能变化，需要定期更新选择器
4. **错误处理**: 实现完善的错误处理和重试机制

### 最佳实践

1. **礼貌爬取**: 在请求之间添加适当延迟
2. **用户代理**: 使用合理的 User-Agent
3. **会话管理**: 合理使用 cookies 和会话
4. **数据验证**: 对提取的数据进行验证和清洗

## 程序设计提示词

以下是一个详细的提示词模板，可用于指导后续的程序设计：

### 数据模型设计

```
设计一个完整的香港房产数据模型，包括以下字段：

必需字段：
- property_id: 房产唯一标识符
- source: 数据来源网站（centanet/28hse/ricacorp）
- title: 房产标题
- price: 价格（港币）
- area: 面积（平方英尺）
- location: 位置（区域、街道、具体地址）
- property_type: 房型（一房、两房、三房等）
- floor: 楼层信息
- orientation: 朝向
- post_date: 发布日期
- url: 详情页URL

可选字段：
- description: 详细描述
- images: 图片URL列表
- facilities: 周边设施
- transportation: 交通信息
- agent_info: 经纪人信息
- view_count: 浏览次数
- update_date: 最后更新时间

数据验证规则：
- 价格必须为正数
- 面积必须为正数
- 位置不能为空
- URL必须有效
```

### 爬虫架构设计

```
设计一个可扩展的爬虫架构，包括以下组件：

1. 爬虫核心模块 (CrawlerCore)
   - 使用 Crawl4AI 的 AsyncWebCrawler
   - 支持异步并发爬取
   - 实现请求队列管理
   - 支持重试机制

2. 网站适配器模块 (SiteAdapter)
   - 为每个网站创建独立的适配器类
   - 实现统一的接口（extract_list, extract_detail）
   - 处理网站特定的反爬虫机制
   - 解析网站特定的HTML结构

3. 数据提取模块 (DataExtractor)
   - 使用 CSS 选择器或 XPath
   - 支持多种提取策略（JsonCssExtractionStrategy）
   - 数据清洗和标准化
   - 数据验证

4. 数据存储模块 (DataStorage)
   - 支持多种存储格式（JSON、CSV、数据库）
   - 实现去重机制
   - 支持增量更新
   - 数据备份

5. 任务调度模块 (TaskScheduler)
   - 支持定时爬取
   - 任务优先级管理
   - 失败任务重试
   - 进度跟踪

6. 监控和日志模块 (Monitor)
   - 爬取进度监控
   - 错误日志记录
   - 性能指标收集
   - 告警机制
```

### 数据存储方案

```
设计数据存储方案，支持以下需求：

1. 文件存储
   - JSON格式：便于读取和调试
   - CSV格式：便于Excel分析
   - 按日期和网站分类存储

2. 数据库存储（可选）
   - SQLite：轻量级，适合小规模数据
   - PostgreSQL：适合大规模数据，支持复杂查询
   - 表结构设计：
     * properties: 房产主表
     * price_history: 价格历史记录
     * images: 图片信息
     * facilities: 设施信息

3. 数据去重
   - 基于 property_id 和 source 组合
   - 基于 URL 去重
   - 基于位置和价格相似度去重

4. 增量更新
   - 记录最后爬取时间
   - 只爬取新增或更新的房产
   - 价格变化追踪
```

### 错误处理和重试机制

```
实现完善的错误处理：

1. 错误分类
   - 网络错误（超时、连接失败）
   - HTTP错误（404、500、403）
   - 解析错误（HTML结构变化）
   - 反爬虫错误（验证码、IP封禁）

2. 重试策略
   - 指数退避重试
   - 最大重试次数限制
   - 不同类型错误的不同重试策略
   - 记录失败原因

3. 错误恢复
   - 保存爬取进度
   - 支持断点续传
   - 失败URL记录和后续处理
```

### 速率限制和礼貌爬取

```
实现礼貌爬取机制：

1. 请求速率控制
   - 每个网站独立的速率限制
   - 使用 asyncio.Semaphore 控制并发数
   - 请求间隔控制（随机延迟）

2. 用户代理轮换
   - 多个 User-Agent 轮换使用
   - 模拟真实浏览器行为

3. Cookie 管理
   - 合理使用 cookies
   - 会话保持

4. 请求头配置
   - Referer 设置
   - Accept 头设置
   - 其他必要的请求头
```

### 数据清洗和验证

```
实现数据清洗和验证：

1. 数据清洗
   - 去除HTML标签
   - 统一单位（面积、价格）
   - 标准化格式（日期、数字）
   - 处理特殊字符

2. 数据验证
   - 必填字段检查
   - 数据类型验证
   - 数值范围检查
   - URL有效性检查

3. 数据标准化
   - 位置名称标准化（统一区域名称）
   - 房型标准化
   - 价格单位统一
   - 日期格式统一
```

## 项目状态

### 已完成

- ✅ **可行性测试**: 完成三个目标网站的可行性测试
- ✅ **效率测试**: 完成爬取性能评估
- ✅ **中原地产爬虫**: 已实现并全面优化
  - ✅ **列表页爬取**：支持買樓、租樓、成交三种类别
  - ✅ **AJAX 分页支持**：通过 JavaScript 模拟点击实现翻页，支持多页爬取
  - ✅ **详情页爬取**：并发爬取详情页，提高效率
  - ✅ **多策略数据提取**：
    - 从 JavaScript `__NUXT__` 对象提取面包屑（最可靠）
    - 从 HTML 元素提取
    - 从正则表达式匹配提取
    - 从 URL 推断
  - ✅ **完整字段提取**：提取所有关键信息，包括价格、面积、位置、面包屑导航、房产属性等
  - ✅ **面包屑字段映射**：正确解析 category、region、district_level2、sub_district、estate_name
  - ✅ **类别和地区筛选**：支持按类别和地区筛选数据
  - ✅ **数据保存**：自动保存为 JSON 和 CSV 格式
  - ✅ **错误处理**：记录失败 URL，支持断点续传
  - ✅ **代码优化**：清理冗余代码，添加详细注释，提高可维护性
- ✅ **28Hse.com 爬虫**: 已实现并全面优化
  - ✅ **列表页爬取**：支持買樓、租樓两种类别，只爬取 apartment 类型
  - ✅ **分页支持**：支持 URL 参数分页和 AJAX 分页
  - ✅ **详情页爬取**：并发爬取详情页，提高效率
  - ✅ **列表页地址提取**：从列表页提取地址信息，补充详情页的 address 字段
  - ✅ **多策略数据提取**：
    - 从 HTML 面包屑导航元素提取
    - 从页面文本中通过正则表达式提取
    - 从 URL 中推断类别信息
  - ✅ **完整字段提取**：提取所有关键信息，包括价格、面积、位置、面包屑导航、房产属性等
  - ✅ **字段映射优化**：正确解析 28hse 特有的 breadcrumb 格式（主頁 > 地產主頁 > 住宅售盤 > ...）
  - ✅ **类别和地区筛选**：支持按类别（buy/rent）和地区（港島/九龍/新界/離島）筛选数据
  - ✅ **数据保存**：自动保存为 JSON 和 CSV 格式
- ✅ **错误处理**：完善的错误处理和重试机制，记录失败 URL
- ✅ **代码优化**：添加详细注释，提高可维护性
- ✅ **利嘉阁爬虫**: 已实现并全面优化
  - ✅ **列表页爬取**：支持爬取利嘉阁的房产列表页
  - ✅ **详情页爬取**：并发爬取详情页，提高效率
  - ✅ **URL 规范化**：自动规范化 URL，确保 URL 格式一致（去除百分号编码）
  - ✅ **多策略数据提取**：
    - 从 HTML 面包屑导航元素提取（优先）
    - 从 URL slug 推断（备用）
  - ✅ **完整字段提取**：提取所有关键信息，包括价格、面积、位置、面包屑导航、房产属性等
  - ✅ **面包屑去重优化**：自动去除重复的面包屑项，过滤纯「X座」格式的项
  - ✅ **字段映射优化**：正确解析利嘉阁特有的 breadcrumb 格式，准确映射 category、region、district、district_level2、estate_name 等字段
  - ✅ **URL 过滤**：严格过滤无效 URL，只提取有效的详情页 URL
  - ✅ **数据保存**：自动保存为 JSON 和 CSV 格式
  - ✅ **错误处理**：完善的错误处理和重试机制，记录失败 URL
  - ✅ **代码优化**：添加详细注释，提高可维护性

### 进行中

（暂无）

### 计划中
2. **数据存储优化**: 实现数据库存储和查询功能
3. **数据清洗**: 实现数据标准化和验证
4. **定时任务**: 实现定时自动爬取
5. **数据可视化**: 开发数据分析和可视化功能
6. **API 接口**: 提供数据查询 API
7. **Web 界面**: 开发简单的 Web 界面查看数据
8. **增量更新**: 实现增量爬取，只爬取新增或更新的房产
9. **价格追踪**: 实现价格变化追踪和历史记录

## 贡献指南

欢迎提交 Issue 和 Pull Request 来改进本项目。

## 许可证

本项目仅供学习和研究使用。请遵守目标网站的使用条款和相关法律法规。

## 联系方式

如有问题或建议，请通过 Issue 联系。

## 技术实现细节

### AJAX 分页处理

Centanet 网站使用 JavaScript 驱动的 AJAX 分页，URL 不变，需要通过模拟用户点击分页按钮来加载内容。爬虫实现：

1. **浏览器会话管理**：使用`session_id`维护同一浏览器会话，确保分页状态持续
2. **JavaScript 执行**：通过执行 JavaScript 代码查找并点击对应的页码按钮
3. **内容等待**：等待 AJAX 内容加载完成后再提取数据
4. **Element UI 支持**：针对 Centanet 使用的 Element UI 分页组件进行优化

### 多策略数据提取

为提高数据提取的准确性和可靠性，爬虫采用多策略提取方法：

1. **JavaScript 路径提取**（优先级最高）：

   - 从`window.__NUXT__.data`中的`paths`数组提取面包屑
   - 这是最可靠的方法，因为数据来自网站的内部状态

2. **HTML 元素提取**：

   - 从页面中的面包屑导航元素提取
   - 使用 CSS 选择器定位元素

3. **正则表达式匹配**：

   - 从页面文本中通过正则表达式匹配面包屑模式
   - 支持多种格式的面包屑结构

4. **URL 推断**：
   - 从 URL 路径中提取房产名称等信息
   - 作为备用方法

### 面包屑字段映射

爬虫会从完整的面包屑路径中解析各个字段：

- **格式**：`主頁 > 買樓 > 新界西 > 屯門 > 屯門市中心 > 瓏門`
- **映射规则**：
  - `category`: 第 2 个字符串（移除"主頁"后索引 0）
  - `region`: 第 3 个字符串（索引 1）
  - `district_level2`: 第 4 个字符串（索引 2）
  - `sub_district`: 第 5 个字符串（索引 3）
  - `estate_name`: 最后一个字符串

### 数据验证和清理

- 过滤无效值（如"屋苑"、"主頁"等）
- 验证数据完整性
- 设置合理的默认值
- 处理特殊字符和格式

---

**最后更新**: 2025 年 12 月

## 快速开始

1. **安装依赖**：

   ```bash
   pip install -r requirements.txt
   python -m playwright install
   ```

2. **验证安装**：

   ```bash
   python check_dependencies.py
   ```

3. **运行测试**（可选）：

   ```bash
   python feasibility_test.py
   python efficiency_test.py
   ```

4. **开始爬取**：

   ```bash
   # 中原地产 - 基本用法（默认：2页，最多50个房产）
   python centanet_crawler.py

   # 中原地产 - 自定义参数
   python centanet_crawler.py --max-pages 20 --max-properties 120

   # 中原地产 - 按类别和地区筛选
   python centanet_crawler.py --category buy --region 新界西

   # 28Hse.com - 基本用法（默认：2页，最多50个房产，只爬取apartment）
   python 28hse_crawler.py

   # 28Hse.com - 按类别和地区筛选
   python 28hse_crawler.py --category buy --region 九龍 --max-pages 5

   # 利嘉阁 - 基本用法（默认：2页，最多50个房产）
   python ricacorp_crawler.py

   # 利嘉阁 - 自定义参数
   python ricacorp_crawler.py --max-pages 10 --max-properties 100
   ```

5. **查看结果**：
   - 中原地产数据文件：`data/centanet/properties_*.json` 和 `properties_*.csv`
   - 28Hse.com 数据文件：`data/28hse/properties_*.json` 和 `properties_*.csv`
   - 利嘉阁数据文件：`data/ricacorp/properties_*.json` 和 `properties_*.csv`
   - 失败 URL：`data/{site}/failed_urls_*.txt`
   - 测试报告：`results/`
