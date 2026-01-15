import os
import asyncio
import requests
import time
import re
from telegram import Bot
from duckduckgo_search import DDGS

# 1. 환경변수
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()

# ==========================================
# ★ 텔레그램 채널 주소 목록 (사용자님 요청 반영 완료) ★
# FinancialJuice & Walter Bloomberg 탑재
# ==========================================
TELEGRAM_CHANNEL_URLS = [
    "https://t.me/s/FinancialJuice",    # 실시간 금융 속보
    "https://t.me/s/WalterBloomberg"    # 글로벌 마켓 헤드라인
]

# 7개의 열쇠 꾸러미
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

# 2. 모델 자동 찾기
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

# 3-1. 뉴스 수집 (Macro + Portfolio)
def get_ddg_news():
    print("📰 뉴스 데이터 수집 중...")
    results = []
    
    keywords = [
        "Why is US stock market moving today",  # 시황
        "US stock market key events today",     # 주요 이슈
        "Pure Storage stock news analysis",     # PSTG
        "SPHD ETF dividend news today",         # SPHD
        "S&P 500 VOO ETF forecast"              # VOO
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
    except Exception as e:
        print(f"DDGS 오류: {e}")
    return "\n".join(results)

# 3-2. 텔레그램 채널 스크랩 (FinancialJuice + WalterBloomberg)
def get_telegram_news():
    print(f"📡 텔레그램 채널 {len(TELEGRAM_CHANNEL_URLS)}개 스캔 중...")
    collected_text = []
    
    for url in TELEGRAM_CHANNEL_URLS:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                html = response.text
                # HTML 태그 제거 및 텍스트 정제
                text_content = re.sub('<[^<]+?>', ' ', html)
                text_content = ' '.join(text_content.split())
                
                # 채널 이름 추출 (URL 끝부분)
                channel_name = url.split('/')[-1]
                
                # 최신글 2000자 확보 (속보가 많으므로 조금 더 길게)
                collected_text.append(f"\n[Telegram: {channel_name}]\n{text_content[:2000]}...\n")
        except Exception as e:
            print(f"채널({url}) 스크랩 실패: {e}")
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
    제공된 뉴스(웹 검색 + FinancialJuice/WalterBloomberg 속보)를 종합 분석하여 브리핑하라.
    특히 텔레그램 속보 채널에서 나온 최신 마켓 루머나 지표 발표를 중요하게 다뤄라.
    
    [Formatting Rules]
    1. **가독성**: 섹션 분리 명확히.
    2. **출처 분리**: 각 섹션 하단에 `> 🗞️ [출처: ...]` 표기.
    
    [Output Structure]
    📰 **미국 증시 & 포트폴리오 브리핑**
    
    **1. 🌎 Global Market Review**
    * (시장 등락 원인 및 거시경제 이슈 분석)
    
    **2. 💼 My Portfolio Focus (PSTG, SPHD)**
    * **PSTG:** (성장주 관점 분석)
    * **SPHD:** (배당/안정성 관점 분석)
    * **VOO:** (지수 흐름 체크)
    
    **3. 📡 Bloomberg & FinancialJuice Insight**
    * (텔레그램 채널에서 수집된 실시간 속보 및 중요 헤드라인 요약)
    
    **4. 💡 Investment Insight**
    * (최종 요약 및 조언)
    """
    
    print("종합 보고서 작성 중...")
    msg = ask_gemini(model_name, prompt)

    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    except:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    
    print("전송 성공!")

if __name__ == "__main__":
    asyncio.run(main())
