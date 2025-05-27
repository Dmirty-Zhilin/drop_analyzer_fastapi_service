import asyncio
import aiohttp
import os
import json
from typing import Dict, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Configure a basic logger for this module if not configured globally
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Путь к файлу конфигурации для хранения ключа API
CONFIG_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

# Создаем директорию config, если она не существует
CONFIG_DIR.mkdir(exist_ok=True)

# Функция для загрузки ключа API из файла конфигурации
def load_api_key():
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('openrouter_api_key')
    except Exception as e:
        logger.error(f"Error loading API key from config file: {e}")
    return None

# Функция для сохранения ключа API в файл конфигурации
def save_api_key(api_key):
    try:
        config = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                try:
                    config = json.load(f)
                except json.JSONDecodeError:
                    config = {}
        
        config['openrouter_api_key'] = api_key
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        return True
    except Exception as e:
        logger.error(f"Error saving API key to config file: {e}")
        return False

class OpenRouterService:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "openai/gpt-3.5-turbo"):
        # Приоритет: 1) переданный ключ, 2) ключ из файла конфигурации, 3) переменная окружения
        self.api_key = api_key or load_api_key() or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("OpenRouter API key is not set. Thematic analysis will not work.")
        self.base_url = "https://openrouter.ai/api/v1"
        self.model_name = model_name
        
    def set_api_key(self, api_key: str) -> bool:
        """Устанавливает и сохраняет ключ API в файл конфигурации"""
        if not api_key or not isinstance(api_key, str) or api_key.strip() == "":
            return False
            
        # Сохраняем ключ в файл
        success = save_api_key(api_key)
        if success:
            self.api_key = api_key
            return True
        return False

    async def get_thematic_analysis(self, text_content: str, domain: str) -> Dict[str, Any]:
        """Performs thematic analysis on the given text content using OpenRouter."""
        if not self.api_key:
            return {"error": "OpenRouter API key not configured."}
        if not text_content or text_content.isspace():
            return {"error": "No content provided for thematic analysis."}

        # Truncate text_content if it's too long to avoid excessive API costs/limits
        # Typical context window for gpt-3.5-turbo is around 4k tokens. 1 token ~ 4 chars.
        # Let's aim for roughly 2000-3000 words (around 10000-15000 chars) as a safe limit.
        max_chars = 15000
        if len(text_content) > max_chars:
            logger.info(f"Content for {domain} is too long ({len(text_content)} chars), truncating to {max_chars} chars for thematic analysis.")
            text_content = text_content[:max_chars]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are an expert in website content analysis. Analyze the following text from a website and provide a concise thematic summary. Identify the main topics, keywords (up to 10), and suggest a primary category for the website (e.g., E-commerce, Blog, News, Corporate, Technology, Health, etc.). Respond in JSON format with keys: 'primary_category', 'main_topics' (list of strings), 'keywords' (list of strings), and 'summary' (a brief text summary)."},
                {"role": "user", "content": f"Analyze the following website content for domain {domain}:\n\n{text_content}"}
            ]
        }

        analysis_result = {
            "domain": domain,
            "model_used": self.model_name,
            "primary_category": None,
            "main_topics": [],
            "keywords": [],
            "summary": None,
            "error": None
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        # print(f"OpenRouter Raw Response for {domain}: {data}") # For debugging
                        message_content = data.get("choices", [{}])[0].get("message", {}).get("content")
                        if message_content:
                            try:
                                # The LLM should respond in JSON format as per the prompt
                                parsed_content = await asyncio.to_thread(json.loads, message_content) # json.loads is blocking
                                analysis_result["primary_category"] = parsed_content.get("primary_category")
                                analysis_result["main_topics"] = parsed_content.get("main_topics", [])
                                analysis_result["keywords"] = parsed_content.get("keywords", [])
                                analysis_result["summary"] = parsed_content.get("summary")
                            except json.JSONDecodeError as je:
                                logger.error(f"Failed to parse JSON response from OpenRouter for {domain}: {je}. Content: {message_content}")
                                analysis_result["error"] = "Failed to parse LLM response. Content was not valid JSON."
                                analysis_result["summary"] = message_content # Store raw content if not JSON
                        else:
                            analysis_result["error"] = "No content in OpenRouter response message."
                            logger.warning(f"No content in OpenRouter response for {domain}: {data}")
                    else:
                        error_details = await response.text()
                        logger.error(f"OpenRouter API error for {domain} (Status {response.status}): {error_details}")
                        analysis_result["error"] = f"OpenRouter API error: {response.status} - {error_details[:200]}"
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error with OpenRouter for {domain}: {e}")
            analysis_result["error"] = f"OpenRouter connection error: {e}"
        except asyncio.TimeoutError:
            logger.error(f"Timeout error when calling OpenRouter for {domain}")
            analysis_result["error"] = "OpenRouter request timed out."
        except Exception as e:
            logger.exception(f"Unexpected error during OpenRouter thematic analysis for {domain}: {e}")
            analysis_result["error"] = f"An unexpected error occurred: {str(e)}"
        
        return analysis_result

# Example Usage (for testing this module):
async def main_test():
    # Ensure OPENROUTER_API_KEY is set in your environment for this test to work
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Skipping OpenRouterService test: OPENROUTER_API_KEY not set.")
        return

    service = OpenRouterService()
    sample_content = ("This website is about sustainable gardening and permaculture. "
                      "We discuss organic farming techniques, companion planting, and soil health. "
                      "Our blog features articles on composting, rainwater harvesting, and attracting beneficial insects. "
                      "We also have a shop selling heirloom seeds and eco-friendly gardening tools.")
    domain_to_test = "examplegarden.com"
    
    print(f"Performing thematic analysis for {domain_to_test}...")
    analysis = await service.get_thematic_analysis(sample_content, domain_to_test)
    print("Thematic Analysis Result:", analysis)

if __name__ == "__main__":
    import json # Required for json.loads in the main_test if the LLM responds with JSON string
    asyncio.run(main_test())

