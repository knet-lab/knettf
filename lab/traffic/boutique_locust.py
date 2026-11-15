"""
Online Boutique 的仿真用户（locust）。由 client-zone.sh 在每个客户端 netns 里各启动一份。

行为：首页 → 换币种 → 看商品 → 加购物车 → 看购物车 → 偶尔下单，带随机思考时间。
负载曲线：用户数按余弦"日周期"在 MIN~MAX 之间起伏，每个客户端相位不同，
          避免所有客户端同时高峰、流量形态过于整齐。

环境变量：
  CLIENT_MIN_USERS / CLIENT_MAX_USERS   用户数范围（默认 1 / 6）
  CLIENT_PERIOD_SEC                     一个"日周期"的长度（默认 3600 秒，压缩的一天）
  CLIENT_PHASE                          相位 0~1（默认 0）
"""

import math
import os
import random

from locust import HttpUser, LoadTestShape, between, task

PRODUCTS = [
    "0PUK6V6EV0", "1YMWWN1N4O", "2ZYFJ3GM2N", "66VCHSJNUP", "6E92ZMYYFZ",
    "9SIQT8TOJO", "L9ECAV7KIM", "LS4PSXUNUM", "OLJCESPC7Z",
]
CURRENCIES = ["EUR", "USD", "JPY", "CAD", "GBP", "TRY"]


class Shopper(HttpUser):
    wait_time = between(1, 8)  # 秒：人的思考时间

    @task(10)
    def index(self):
        self.client.get("/")

    @task(2)
    def set_currency(self):
        self.client.post("/setCurrency", {"currency_code": random.choice(CURRENCIES)})

    @task(10)
    def browse_product(self):
        self.client.get(f"/product/{random.choice(PRODUCTS)}", name="/product/[id]")

    @task(3)
    def view_cart(self):
        self.client.get("/cart")

    @task(2)
    def add_to_cart(self):
        p = random.choice(PRODUCTS)
        self.client.get(f"/product/{p}", name="/product/[id]")
        self.client.post("/cart", {"product_id": p, "quantity": random.randint(1, 5)})

    @task(1)
    def checkout(self):
        self.add_to_cart()
        # Online Boutique 自带的演示用测试数据，不是真实信息
        self.client.post("/cart/checkout", {
            "email": "someone@example.com",
            "street_address": "1600 Amphitheatre Parkway",
            "zip_code": "94043",
            "city": "Mountain View",
            "state": "CA",
            "country": "United States",
            "credit_card_number": "4432-8015-6152-0454",
            "credit_card_expiration_month": "1",
            "credit_card_expiration_year": "2039",
            "credit_card_cvv": "672",
        })


class Diurnal(LoadTestShape):
    lo = int(os.environ.get("CLIENT_MIN_USERS", "1"))
    hi = int(os.environ.get("CLIENT_MAX_USERS", "6"))
    period = float(os.environ.get("CLIENT_PERIOD_SEC", "3600"))
    phase = float(os.environ.get("CLIENT_PHASE", "0"))

    def tick(self):
        t = self.get_run_time()
        x = (1 - math.cos(2 * math.pi * (t / self.period + self.phase))) / 2  # 0~1
        users = max(1, round(self.lo + (self.hi - self.lo) * x))
        return users, 1  # (用户数, 每秒增减速率)
