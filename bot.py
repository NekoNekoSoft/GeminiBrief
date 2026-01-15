import os
import asyncio
import requests
import json
from telegram import Bot
from duckduckgo_search import DDGS

# 1. 환경변수 (공백 제거 안전장치 추가!)
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()
GEMINI_API_KEY = os.environ['GEMINI_API_KEY'].strip()

# 2. 살아있는 모델 찾기 (핵심 기능!)
def get_working_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            models = response.json().get('models', [])
            for m in models:
                # 'generateContent' 기능을 지원하는 모델만 찾음
                if 'generateContent' in m['supportedGenerationMethods']:
                    print(f"✅ 찾은 모델: {m['name']}")
                    return m['name'] # 예: models/gemini-1.5-flash
    except Exception as e:
        print(f"모델 찾기 실패: {e}")
    
    # 못 찾으면 그냥 기본값 던짐
    return "models/gemini-1.5-flash"

# 3. 뉴스 검색
def get_latest_news():
    print("뉴스 검색 시작...")
    results = []
    try:
        with DDGS() as ddgs:
            keywords = ["US stock market news", "PSTG stock", "SPHD ETF", "S&P 500"]
            for keyword in keywords:
                try:
                    r_gen = ddgs.text(keyword, max_results=1)
                    for r in r_gen:
                        results.append(f"- {r['title']}: {r['body']}")
                except:
                    continue
    except:
        return "뉴스 검색 실패"
    return "\n".join(results) if results else "뉴스 검색 결과 없음"

# 4. 제미나이 요청 (찾아낸 모델로 요청)
def ask_gemini(model_name, prompt):
    # model_name은 'models/gemini-1.5-flash' 형태임
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ API 에러 ({response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ 요청 실패: {e}"

# 5. 메인 실행
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # 1) 작동하는 모델부터 찾기
    model_name = get_working_model()
    
    # 2) 뉴스 가져오기
    news_text = get_latest_news()

    # 3) 질문하기
    prompt = f"""
    [역할] 주식 비서.
    [뉴스] {news_text}
    [요청] PSTG, SPHD, 미국증시 시황을 한국어로 브리핑해줘. 쉬운 용어로.
    """
    
    print(f"제미나이({model_name})에게 질문 중...")
    msg = ask_gemini(model_name, prompt)

    # 4) 텔레그램 전송
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        print("텔레그램 전송 성공!")
    except Exception as e:
        print(f"텔레그램 실패: {e}")

if __name__ == "__main__":
    asyncio.run(main())
