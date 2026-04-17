# 代码优化知识库

本文档包含常用的优化模式、反模式和最佳实践，供进化式代码优化智能体参考。

---

## 优化模式库

### 1. 缓存优化 (Caching)

**问题**：重复计算或数据获取导致响应延迟

**解决方案**：
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_user_data(user_id):
    return database.query(f"SELECT * FROM users WHERE id = {user_id}")
```

**适用场景**：
- 数据库查询
- API调用
- 复杂计算
- 递归调用

**预期收益**：减少延迟，降低资源消耗

**注意事项**：
- 注意缓存失效策略
- 内存使用需监控
- 考虑并发安全

---

### 2. 延迟加载 (Lazy Loading)

**问题**：启动时加载过多资源导致启动缓慢

**解决方案**：
```python
class OrderService:
    def __init__(self):
        self._inventory_service = None
        self._payment_service = None

    @property
    def inventory_service(self):
        if self._inventory_service is None:
            self._inventory_service = InventoryService()
        return self._inventory_service
```

**适用场景**：
- 模块导入
- 服务初始化
- 资源密集型操作
- 大对象创建

**预期收益**：提升启动速度，减少内存占用

---

### 3. 并行化处理 (Parallelization)

**问题**：顺序执行导致吞吐量受限

**解决方案**：
```python
from concurrent.futures import ThreadPoolExecutor

def process_items(items):
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_single, items))
    return results
```

**适用场景**：
- 批处理任务
- I/O密集型操作
- 独立任务处理
- 数据转换

**预期收益**：提升吞吐量，减少总执行时间

**注意事项**：
- 注意线程安全
- 合理设置并发数
- 考虑资源竞争

---

### 4. 数据结构优化 (Data Structure Optimization)

**问题**：使用低效的数据结构导致查找/插入性能差

**解决方案**：
```python
# 优化前: 列表查找 O(n)
def find_user_by_id(users_list, user_id):
    for user in users_list:
        if user.id == user_id:
            return user

# 优化后: 字典查找 O(1)
def find_user_by_id(users_dict, user_id):
    return users_dict.get(user_id)
```

**适用场景**：
- 频繁查找操作
- 集合操作
- 状态管理
- 缓存实现

**预期收益**：时间复杂度从O(n)优化到O(1)

---

### 5. 批量操作优化 (Batch Operation)

**问题**：N+1问题或频繁小操作导致性能损耗

**解决方案**：
```python
# 优化前: N+1查询
def get_orders_with_users(order_ids):
    orders = []
    for order_id in order_ids:
        order = db.query(f"SELECT * FROM orders WHERE id = {order_id}")
        user = db.query(f"SELECT * FROM users WHERE id = {order.user_id}")
        orders.append({**order, 'user': user})
    return orders

# 优化后: 批量查询
def get_orders_with_users(order_ids):
    orders = db.query(f"SELECT * FROM orders WHERE id IN ({order_ids})")
    user_ids = [o.user_id for o in orders]
    users = db.query(f"SELECT * FROM users WHERE id IN ({user_ids})")
    users_map = {u.id: u for u in users}
    return [{**order, 'user': users_map[order.user_id]} for order in orders]
```

**适用场景**：
- 数据库操作
- API调用
- 文件处理
- 网络请求

**预期收益**：减少I/O次数，降低延迟

---

### 6. 算法替换 (Algorithm Replacement)

**问题**：使用低效算法导致性能瓶颈

**常见替换**：

| 原算法 | 替换算法 | 复杂度改进 |
|--------|----------|------------|
| 冒泡排序 | 快速排序/归并排序 | O(n²) → O(n log n) |
| 线性搜索 | 二分搜索 | O(n) → O(log n) |
| 递归斐波那契 | 迭代/记忆化 | O(2^n) → O(n) |
| 暴力匹配 | KMP算法 | O(nm) → O(n+m) |

**预期收益**：显著提升处理大规模数据的性能

---

### 7. 索引优化 (Index Optimization)

**问题**：缺少索引或低效查询导致数据库性能差

**解决方案**：
```sql
-- 创建复合索引
CREATE INDEX idx_orders_customer_date ON orders(customer_id, created_at);

-- 优化查询，只选择需要的列
SELECT id, total_amount FROM orders WHERE customer_id = 123;
```

**适用场景**：
- 数据库查询
- 报表生成
- 搜索功能

**预期收益**：减少查询时间

---

### 8. 内存优化 (Memory Optimization)

**问题**：内存占用过高或内存泄漏

**解决方案**：
- 使用生成器替代列表
- 及时释放大对象
- 使用弱引用
- 避免循环引用

```python
# 使用生成器
def read_large_file(file_path):
    with open(file_path) as f:
        for line in f:
            yield line
```

**预期收益**：降低内存占用，支持更大规模数据处理

---

## 反模式库

### 1. N+1查询问题

**检测方法**：分析查询日志，检查循环内的数据库调用

**影响**：严重性能退化，数据库压力增大

**修复**：使用批量查询或JOIN

---

### 2. 上帝类 (God Class)

**检测方法**：圈复杂度分析，类方法数量检查

**影响**：可维护性差，测试困难

**修复**：拆分职责，应用单一职责原则

---

### 3. 过早优化

**检测方法**：代码审查

**影响**：增加复杂度，收益不明确

**修复**：先分析瓶颈，再针对性优化

---

### 4. 魔法数字

**检测方法**：静态分析

**影响**：可读性差，维护困难

**修复**：使用命名常量

---

### 5. 深层嵌套

**检测方法**：圈复杂度分析

**影响**：可读性差，逻辑复杂

**修复**：提取方法，使用卫语句

---

## 最佳实践

### 性能分析优先

1. 先测量，后优化
2. 使用Profiler识别热点
3. 关注P99延迟而非平均值
4. 建立性能基线

### 渐进式优化

1. 从最大瓶颈开始
2. 每次只改一个变量
3. 验证每次优化的效果
4. 保持代码可读性

### 测试保障

1. 优化前确保有测试覆盖
2. 优化后运行回归测试
3. 建立性能基准测试
4. 监控生产环境性能
