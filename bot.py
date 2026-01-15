import os
import asyncio
import requests
import time
from telegram import Bot
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup # ★ 수술용 핀셋 도구 가져오기

# 1. 환경변수
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()

# 텔레그램 채널 (속보 채널)
TELEGRAM_CHANNEL_URLS = [
    "https://t.me/s/FinancialJuice",
    "https://t.me/s/WalterBloomberg"
]

# 7개의 열쇠
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

# 2. 모델 찾기
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

# 3-1. 뉴스 검색
def get_ddg_news():
    print("📰 뉴스 수집 중...")
    results = []
    keywords = [
        "Why is US stock market moving today",
        "US stock market key events today",
        "Pure Storage stock news analysis",
        "SPHD ETF dividend news today",
        "S&P 500 VOO ETF forecast"
    ]
    try:
        with DDGS() as ddgs:
            for keyword in keywords:
                try:
                    news_gen = ddgs.news(keyword, max_results=2)
                    for r in news_gen:
                        results.append(f"[{keyword}] {r['title']} ({r['date']}): {r['body'][:500]}...")
                except:
                    continue
    except:
        pass
    return "\n".join(results)

# 3-2. 텔레그램 스크랩 (★ BeautifulSoup 적용: 진짜 텍스트만 추출 ★)
def get_telegram_news():
    print(f"📡 텔레그램 정밀 스캔 중...")
    collected_text = []
    
    # 텔레그램이 봇을 차단하지 않게 '나는 사람이야'라고 속이는 헤더
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    for url in TELEGRAM_CHANNEL_URLS:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 텔레그램 메시지 본문 클래스: 'tgme_widget_message_text'
                # 이 클래스를 가진 태그만 찾아내면 순수한 대화 내용임!
                messages = soup.find_all('div', class_='tgme_widget_message_text')
                
                if not messages:
                    continue

                # 최근 메시지 5개만 가져오기 (너무 옛날 건 필요 없음)
                recent_msgs = messages[-5:] 
                
                channel_text = []
                for msg in recent_msgs:
                    # HTML 태그 떼고 순수 텍스트만 추출 (.get_text)
                    clean_msg = msg.get_text(separator=" ", strip=True)
                    channel_text.append(f"- {clean_msg}")
                
                channel_name = url.split('/')[-1]
                collected_text.append(f"\n[Telegram: {channel_name} 최신 속보]\n" + "\n".join(channel_text))
                
        except Exception as e:
            print(f"스크랩 에러({url}): {e}")
            continue
            
    return "\n".join(collected_text)

# 4. 제미나이 요청
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

# 5. 메인 실행
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    model_name = get_working_model()
    
    news_1 = get_ddg_news()
    news_2 = get_telegram_news()
    combined_news = f"{news_1}\n\n{news_2}"
    
    if len(combined_news) < 10:
        combined_news = "뉴스 수집 실패."

    prompt = f"""
    [Role] 월스트리트 수석 애널리스트
    [Portfolio] PSTG, SPHD, VOO
    
    [Input Data]
    {combined_news}
    
    [Instruction]
    제공된 뉴스(웹 뉴스 + 텔레그램 속보)를 분석하여 브리핑하라.
    **특히 텔레그램(FinancialJuice, WalterBloomberg)의 내용은 100% 반영하라.**
    (금융 뉴스가 아니더라도, 해당 채널에 올라온 내용을 요약해서 무슨 말이 오가는지 알려줄 것)
    
    [Formatting Rules]
    1. **가독성**: 섹션 분리 명확히.
    2. **출처 분리**: 섹션 하단에 `> 🗞️ [출처: ...]` 표기.
    
    [Output Structure]
    📰 **미국 증시 & 포트폴리오 브리핑**
    
    **1. 🌎 Global Market Review**
    * (시장 흐름 및 원인 분석)
    
    **2. 💼 My Portfolio Focus (PSTG, SPHD)**
    * (내 종목 관련 이슈 및 전략)
    
    **3. 📡 FinancialJuice & Bloomberg Insight**
    * (텔레그램 속보 내용을 바탕으로, 지금 시장이 주목하는 단신/루머/지표를 정리)
    * **(뉴스가 없으면 "현재 채널에 특별한 속보가 없습니다"라고 있는 그대로 전달)**
    
    **4. 💡 Investment Insight**
    * (최종 요약)
    """
    
    print("보고서 작성 중...")
    msg = ask_gemini(model_name, prompt)

    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    except:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    
    print("전송 성공!")

if __name__ == "__main__":
    asyncio.run(main())
