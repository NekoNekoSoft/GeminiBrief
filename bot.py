import os
import asyncio
import requests
from telegram import Bot
from duckduckgo_search import DDGS

# 1. 환경변수 (안전장치 포함)
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()
GEMINI_API_KEY = os.environ['GEMINI_API_KEY'].strip()

# 2. 모델 자동 찾기
def get_working_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
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

# 3. 뉴스 수집 (범위 확장!)
def get_latest_news():
    print("뉴스 수집 중 (내 종목 + 시장 트렌드)...")
    results = []
    
    keywords = [
        # [1] 내 종목 집중
        "Pure Storage AI data center trend", # PSTG
        "SPHD ETF dividend analysis",        # SPHD
        "S&P 500 market forecast today",     # VOO/SSO
        
        # [2] 시장 전체 핫이슈 (추가됨!)
        "US stock market breaking news today", # 속보
        "Trending stocks US market today",     # 급등락 종목
        "Global economic crisis update"        # 거시경제
    ]
    
    try:
        with DDGS() as ddgs:
            for keyword in keywords:
                try:
                    # 키워드별 최신 기사 1~2개씩 수집
                    news_gen = ddgs.news(keyword, max_results=2)
                    for r in news_gen:
                        # [검색어] 제목 - 내용 형식을 유지해야 AI가 구분하기 쉬움
                        full_text = f"[{keyword}] {r['title']} ({r['date']}): {r['body']}"
                        results.append(full_text)
                except:
                    continue
    except Exception as e:
        print(f"DDGS 접속 오류: {e}")
        return ""

    return "\n".join(results)

# 4. 제미나이 요청
def ask_gemini(model_name, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ 분석 실패: {response.text}"
    except Exception as e:
        return f"❌ 요청 실패: {e}"

# 5. 메인 실행
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    model_name = get_working_model()
    news_text = get_latest_news()
    
    if not news_text:
        news_text = "뉴스 수집 실패. 일반적인 시장 시황만 브리핑 바람."

    # ★ 프롬프트 수정: 내 종목 + '그 외 소식' 요청 ★
    prompt = f"""
    [Role]
    당신은 통찰력 있는 주식 애널리스트입니다.

    [User Portfolio]
    - 보유: PSTG, SPHD, VOO(S&P500)
    - 관심: 시장 전체를 주도하는 새로운 트렌드나 급등락 종목

    [Input Data]
    {news_text}

    [Instruction]
    제공된 뉴스를 분석하여 아래 **4단계 구조**로 브리핑하세요.
    내 종목은 깊게 분석하고, 그 외 소식은 핵심만 임팩트 있게 전달하세요.

    [Output Format]
    📰 **미국 증시 올인원 브리핑**

    **1. 🚨 메인 이슈 (Macro)**
    * **[팩트 & 맥락]:** 오늘 시장을 지배한 가장 큰 재료는?
    * **[영향]:** 그래서 지수는 어떻게 움직였나?

    **2. 💼 내 포트폴리오 점검 (PSTG, SPHD)**
    * **[이슈 체크]:** 관련 호재/악재가 있는가? (없으면 '특이사항 없음' 표기)
    * **[대응 전략]:** 현재 홀딩/매수/매도 중 유
