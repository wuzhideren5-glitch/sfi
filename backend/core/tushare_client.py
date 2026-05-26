"""
Tushare 金融数据客户端初始化
用法: from core.tushare_client import pro
"""
import os
import tushare as ts

# 从环境变量读取 token（不要硬编码！）
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_HTTP_URL = os.getenv("TUSHARE_HTTP_URL", "http://101.35.233.113:8020/")

if not TUSHARE_TOKEN:
    raise RuntimeError("TUSHARE_TOKEN 环境变量未设置")

pro = ts.pro_api(TUSHARE_TOKEN)
pro._DataApi__http_url = TUSHARE_HTTP_URL

# 快速测试
if __name__ == "__main__":
    df = pro.index_basic(limit=5)
    print("index_basic test:")
    print(df)
    df2 = ts.pro_bar(api=pro, ts_code="000001.SZ", limit=3)
    print("\npro_bar test:")
    print(df2)
