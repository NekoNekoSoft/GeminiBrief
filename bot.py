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

# 1. 환경변수
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()

# 텔레그램 속보 채널 (FinancialJuice, WalterBloomberg)
TELEGRAM_CHANNEL_URLS = [
    "https://t.me/s/FinancialJuice",
    "https://t.me/s/WalterBloomberg"
]

# API 키 7개
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

# 4-1. 뉴스 검색 (리스트 반환)
def get_ddg_news():
    results = []
    keywords = [
        "US stock market breaking news impact",
        "Pure Storage stock latest analysis",
        "SPHD ETF latest dividend news",
        "S&P 500 VOO latest forecast"
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

# 4-2. 텔레그램 정밀 분석 (리스트 반환)
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

                recent_msgs = messages[-5:] # 최신 5개
                
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

# ★★★ 5. 스마트 필터링 (중복 제거 & 기록) ★★★
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
    
    # 현재 상태 저장 (다음 비교를 위해)
    with open(log_file, "w", encoding="utf-8") as f:
        for item in current_items:
            f.write(item.strip() + "\n")
            
    return new_items

# 6. 제미나이 요청 (7-Key Rotation)
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
    return "❌ API 요청 실패."

# 7. 메인 실행
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    model_name = get_working_model()
    current_time = get_korea_time_str()
    
    # 1) 데이터 수집
    web_list = get_ddg_news()
    telegram_list = get_telegram_news()
    all_current_list = web_list + telegram_list
    
    if not all_current_list:
        print("수집된 데이터가 없습니다.")
        return

    # 2) ★ 필터링 실행 (새로운 것만 추출) ★
    real_new_news = filter_new_items(all_current_list)
    
    if not real_new_news:
        print("🔍 확인 결과: 모든 뉴스가 지난번과 동일합니다. (전송 안 함)")
        return 

    # 3) 브리핑 시작
    print(f"✨ 새로운 소식 {len(real_new_news)}건 발견! 브리핑 시작.")
    combined_data = "\n".join(real_new_news)

    prompt = f"""
    [Role] 월스트리트 수석 매크로 전략가
    [Current Time] {current_time} (KST)
    [User Portfolio] PSTG, SPHD, VOO
    
    [New Input Data]
    {combined_data}
    
    [Instruction]
    위 데이터는 방금 들어온 **따끈따끈한 새 소식**들이다.
    이미 알고 있는 내용은 제외되었으니, 이 내용들을 집중적으로 분석해서 브리핑하라.
    
    1. **속보 해석**: 텔레그램/웹 뉴스의 의미를 분석하라. (단순 번역 금지)
    2. **포트폴리오 영향**: 이 새 소식이 PSTG, SPHD, VOO에 호재인지 악재인지 판단하라.
    3. **대응 전략**: 그래서 지금 당장 뭘 해야 하는가?
    
    [Output Structure]
    🔔 **New Market Alert** ({current_time})
    
    **1. ⚡ Breaking Insight**
    * (새로 들어온 속보의 핵심과 시장 함의 분석)
    
    **2. 💼 Portfolio Check**
    * (내 종목에 미치는 영향 분석. 관련 없으면 "직접적 영향 없음" 명시)
    
    **3. 💡 Quick Take**
    * (한 줄 요약 조언)
    """
    
    print("브리핑 생성 중...")
    msg = ask_gemini(model_name, prompt)

    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    except:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    
    print("전송 성공!")

if __name__ == "__main__":
    asyncio.run(main())
