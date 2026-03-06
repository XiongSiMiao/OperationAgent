# 生产运营数字人系统总体框架设计

## 1. 项目概述

生产运营数字人系统，以辅助传统App Support团队处理客户投诉排查工作。重点覆盖国业平台的典型场景，**还需要持续补充**，目前正在开发的场景包括：

- 交易问题根因定位。
- 清算状态排查。
- 立减活动客诉排查。
- 移动支付平台客诉排查。

系统通过AI Agent架构实现智能化排查，减少人工干预，提高效率和准确性。核心设计原则：

- **模块化**：每个场景独立开发Agent，便于维护和扩展。
- **自动化数据采集**：使用RPA工具提前从各平台扒取数据（如立减活动参数），存储到数据库，实现参数侧实时查询。
- **交叉协作**：场景间可共享信息（如交易定位结果辅助清算排查）。
- **智能调度**：由总调度Agent识别用户意图，进行场景路由和任务编排。
- **可迭代性**：框架支持技术演进，从初始工程式实现逐步转向ReAct（Reasoning and Acting）框架或集成新Skills。

## 2. 系统架构

### 2.1 总体结构

系统采用分层架构：

- **用户交互层**：前端界面（如Streamlit Web App），支持自然语言输入。
- **调度层**：总调度Agent，负责意图识别、场景路由和任务编排。
- **业务层**：各场景Agent（e.g., 交易定位Agent、清算排查Agent、立减客诉Agent），可调用RPA工具、数据库和自定义**Skills**。
- **数据层**：数据厨房交易明细，存储RPA扒取的数据（如每日活动参数），LDM。
- **基础设施层**：RPA调度器（每日凌晨运行）、日志监控、AI模型集成。

逻辑流程：

1. 用户输入自然语言查询。
2. 调度Agent解析意图（使用NLP，正则+LLM）。
3. 路由到对应场景Agent，或编排多Agent协作（e.g., 先交易定位，再清算检查）。
4. Agent调用数据库/RPA获取数据，进行分析。
5. 返回结果（文本+可视化，如日志高亮、分析结论）。

伪代码示例（调度Agent）：

```python
def dispatch_query(user_input):
    intent = parse_intent(user_input)  # e.g., {'scene': '交易定位', 'params': {'date': '2026-02-24', 'f11': '358154*', 'f33': '26260792'}}
    if intent['scene'] == '交易定位':
        return transaction_agent(intent['params'])
    elif intent['scene'] == '清算排查':
        trans_result = transaction_agent(intent['params'])  # 交叉调用
        return settlement_agent(trans_result)
    else:
        # 复杂任务编排
        plan = llm_plan_tasks(intent)  # 使用LLM生成任务链
        return execute_plan(plan)
```

### 2.2 组件间交互

- **调度Agent ↔ 场景Agent**：通过标准化接口（JSON格式）传递参数和结果。
- **Agent ↔ RPA**：Agent调用RPA API扒取实时数据（如果DB无缓存）。
- **RPA ↔ DB**：每日批处理，将前一天数据入库（e.g., 新增活动参数）。

## 3. 技术栈

### 3.1 核心技术

- **编程语言**：Python 3.12（主语言，支持异步处理）。
- **AI框架**：LangChain(后续考虑升级LangGraph)或LlamaIndex（用于Agent构建和LLM集成）；初始使用工程式规则，后迭代到ReAct（e.g., 使用Groq API的ReAct模式）。
- **LLM模型**：DeepSeek（用于意图解析、分析结论生成）；支持长上下文查询。
- **前端**：Streamlit（目前，适合快速原型，支持自然语言输入和结果展示）。
- **数据库**：Oracle（生产级，支持复杂查询）。
- **RPA工具**：金智维（自动化扒取平台数据）；调度使用Airflow/Cron。
- **日志/监控**：LDM。
- **其他(可能会用到)**：Docker/Kubernetes（部署）；FastAPI（内部API服务）。


### 3.2 开发规范）

#### 3.2.1 代码风格

目标：让团队任何人打开代码都能快速读懂、修改、调试。

* **格式统一** ：全部使用 black 格式化，提交前运行 black .
* **命名约定** ：
* 函数、变量：snake_case（小写+下划线）
* 类：CamelCase
* 常量：UPPER_CASE
* 避免缩写，除非行业公认（如 f11, f33, sett_ind）
* **函数长度** ：尽量控制在30–50行以内，超过则拆分成小函数
* **异常处理** ：捕获具体异常，而不是裸 except:，并记录上下文
  Python

```
  try:
      response = requests.post(url, json=payload, timeout=15)
  except requests.Timeout:
      logger.warning(f"请求超时: {url}", extra={"payload": payload})
      return {"status": "timeout", "error": "请求超时"}
  except requests.RequestException as e:
      logger.error(f"请求失败: {url}", exc_info=True)
      return {"status": "error", "error": str(e)}
```

