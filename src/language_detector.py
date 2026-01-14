"""
Language Detector
Automatically detect source language from text using AI.
"""

import logging
import json
import re
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class LanguageDetector:
    """Detect source language using AI (Gemini/Claude)."""

    # Comprehensive language support (ISO 639-1 codes)
    SUPPORTED_LANGUAGES = {
        'auto': 'Auto-Detect',
        # East Asian
        'ja': 'Japanese (日本語)',
        'zh': 'Chinese Simplified (简体中文)',
        'zh-TW': 'Chinese Traditional (繁體中文)',
        'ko': 'Korean (한국어)',
        # European
        'en': 'English',
        'es': 'Spanish (Español)',
        'fr': 'French (Français)',
        'de': 'German (Deutsch)',
        'pt': 'Portuguese (Português)',
        'it': 'Italian (Italiano)',
        'nl': 'Dutch (Nederlands)',
        'pl': 'Polish (Polski)',
        'ru': 'Russian (Русский)',
        'uk': 'Ukrainian (Українська)',
        'cs': 'Czech (Čeština)',
        'sk': 'Slovak (Slovenčina)',
        'ro': 'Romanian (Română)',
        'hu': 'Hungarian (Magyar)',
        'el': 'Greek (Ελληνικά)',
        # Scandinavian
        'sv': 'Swedish (Svenska)',
        'no': 'Norwegian (Norsk)',
        'da': 'Danish (Dansk)',
        'fi': 'Finnish (Suomi)',
        # Other
        'ar': 'Arabic (العربية)',
        'he': 'Hebrew (עברית)',
        'hi': 'Hindi (हिन्दी)',
        'th': 'Thai (ไทย)',
        'vi': 'Vietnamese (Tiếng Việt)',
        'id': 'Indonesian (Bahasa Indonesia)',
        'tr': 'Turkish (Türkçe)',
        'fa': 'Persian (فارسی)',
        'bn': 'Bengali (বাংলা)',
        'ur': 'Urdu (اردو)',
        'ta': 'Tamil (தமிழ்)',
        'te': 'Telugu (తెలుగు)',
        'mr': 'Marathi (मराठी)',
        'gu': 'Gujarati (ગુજરાતી)',
        'kn': 'Kannada (ಕನ್ನಡ)',
        'ml': 'Malayalam (മലയാളം)',
        'pa': 'Punjabi (ਪੰਜਾਬੀ)',
    }

    def __init__(self, ai_client=None):
        """
        Initialize with AI client (Gemini/Claude).

        Args:
            ai_client: AI client with generate_content method
                       If None, will try to import and create Gemini client
        """
        self.ai_client = ai_client

        if not self.ai_client:
            # Try to initialize Gemini client
            try:
                from google import genai
                import os

                api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
                # Use 2.0 Flash (fast, efficient for simple language detection)
                model_name = os.getenv('LANGUAGE_MODEL', 'gemini-2.0-flash')
                self.ai_client = genai.Client(api_key=api_key)
                self.model_name = model_name
                logger.info(f"Initialized Gemini {model_name} for language detection")
            except Exception as e:
                logger.warning(f"Could not initialize AI client: {e}")
                self.ai_client = None

    def detect_language(self, text_sample: str) -> Dict[str, Any]:
        """
        Detect language from text sample.

        Args:
            text_sample: Text extracted from OCR (first 500 chars is enough)

        Returns:
            {
                'language': 'ja',  # ISO 639-1 code
                'language_name': 'Japanese (日本語)',
                'confidence': 0.98,  # 0.0 to 1.0
                'script': 'kanji/hiragana/katakana'
            }
        """
        if not text_sample or not text_sample.strip():
            logger.warning("Empty text sample provided for language detection")
            return self._default_response()

        # Truncate to first 500 chars for efficiency
        sample = text_sample.strip()[:500]

        # Quick heuristic check before AI call (saves API costs)
        heuristic_result = self._heuristic_detection(sample)
        if heuristic_result and heuristic_result['confidence'] > 0.9:
            logger.info(f"Heuristic detection: {heuristic_result['language_name']} "
                       f"(confidence: {heuristic_result['confidence']:.2%})")
            return heuristic_result

        # Use AI for more complex cases
        if self.ai_client:
            try:
                ai_result = self._ai_detection(sample)
                logger.info(f"AI detection: {ai_result['language_name']} "
                           f"(confidence: {ai_result['confidence']:.2%})")
                return ai_result
            except Exception as e:
                logger.error(f"AI detection failed: {e}, falling back to heuristic")
                return heuristic_result or self._default_response()
        else:
            # No AI client, use heuristic only
            logger.warning("No AI client available, using heuristic detection only")
            return heuristic_result or self._default_response()

    def _heuristic_detection(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Fast heuristic-based language detection using character ranges.
        """
        # Count characters by Unicode range
        char_counts = {
            'hiragana': 0,
            'katakana': 0,
            'kanji': 0,
            'hangul': 0,
            'chinese': 0,
            'arabic': 0,
            'cyrillic': 0,
            'thai': 0,
            'latin': 0,
        }

        for char in text:
            code = ord(char)

            # Japanese
            if 0x3040 <= code <= 0x309F:
                char_counts['hiragana'] += 1
            elif 0x30A0 <= code <= 0x30FF:
                char_counts['katakana'] += 1
            elif 0x4E00 <= code <= 0x9FFF:
                char_counts['kanji'] += 1

            # Korean
            elif 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF:
                char_counts['hangul'] += 1

            # Arabic
            elif 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F:
                char_counts['arabic'] += 1

            # Cyrillic (Russian, Ukrainian, etc.)
            elif 0x0400 <= code <= 0x04FF:
                char_counts['cyrillic'] += 1

            # Thai
            elif 0x0E00 <= code <= 0x0E7F:
                char_counts['thai'] += 1

            # Latin (English, European languages)
            elif (0x0041 <= code <= 0x005A or  # A-Z
                  0x0061 <= code <= 0x007A):    # a-z
                char_counts['latin'] += 1

        total_chars = sum(char_counts.values())
        if total_chars == 0:
            return None

        # Calculate percentages
        percentages = {k: v / total_chars for k, v in char_counts.items()}

        # Japanese detection
        if percentages['hiragana'] > 0.1 or percentages['katakana'] > 0.05:
            # Mix of hiragana/katakana indicates Japanese
            confidence = min(0.95, percentages['hiragana'] + percentages['katakana'] + 0.5)
            return {
                'language': 'ja',
                'language_name': self.SUPPORTED_LANGUAGES['ja'],
                'confidence': confidence,
                'script': 'kanji/hiragana/katakana',
                'method': 'heuristic'
            }

        # Korean detection
        if percentages['hangul'] > 0.3:
            return {
                'language': 'ko',
                'language_name': self.SUPPORTED_LANGUAGES['ko'],
                'confidence': min(0.95, percentages['hangul'] + 0.3),
                'script': 'hangul',
                'method': 'heuristic'
            }

        # Chinese detection (more kanji, no hiragana/katakana)
        if percentages['kanji'] > 0.3 and percentages['hiragana'] == 0:
            return {
                'language': 'zh',
                'language_name': self.SUPPORTED_LANGUAGES['zh'],
                'confidence': min(0.90, percentages['kanji'] + 0.2),
                'script': 'hanzi',
                'method': 'heuristic'
            }

        # Arabic detection
        if percentages['arabic'] > 0.5:
            return {
                'language': 'ar',
                'language_name': self.SUPPORTED_LANGUAGES['ar'],
                'confidence': min(0.95, percentages['arabic'] + 0.3),
                'script': 'arabic',
                'method': 'heuristic'
            }

        # Russian/Cyrillic detection
        if percentages['cyrillic'] > 0.5:
            return {
                'language': 'ru',
                'language_name': self.SUPPORTED_LANGUAGES['ru'],
                'confidence': min(0.90, percentages['cyrillic'] + 0.2),
                'script': 'cyrillic',
                'method': 'heuristic'
            }

        # Thai detection
        if percentages['thai'] > 0.5:
            return {
                'language': 'th',
                'language_name': self.SUPPORTED_LANGUAGES['th'],
                'confidence': min(0.95, percentages['thai'] + 0.3),
                'script': 'thai',
                'method': 'heuristic'
            }

        # Latin-based (lower confidence, needs AI)
        if percentages['latin'] > 0.7:
            return {
                'language': 'en',  # Default to English for Latin
                'language_name': self.SUPPORTED_LANGUAGES['en'],
                'confidence': 0.5,  # Low confidence, needs AI verification
                'script': 'latin',
                'method': 'heuristic'
            }

        return None

    def _ai_detection(self, text: str) -> Dict[str, Any]:
        """Use AI to detect language."""
        prompt = f"""
Detect the language of this text sample. Return ONLY a JSON object, no other text.

Text sample:
"{text}"

Return this exact JSON format:
{{
    "language": "ISO-639-1 code (e.g., 'ja', 'zh', 'ko', 'en', 'es', 'fr', 'de')",
    "confidence": 0.98,
    "script": "writing system (e.g., 'kanji', 'latin', 'cyrillic', 'hangul', 'arabic')"
}}

Common languages:
- ja: Japanese
- zh: Chinese
- ko: Korean
- en: English
- es: Spanish
- fr: French
- de: German
- ru: Russian
- ar: Arabic
- hi: Hindi
- th: Thai
- vi: Vietnamese
"""

        response = self.ai_client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        result = self._parse_json_response(response)

        # Add language name
        lang_code = result.get('language', 'en')
        result['language_name'] = self.SUPPORTED_LANGUAGES.get(
            lang_code,
            f"Unknown ({lang_code})"
        )
        result['method'] = 'ai'

        # Ensure confidence is between 0 and 1
        result['confidence'] = max(0.0, min(1.0, result.get('confidence', 0.5)))

        return result

    def _parse_json_response(self, response) -> dict:
        """Parse AI response into JSON."""
        # Get text from response
        text = response.text if hasattr(response, 'text') else str(response)

        # Try to find JSON in response
        json_match = re.search(r'\{[^}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")

        # Fallback: try to extract values manually
        logger.warning("Could not parse JSON, using fallback extraction")

        # Extract language code
        lang_match = re.search(r'"language":\s*"([a-z-]+)"', text, re.IGNORECASE)
        conf_match = re.search(r'"confidence":\s*([0-9.]+)', text)

        return {
            'language': lang_match.group(1) if lang_match else 'en',
            'confidence': float(conf_match.group(1)) if conf_match else 0.5,
            'script': 'unknown'
        }

    def _default_response(self) -> Dict[str, Any]:
        """Return default response (Japanese for backward compatibility)."""
        return {
            'language': 'ja',
            'language_name': self.SUPPORTED_LANGUAGES['ja'],
            'confidence': 0.0,
            'script': 'unknown',
            'method': 'default'
        }

    @classmethod
    def get_language_name(cls, lang_code: str) -> str:
        """Get language name from ISO code."""
        return cls.SUPPORTED_LANGUAGES.get(lang_code, f"Unknown ({lang_code})")

    @classmethod
    def is_supported(cls, lang_code: str) -> bool:
        """Check if language code is supported."""
        return lang_code in cls.SUPPORTED_LANGUAGES


# Convenience function
def detect_language(text_sample: str, ai_client=None) -> Dict[str, Any]:
    """
    Convenience function to detect language.

    Args:
        text_sample: Text to analyze
        ai_client: Optional AI client

    Returns:
        Language detection result
    """
    detector = LanguageDetector(ai_client)
    return detector.detect_language(text_sample)
