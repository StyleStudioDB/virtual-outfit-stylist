def call_gemini_outfits(contents, api_key):
    """Calls Gemini 3.5 Flash Lite to return structured JSON outfits."""
    model_name = 'gemini-3.5-flash-lite'
    
    for attempt in range(2):
        try:
            if NEW_SDK:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        tools=[get_trending_fashion_items],
                        response_mime_type="application/json"
                    )
                )
                raw_text = response.text
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name, tools=[get_trending_fashion_items])
                response = model.generate_content(contents)
                raw_text = response.text

            # 1. Prevent the NoneType JSON error
            if not raw_text:
                finish_reason = "Unknown"
                if hasattr(response, 'candidates') and response.candidates:
                    if hasattr(response.candidates[0], 'finish_reason'):
                        finish_reason = str(response.candidates[0].finish_reason)
                
                raise ValueError(
                    f"API returned an empty response (Finish Reason: {finish_reason}). "
                    "This usually means a Safety Filter blocked the model photos."
                )

            # 2. Safely parse the text
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)

        except Exception as e:
            if attempt == 0 and ("503" in str(e) or "UNAVAILABLE" in str(e)):
                time.sleep(1.5)
                continue
            else:
                raise e
