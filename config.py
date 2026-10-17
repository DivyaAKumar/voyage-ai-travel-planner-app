import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

AVIATIONSTACK_API_KEY=os.getenv('AVIATIONSTACK_API_KEY')
TAVILY_API_KEY=os.getenv('TAVILY_API_KEY')
DATABASE_URL=os.getenv('DATABASE_URL')
OPENWEATHER_API_KEY=os.getenv('OPENWEATHER_API_KEY')

def get_llm():
    return ChatOpenAI()