* **日志** ：使用 logging 模块，重要分支打 info / warning / error，带上关键上下文（如 user_input、f11、scene）

#### 3.2.2 文档

目标：新同事/自己过一个月后还能快速上手。

* **模块/文件头部** ：每个主要 py 文件顶部写简短说明
  Python

```
  # transaction_agent.py
  # 交易问题根因定位 Agent
  # 主要功能：根据 f11/f33/日期 查询 LDM 日志 → 调用 LLM 解读根因
  # 输入：{"date": "...", "f11": "...", "f33": "..."}
  # 输出：标准 JSON 格式（status, result, details）
```

* **函数 Docstring** ：采用 Google 风格，简洁写清楚输入输出和主要逻辑
  Python

```
  def parse_intent(user_input: str) -> dict:
      """从自然语言中提取意图和关键参数。

      Args:
          user_input: 用户原始输入，例如“查2026-02-24 f11=358154* 的交易失败原因”

      Returns:
          dict: 包含 'scene' 和 'params' 的意图字典
                示例: {'scene': '交易定位', 'params': {'date': '2026-02-24', 'f11': '358154*', ...}}
      """
```

* **Prompt 文档** ：所有重要 Prompt 单独文件或注释块说明
* 说明这个 Prompt 针对什么场景
* 期望输出格式（JSON / 纯文本）
* 已知较好的 Few-shot 示例（如果有）
* **变更记录** ：重要功能改动时，在函数/模块顶部加简短变更注释（日期+改动内容）

#### 3.2.3 测试

* **核心测试类型** ： **效果回归测试** （Scenario-based / Golden-set 测试）
* 收集真实客诉案例，整理成测试集（目前建议 20–50 个案例起步）
* 每个案例包含：

  * 输入：用户原始问题（自然语言）
  * 期望输出：人工标注的正确根因/建议（或关键结论）
  * 可选：中间上下文（如日志片段、数据库记录）
* 示例结构（放在 tests/golden_cases/ 目录下，json 或 yaml 格式）
  JSON

  ```
  {
    "case_id": "txn_001",
    "scene": "交易定位",
    "input": "2026-02-24 f11=358154* f33=26260792 交易失败了",
    "expected": {
      "root_cause": "字段f35、f36、f45不存在",
      "suggestion": "验证卡轨信息完整性",
      "confidence": "high"
    },
    "tags": ["字段缺失", "语义校验", "常见失败"]
  }
  ```
* **评估方式** （目前推荐的简单组合）：

1. **关键词匹配** （粗排）：根因描述中是否包含核心关键词（如“f35不存在”“语义校验”“RESP_CD_30”）
2. **LLM-as-a-Judge** （精排）：用另一个强模型（或同一模型不同 Prompt）打分

   * Prompt 示例：
     text

   ```
   你是一个金融支付专家。请对比以下两个回答，判断 Agent 的回答是否正确、完整、符合业务逻辑。
   正确答案：{expected}
   Agent 回答：{agent_output}
   输出格式：
   {"score": 0-10, "reason": "简短说明"}
   ```
3. **人工抽样复核** ：每月或每次大版本迭代，随机抽 10–20 个案例人工确认

* **自动化运行方式** ：
  Bash

```
  # 运行所有 golden cases
  python -m tests.run_golden_tests --scene 交易定位 --model deepseek-r1
  # 输出示例
  交易定位场景 - 32 cases
  ✓ Pass: 24 (75.0%)
  ✗ Fail: 8
  平均 Judge 分：8.4 / 10
  最差案例：txn_017 (score=4.2)
```

* **迭代改进闭环** ：
* 把 Judge 分低的案例加入 Few-shot Prompt 或重新设计 Prompt
* 失败案例定期反馈给调度/场景 Agent 的 Prompt 维护人
* 目标：3–6 个月内主要场景的 Pass@1 达到 75–85%（视复杂度而定）
* **辅助传统测试** （少量即可）：
* 单元测试：parse_intent、extract_core_from_log 等纯逻辑函数
* Mock 测试：Mock LDM API、Oracle 查询，验证 Agent 是否正确组装参数和处理返回



## 4. 输入输出规范

为确保模块间兼容，所有Agent遵循统一接口规范（JSON Schema）。

### 4.1 输入规范（用户查询 → 调度Agent）

- **格式**：自然语言字符串，或结构化JSON（for API调用）。
- **解析规则**：使用正则+LLM提取关键参数（e.g., 日期、F11、F33、场景关键词如“清算”）。
- 示例输入：
  ```json
  {
    "query": "查询2026-02-24的清算状态，f11=358154*, f33=26260792"
  }
  ```

