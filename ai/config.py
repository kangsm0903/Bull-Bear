"""
OpenAI 연결 설정. 모든 에이전트가 여기서 client와 MODEL을 가져다 쓴다.
모델을 바꾸려면 아래 MODEL 한 줄만 고치면 전체에 반영된다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 프로젝트 루트(ai/의 부모 폴더)의 .env를 읽어 환경변수로 올린다.
# ai/ 어디서 실행하든 항상 루트 .env를 가리키도록 절대 경로로 지정.
load_dotenv(Path(__file__).parent.parent / ".env")

# 사용할 모델 (저렴한 mini급으로 시작). 나중에 여기만 바꾸면 됨.
MODEL = "gpt-4o-mini"

# OpenAI 클라이언트. .env에서 읽은 OPENAI_API_KEY로 인증한다.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
