import asyncio
import json
import aiohttp
from telegram import Bot
import hashlib
import os
from curl_cffi.requests import AsyncSession
import random


# 定义常量
URL = 'https://api.cryptorank.io/v0/round/upcoming'
HEADERS = {
    'accept': '*/*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'content-type': 'application/json',
    'origin': 'https://cryptorank.io',
    'referer': 'https://cryptorank.io/',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}
DATA = {
    "path": "round/upcoming",
    "limit": 50,
    "filters": {"tokenSaleTypes": {"condition": "or", "data": ["IDO", "IEO"]}},
    "skip": 0,
    "status": "upcoming"
}

TARGET_LAUNCHPADS = {"bitget", "binance-launchpad", "okx-jumpstart", "bybit-launchpad", "pancake-swap", "gateio-startup"}

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
PROXY = os.getenv('PROXY')

if PROXY:
    proxies = PROXY.split(',')  # 假设多个代理以逗号分隔
else:
    proxies = []

# 随机选择一个代理
chosen_proxy = random.choice(proxies) if proxies else None
    
# 初始化 Telegram Bot
bot = Bot(token=TELEGRAM_TOKEN)

# 计算一个稳定的哈希值，使用 SHA256
def get_stable_hash(message):
    return hashlib.sha256(message.encode('utf-8')).hexdigest()

async def fetch_data():

    async with AsyncSession(impersonate="chrome124", verify=True) as session:
        session.timeout = 10
        session.proxies = {"http": f'http://{chosen_proxy.strip()}', "https": f'http://{chosen_proxy.strip()}'}
        response = await session.post(URL, json=DATA, headers=HEADERS)
        if response.status_code == 201:
            return response.json()
        else:
            print(f"请求失败，状态码：{response.status_code}")
            return None

async def send_message(message):
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=None, disable_web_page_preview=True)

async def process_data():
    # 异步获取数据
    data = await fetch_data()
    if data:
        # 读取已处理的项目
        try:
            with open('launched.json', 'r', encoding='utf-8') as file:
                launched = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            launched = {}

        # 处理新项目
        for item in data.get('data', []):
            launchpad_keys = {launchpad['key'] for launchpad in item.get('launchpads', [])}
            if launchpad_keys.intersection(TARGET_LAUNCHPADS):
                # 构建消息内容
                launchpad_names = {launchpad['name'] for launchpad in item.get('launchpads', [])}
                sale_price = item.get('salePrice')
                when = item.get('when')
                till = item.get('till')
                blockchains = item.get('blockchains', [])
                blockchain_names = [blockchain.get('name') for blockchain in blockchains]
                message = (
                    f"项目名称：{item.get('name')}\n"
                    f"代币符号：{item.get('symbol')}\n"
                    f"销售价格：{sale_price}\n"
                    f"销售平台：{' | '.join(launchpad_names)}\n"
                    f"开始日期：{when}\n"
                    f"截止日期：{till}\n"
                    f"支持的区块链：{', '.join(blockchain_names) if blockchain_names else '无'}\n"
                )

                # 计算项目的唯一标识符（哈希值）
                item_hash = get_stable_hash(message)
                if item_hash not in launched:
                    # 异步发送 Telegram 消息
                    await send_message(message)

                    # 更新已处理的项目字典
                    launched[item_hash] = message
                    with open('launched.json', 'w', encoding='utf-8') as file:
                        json.dump(launched, file, ensure_ascii=False, indent=4)

# 启动异步任务
async def main():
    await process_data()

# 使用 asyncio 运行主函数
if __name__ == "__main__":
    asyncio.run(main())