### 4.2 调度Agent → 场景Agent 输入

- **格式**：JSON对象。
- **必填字段**：
  - `scene`: 场景，字符串格式（e.g., "交易定位"）。
  - `params`: 关键参数，字典格式（e.g., {"date": "2026-02-24", "f11": "358154*", "f33": "26260792"}）。
  - `context`: 上下文，字典格式（可选，交叉场景数据，如前一个Agent结果）。
- 示例：
  ```json
  {
    "scene": "清算排查",
    "params": {"date": "20260224", "f11": "358154*", "f33": "26260792"},
    "context": {"transaction_log": "..."}  // 从交易Agent获取
  }
  ```

### 4.3 场景Agent 输出 → 调度Agent/用户

- **格式**：JSON对象。
- **必填字段**：
  - `status`: 字符串（"success"/"error"）。
  - `result`: 字典（e.g., {"root_cause": "字段f35不存在", "suggestion": "检查卡信息"}）。
  - `details`: 字符串（详细日志/分析过程）。
- 示例（交易定位Agent输出）：
  ```json
  {
    "status": "success",
    "result": {
      "root_cause": "字段f35、f36、f45不存在",
      "suggestion": "验证卡轨信息"
    },
    "details": "核心日志：seq1: _chkFldSemantics... "
  }
  ```

### 4.4 输出渲染

- （暂时，需前端同事进场后商议）前端使用Markdown/Table渲染结果；复杂分析使用AI生成总结（如steam.py中的分析）。

## 5. 核心组件实现指南

### 5.1 总调度Agent

- **功能**：意图识别（规则+LLM）；场景路由；任务编排（针对复杂查询，使用LLM生成计划，如“先查数据库报名卡号，再查立减交易明细”）。
- **实现**：初始工程式（ 正则+固定格式输入）；迭代到ReAct（使用LangChain的AgentExecutor）（该侧实现细节会持续迭代）。
- **输入输出**：见上节。

### 5.2 交易定位Agent

- **功能**：基于日期、F11、F33查询日志（目前）；AI分析根因（调用log_agent、oracle_agent）。
- **实现**：集成日志API +NL2SQL+ AI Prompt+RAG。核心日志解读：使用DeepSeek长上下文输入原始日志，Prompt指导提取seq级错误、知识库映射业务含义（e.g., "fld22[022],!f35Exist" → "卡轨字段缺失，导致语义校验失败"）。。
- **交叉**：输出可供其他Agent使用。

### 5.3 其他场景Agent建议(待补充)

- 清算排查：集成Oracle查询清算标志。
- 立减活动/移动支付：RPA获取全量活动参数 + 人工规则校验。技术建议：构建历史查询记录（可研究sirchmunk，自迭代知识簇）；实现Agent自迭代——通过历史客诉数据训练小型ML模型（e.g., 聚类算法模型），或使用LLM反馈循环（e.g., ReAct中添加反思步骤："如果结果不准，重新查询参数"）；集成Graph-based编排（LangGraph）处理多步校验（如报名→扣减→结算）。

## 6. 数据管理

- **RPA调度**：每日04:00运行，扒取前一天数据（e.g., 新活动参数）入DB。
- **DB Schema**： `tbl_daily_trans_temp_15` (columns: date, param_id, value)。
- **日志管理**：对接LDM 报错日志。
- **性能优化**：索引关键字段；缓存热门查询。

## 7. 潜在问题

- **问题1：意图识别准确性低** → 解决方案：训练自定义NLP模型；Fallback到人工。
- **问题2：RPA失败/数据延迟** → 解决方案：重试机制 + 监控告警；实时RPA fallback。
- **问题3：交叉场景复杂** → 解决方案：标准化上下文传递；使用Graph-based编排（LangGraph）。
- **问题4：安全/隐私** → 解决方案：数据加密；权限控制。
- **问题5：性能瓶颈** → 解决方案：异步处理；分布式部署。
- **问题6：技术迭代兼容** → 解决方案：抽象接口层（e.g., Agent基类），便于替换ReAct/Skills。

## 8. 迭代计划

- **Phase 1 (当前)**：工程式调度 + 基本场景Agent；集成现有RPA/DB。
- **Phase 2**：转向ReAct（集成LangChain）；添加新Skills（e.g., 外部API工具）。
- **Phase 3**：ML优化（意图分类模型）；A/B测试新功能。。

## 9. 实施计划与分工

- **时间线**：Q1&Q2设计&原型；Q2&Q3开发&测试；Q4上线&迭代。
- **分工**：调度&交易Agent；其他场景（邓子杰：立减；张广平：移动支付）；RPA能力封装（邓子杰）。

此框架作为项目蓝图，欢迎反馈优化。
