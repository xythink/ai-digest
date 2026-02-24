# AI Digest 📡

每日自动采集 AI 领域关键人物动态，LLM 总结后推送到 Telegram。

## 架构

```
RSS/Twitter → collect.py → latest.json → 贾维斯总结 → Telegram
```

## 数据源

### RSS (稳定)
- Simon Willison (博客)
- Lilian Weng (博客)
- Nicholas Carlini (博客)
- Andrej Karpathy (YouTube)
- Latent Space / Swyx (播客)

### Twitter/X (需配置账号)
- @karpathy, @DrJimFan, @_jasonwei, @hwchung27
- @hwchase17, @swyx, @emollick, @andyzou_jiaming, @dotey

## Twitter 配置

需要一个 X 账号：
```python
from twscrape import API
import asyncio

async def setup():
    api = API("twitter_accounts.db")
    await api.pool.add_account("username", "password", "email", "email_password")
    await api.pool.login_all()

asyncio.run(setup())
```

## 运行

```bash
python3 collect.py          # 采集
# 总结由贾维斯通过 cron 完成
```

## Cron

每天 08:30 CST 由 OpenClaw cron 触发。
