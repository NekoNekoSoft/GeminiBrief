import os
import asyncio
import requests
from telegram import Bot
from duckduckgo_search import DDGS

# 1. 환경변수
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()
GEMINI_API_KEY = os.environ['GEMINI_API_KEY'].strip()

# 2. 살아있는 모델 찾기
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
    return "models/gemini-1.5-flash" # 기본값

# 3. 뉴스 검색 (업그레이드됨!)
def get_latest_news():
    print("뉴스 수집 시작...")
    results = []
    
    # 검색 키워드 (뉴스 전용)
    keywords = [
        "Pure Storage stock news",   # PSTG (영어 기사가 더 잘 나옴)
        "SPHD ETF dividend news",    # SPHD
        "S&P 500 market update"      # 전체 시황
    ]
    
    try:
        with DDGS() as ddgs:
            for keyword in keywords:
                try:
                    # text() 대신 news() 사용 -> 최신 기사 위주
                    print(f"검색 중: {keyword}")
                    news_gen = ddgs.news(keyword, max_results=2)
                    for r in news_gen:
                        # 기사 제목과 앞부분 내용 가져오기
                        title = r.get('title', '')
                        body = r.get('body', '') or r.get('title', '') # 본문 없으면 제목이라도
                        source = r.get('source', 'Unknown')
                        date = r.get('date', '')
                        
                        full_text = f"- [{source}/{date}] {title}: {body}"
                        results.append(full_text)
                except Exception as e:
                    print(f"키워드 '{keyword}' 건너뜀: {e}")
                    continue
    except Exception as e:
        print(f"DDGS 접속 오류: {e}")
        return ""

    # 수집된 뉴스가 있으면 합쳐서 반환, 없으면 빈 문자열
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
            return f"❌ API 에러: {response.text}"
    except Exception as e:
        return f"❌ 요청 실패: {e}"

# 5. 메인 실행
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    model_name = get_working_model()
    
    # 뉴스 수집
    news_text = get_latest_news()
    
    # 뉴스가 아예 없을 경우를 대비한 멘트
    if not news_text or len(news_text) < 10:
        news_text = "(현재 검색된 특이 뉴스가 없습니다. 시장 전반적인 분위기만 간단히 코멘트해주세요.)"

    # 프롬프트 (반복 설명 금지 조항 추가)
    prompt = f"""
    [역할] 너는 주식 비서야.
    [사용자 보유 종목] PSTG(퓨어스토리지), SPHD(고배당 ETF), VOO(S&P500)
    
    [최신 뉴스 데이터]
    {news_text}
    
    [지시사항]
    1. 위 '뉴스 데이터'를 바탕으로 한국어 브리핑을 작성해.
    2. 뉴스가 없으면 억지로 지어내지 말고 "현재 특별한 뉴스가 없습니다"라고 솔직하게 말해.
    3. 종목에 대한 '사전적 정의'(이 회사는 뭐하는 회사고...)는 절대 하지 마. 매번 똑같은 말은 지겨워.
    4. 오직 '새로운 소식'이나 '현재 가격/등락' 위주로만 전달해.
    5. 출처가 있다면 꼭 명시해줘.
    """
    
    print("브리핑 생성 중...")
    msg = ask_gemini(model_name, prompt)

    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        print("전송 성공!")
    except Exception as e:
        print(f"전송 실패: {e}")

if __name__ == "__main__":
    asyncio.run(main())
