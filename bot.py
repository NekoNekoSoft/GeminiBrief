import os
import asyncio
import requests
import json
from telegram import Bot
from duckduckgo_search import DDGS

# 1. 환경변수
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

# 2. 뉴스 검색
def get_latest_news():
    print("뉴스 검색 시작...")
    results = []
    try:
        with DDGS() as ddgs:
            keywords = ["US stock market news", "PSTG stock", "SPHD ETF", "S&P 500"]
            for keyword in keywords:
                try:
                    # 검색 결과 1개씩만 빠르게 수집
                    r_gen = ddgs.text(keyword, max_results=1)
                    for r in r_gen:
                        results.append(f"- {r['title']}: {r['body']}")
                except:
                    continue
    except Exception as e:
        print(f"DDGS 접속 에러: {e}")
        return "뉴스 검색 실패 (접속 오류)"
        
    return "\n".join(results) if results else "뉴스 검색 결과 없음"

# 3. 제미나이 직접 요청 (REST API)
def ask_gemini_direct(prompt):
    # ★★★ 수정된 부분: 모델 이름을 'gemini-pro'로 변경 (가장 안정적) ★★★
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ API 에러 코드: {response.status_code}\n내용: {response.text}"
    except Exception as e:
        return f"❌ 요청 실패: {e}"

# 4. 메인 실행
async def main():
    # 1) 뉴스 가져오기
    news_text = get_latest_news()

    # 2) 프롬프트 설정
    prompt = f"""
    [역할] 너는 주식 비서야. 아래 뉴스를 요약해서 한국어로 브리핑해줘.
    [뉴스] {news_text}
    [조건] PSTG, SPHD, 미국증시 위주로 설명. 출처 꼭 표기해.
    """

    # 3) 제미나이에게 물어보기
    print("제미나이에게 질문 중...")
    msg = ask_gemini_direct(prompt)
    print("답변 생성 완료.")

    # 4) 텔레그램 전송
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        print("텔레그램 전송 성공!")
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

if __name__ == "__main__":
    asyncio.run(main())
