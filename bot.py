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

# 7개의 API 키 로드
API_KEYS = [
    os.environ.get('GEMINI_API_KEY'),
    os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'),
    os.environ.get('GEMINI_API_KEY_4'),
    os.environ.get('GEMINI_API_KEY_5'),
    os.environ.get('GEMINI_API_KEY_6'),
    os.environ.get('GEMINI_API_KEY_7')
]
# 비어있는 키 제거
API_KEYS = [k.strip() for k in API_KEYS if k]

# 2. 한국 시간 구하기
def get_korea_time_str():
    korea_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(korea_tz)
    return now.strftime("%Y년 %m월 %d일 %H시 %M분")

# 3. 모델 찾기 (API 키 로테이션)
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

# 4-1. 뉴스 검색 (전문 용어 + 포트폴리오 키워드)
def get_ddg_news():
    results = []
    keywords = [
        "US stock market macro analysis",         # 거시경제
        "CBOE VIX index volatility drag",         # 변동성 끌림 (SSO 필수)
        "Pure Storage stock technical analysis",  # PSTG
        "SPHD ETF dividend yield gap",            # SPHD
        "S&P 500 forecast technicals"             # VOO/SSO
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

# 4-2. 텔레그램 정밀 분석 (속보)
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

# 5. 스마트 필터링 (중복 뉴스 제거)
def filter_new_items(current_items):
    log_file = "news_log.txt"
    old_items = set()
    
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                old_items.add(line.strip())
    
    new_items = []
    for item in current_items:
        clean_item = item.strip()
        if clean_item not in old_items:
            new_items.append(clean_item)
    
    with open(log_file, "w", encoding="utf-8") as f:
        for item in current_items:
            f.write(item.strip() + "\n")
            
    return new_items

# 6. 제미나이 요청
def ask_gemini(model_name, prompt):
    for i, key in enumerate(API_KEYS):
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={key}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                time.sleep(1)
                continue
        except:
            continue
    return "❌ API 요청 실패"

# ★★★ 7. 긴 메시지 분할 전송 함수 (에러 방지 핵심 기능) ★★★
async def send_long_message(bot, chat_id, text):
    # 텔레그램 제한은 4096자지만 안전하게 4000자로 자름
    MAX_LENGTH = 4000
    
    # 1. 짧은 경우: 마크다운으로 시도
    if len(text) < MAX_LENGTH:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')
            return
        except Exception as e:
            print(f"마크다운 전송 실패(포맷 에러): {e}")
            # 포맷 에러 시 텍스트로 재시도
            await bot.send_message(chat_id=chat_id, text=text)
            return

    # 2. 긴 경우: 텍스트로 쪼개서 전송
    print("메시지가 너무 길어 분할 전송합니다.")
    for i in range(0, len(text), MAX_LENGTH):
        chunk = text[i:i+MAX_LENGTH]
        try:
            await bot.send_message(chat_id=chat_id, text=chunk)
            time.sleep(1) # 순서 꼬임 방지
        except Exception as e:
            print(f"분할 전송 실패: {e}")

# 8. 메인 실행
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    model_name = get_working_model()
    current_time = get_korea_time_str()
    
    # 데이터 수집
    web_list = get_ddg_news()
    telegram_list = get_telegram_news()
    all_current_list = web_list + telegram_list
    
    if not all_current_list:
        print("수집된 데이터가 없습니다.")
        return

    # 필터링
    real_new_news = filter_new_items(all_current_list)
    
    # 뉴스가 없을 때 생존 신고
    if not real_new_news:
        print("🔍 새로운 정보 없음. 생존 신고 전송.")
        msg = f"🔔 **Market Status Check** ({current_time})\n\n✅ 현재 수집된 새로운 속보나 특이사항이 없습니다.\n시장을 계속 모니터링 중입니다. 👀"
        await send_long_message(bot, CHAT_ID, msg)
        return 

    # 브리핑 생성
    print(f"✨ 새로운 소식 {len(real_new_news)}건 발견! 분석 시작.")
    combined_data = "\n".join(real_new_news)

    # 프롬프트: 전문가 + 1타 강사 (UPRO 제외, SSO 강조)
    prompt = f"""
    [Role]
    당신은 **월스트리트 수석 애널리스트(전문성)**이자, 이를 주린이에게 가르쳐주는 **친절한 1타 강사(교육)**입니다.
    사용자의 **금융 지식 향상**을 위해, 브리핑은 반드시 아래 **[2단계 구조]**를 지켜야 합니다.

    1. **Step 1 (전문적 분석)**: 정확한 금융 용어(Volatility Drag, CPI, Yield Gap 등)와 수치를 사용하여 현상을 정의합니다.
    2. **Step 2 (쉬운 풀이)**: 바로 이어서 "👉 즉," 또는 "쉽게 말해"를 사용하여 **직관적인 비유(운전, 날씨, 파도 등)**로 다시 설명합니다.

    [Current Time] {current_time} (KST)
    [User Portfolio]
    - Core: VOO (1x)
    - Growth/Dividend: PSTG, SPHD (비중 확대)
    - **Leverage: SSO (2x)** <-- (UPRO 제외됨, 2배 레버리지 집중 관리)

    [New Input Data]
    {combined_data}

    [Instruction]
    위 데이터를 바탕으로 **객관적이고 냉철하게** 분석하되, 사용자가 공부가 되도록 작성하세요.

    1. **속보 해석**: 텔레그램 속보를 전문 용어로 정의하고, 그게 무슨 뜻인지 쉽게 풉니다.
    2. **레버리지 경고 (SSO)**: 2배 레버리지도 횡보장에서는 계좌가 녹을 수 있습니다. '변동성' 위험을 운전이나 날씨에 비유해 경고하세요.
    3. **냉정한 조언**: 희망 회로 없이 현실적인 대응책을 제시합니다.

    [Output Structure]
    🔔 **Market Briefing & Study** ({current_time})

    **1. ⚡ Breaking Insight (속보와 해석)**
    * (전문 용어를 포함한 분석 문장)
    * 👉 (초보자도 이해할 수 있는 쉬운 비유)
    
    **2. ⚠️ Portfolio Risk (SSO & SPHD 집중)**
    * **SSO (2x):** (변동성 지표 등 전문 분석 -> 쉬운 경고)
    * **PSTG/SPHD:** (이슈 분석 -> 쉬운 풀이)
    
    **3. 💡 Analyst's View (대응 전략)**
    * (객관적 판단 및 행동 요령)
    """
    
    print("브리핑 생성 중...")
    msg = ask_gemini(model_name, prompt)

    # ★ 분할 전송 함수 사용 ★
    await send_long_message(bot, CHAT_ID, msg)
    print("전송 성공!")

if __name__ == "__main__":
    asyncio.run(main())
 