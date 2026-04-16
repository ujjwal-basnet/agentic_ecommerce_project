from langchain_google_genai import ChatGoogleGenerativeAI

project="genai-492514"
location="us-central1"


model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    
    location=location , # Optional, defaults to us-central1
    temperature=1.0,  # Gemini 3.0+ defaults to 1.0
    max_tokens=None,
    timeout=None,
    max_retries=2,
)


messages = [
    (
        "system",
        "You are a helpful assistant that translates English to French. Translate the user sentence.",
    ),
    ("human", "I love programming."),
]
ai_msg = model.invoke(messages)
print(ai_msg)