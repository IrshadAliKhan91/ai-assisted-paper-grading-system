"""
Molmo Vision Model via OpenRouter
AI-powered vision OCR
"""
import base64
import json
import re
from pathlib import Path


class MolmoOCR:
    """Molmo vision model for OCR"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.name = "Molmo-Vision"
        self.model = "allenai/molmo-2-8b:free"
    
    def extract_text(self, image_path):
        """Extract text using Molmo vision model"""
        try:
            from openai import OpenAI
        except ImportError:
            return {"error": "openai library required: pip install openai"}
        
        try:
            # Encode image
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            ext = Path(image_path).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }.get(ext, 'image/jpeg')
            
            image_url = f"data:{mime_type};base64,{image_data}"
            
            # Initialize client
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key
            )
            
            # Call API
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all text from this image. Return only the text content, preserving the structure and formatting."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }]
            )
            
            text = completion.choices[0].message.content
            
            return {
                'model': self.name,
                'text': text,
                'raw_response': text
            }
            
        except Exception as e:
            return {'error': str(e), 'model': self.name}
