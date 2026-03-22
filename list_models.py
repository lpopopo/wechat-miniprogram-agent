from openai import OpenAI
import sys

client = OpenAI(api_key='your-api-key-1', base_url='http://127.0.0.1:8045/v1')
try:
    models = client.models.list()
    for m in models:
        print(f"- {m.id}")
except Exception as e:
    print(f"Error: {e}")
