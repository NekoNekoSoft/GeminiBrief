import os
import asyncio
import requests
import time
import re
from datetime import datetime
import pytz
from telegram import Bot
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup

# 1. 환경변수 설정
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()

# 텔레그램 속보 채널
TELEGRAM_CHANNEL_URLS = [
    "https://t.me/s/FinancialJuice",
    "https://t.me/s/WalterBloomberg"
]

# 7개의 API 키
API_KEYS = [
    os.environ.get('GEMINI_API_KEY'),
    os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'),
    os.environ.get('GEMINI_API_KEY_4'),
    os.environ.get('GEMINI_API_KEY_5'),
    os.environ.get('GEMINI_API_KEY_6'),
    os.environ.get('GEMINI_API_KEY_7')
]
API_KEYS = [k.strip() for k in API_KEYS if k]

# 2. 한국 시간
def get_korea_time_str():
    korea_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(korea_tz)
    return now.strftime("%Y년 %m월 %d일 %H시 %M분")

# 3. 모델 찾기
def get_working_model():
    if not API_KEYS: return "models/gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEYS[0]}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            models = response.json().get('models', [])
            for m in models:
                if 'generateContent' in m['supportedGenerationMethods']:
                    return m['name']
    except:
        pass
    return "models/gemini-1.5-flash"

# 4-1. 뉴스 검색
def get_ddg_news():
    results = []
    keywords = [
        "US stock market macro analysis",
        "CBOE VIX index volatility drag",
        "Pure Storage stock technical analysis",
        "SPHD ETF dividend yield gap",
        "S&P 500 forecast technicals"
    ]
    try:
        with DDGS() as ddgs:
            for keyword in keywords:
                try:
                    news_gen = ddgs.news(keyword, max_results=1)
                    for r in news_gen:
                        text = f"[WEB] {r['title']} ({r['date']}): {r['body'][:300]}"
                        results.append(text)
                except:
                    continue
    except:
        pass
    return results

# 4-2. 텔레그램 정밀 분석
def get_telegram_news():
    collected_list = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in TELEGRAM_CHANNEL_URLS:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                messages = soup.find_all('div', class_='tgme_widget_message_wrap')
                if not messages: continue

                recent_msgs = messages[-5:] 
                
                channel_name = url.split('/')[-1]
                
                for msg in recent_msgs:
                    text_div = msg.find('div', class_='tgme_widget_message_text')
                    if not text_div: continue
                    text = text_div.get_text(separator=" ", strip=True)
                    
                    time_tag = msg.find('time')
                    msg_time = time_tag['datetime'] if time_tag else ""
                    
                    if len(text) > 5:
                        full_msg = f"[Telegram:{channel_name}] [{msg_time}] {text}"
                        collected_list.append(full_msg)
        except:
            continue
            
    return collected_list

# 5. 스마트 필터링
