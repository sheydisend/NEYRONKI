import os
import json
from typing import Dict, Any
import yt_dlp
import requests

class VideoAnalyzer:
    def __init__(self):
        self.mistral_api_key = os.getenv("MISTRAL_API_KEY")
        self.mistral_api_url = "https://api.mistral.ai/v1/chat/completions"
        
        if self.mistral_api_key and self.mistral_api_key != "your-mistral-api-key-here":
            print("✅ Mistral AI client initialized successfully")
        else:
            print("❌ Mistral API key not found or not configured")
    
    def extract_video_info(self, video_url: str) -> Dict[str, Any]:
        """
        Извлекает информацию о видео с YouTube
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                return {
                    'title': info.get('title', ''),
                    'description': info.get('description', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                    'view_count': info.get('view_count', 0),
                    'categories': info.get('categories', []),
                    'tags': info.get('tags', []),
                    'thumbnail': info.get('thumbnail', ''),
                    'success': True
                }
        except Exception as e:
            print(f"❌ Error extracting video info: {e}")
            return {
                'title': 'Unknown',
                'description': '',
                'duration': 0,
                'uploader': 'Unknown',
                'view_count': 0,
                'categories': [],
                'tags': [],
                'thumbnail': '',
                'success': False,
                'error': str(e)
            }
    
    def analyze_video_suitability(self, video_url: str, user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основной метод анализа видео на соответствие предпочтениям пользователя
        """
        print(f"🔍 Analyzing video: {video_url}")
        print(f"📊 User preferences: {user_preferences}")
        
        # Извлекаем информацию о видео
        video_info = self.extract_video_info(video_url)
        if not video_info.get('success', False):
            error_msg = f"Failed to extract video info: {video_info.get('error')}"
            print(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'is_suitable': False
            }
        
        print(f"📹 Video info extracted: {video_info['title']}")
        
        # Пробуем анализ через Mistral AI
        mistral_result = self._analyze_with_mistral(video_info, user_preferences)
        if mistral_result:
            print("✅ Using Mistral AI analysis")
            return {
                'success': True,
                'video_info': video_info,
                'analysis': mistral_result,
                'is_suitable': mistral_result.get('is_suitable', False)
            }
        
        # Если Mistral не сработал, используем улучшенный fallback анализ
        print("🔄 Using improved fallback analysis")
        fallback_result = self._improved_fallback_analysis(video_info, user_preferences)
        return {
            'success': True,
            'video_info': video_info,
            'analysis': fallback_result,
            'is_suitable': fallback_result.get('is_suitable', False)
        }
    
    def _analyze_with_mistral(self, video_info: Dict[str, Any], user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализ видео с помощью Mistral AI
        """
        if not self.mistral_api_key or self.mistral_api_key == "your-mistral-api-key-here":
            return None
        
        try:
            prompt = self._build_mistral_prompt(video_info, user_preferences)
            
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "mistral-medium",  # Можно использовать mistral-small, mistral-medium, mistral-large-latest
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты - AI помощник для анализа YouTube видео. Анализируй, насколько видео соответствует предпочтениям пользователя. Отвечай ТОЛЬКО в формате JSON."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
                "response_format": {"type": "json_object"}
            }
            
            print("🚀 Sending request to Mistral AI...")
            response = requests.post(self.mistral_api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                analysis_text = result['choices'][0]['message']['content']
                print(f"📝 Mistral AI response received")
                
                parsed_result = self._parse_mistral_response(analysis_text)
                if parsed_result:
                    print(f"✅ Mistral analysis completed: suitable={parsed_result.get('is_suitable')}, score={parsed_result.get('match_score')}")
                    return parsed_result
            else:
                print(f"❌ Mistral API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Mistral AI analysis failed: {e}")
            return None
    
    def _build_mistral_prompt(self, video_info: Dict[str, Any], user_preferences: Dict[str, Any]) -> str:
        """
        Строит промпт для Mistral AI
        """
        video_title = video_info.get('title', 'Неизвестно')
        video_description = video_info.get('description', 'Описание отсутствует')[:800]
        duration_minutes = video_info.get('duration', 0) // 60
        uploader = video_info.get('uploader', 'Неизвестный автор')
        categories = video_info.get('categories', [])
        tags = video_info.get('tags', [])[:20]
        
        # Предпочтения пользователя
        user_categories = user_preferences.get('preferred_categories', [])
        user_languages = user_preferences.get('preferred_languages', [])
        min_duration = user_preferences.get('min_duration_minutes', 0)
        max_duration = user_preferences.get('max_duration_minutes', 120)
        educational_pref = user_preferences.get('educational_preference', False)
        entertainment_pref = user_preferences.get('entertainment_preference', True)
        exclude_explicit = user_preferences.get('exclude_explicit_content', False)
        
        prompt = f"""
        ПРОАНАЛИЗИРУЙ, насколько это YouTube видео соответствует предпочтениям пользователя.

        === ИНФОРМАЦИЯ О ВИДЕО ===
        НАЗВАНИЕ: "{video_title}"
        АВТОР: {uploader}
        ОПИСАНИЕ: {video_description}
        ДЛИТЕЛЬНОСТЬ: {duration_minutes} минут
        КАТЕГОРИИ: {categories}
        ТЕГИ: {tags}

        === ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЯ ===
        ЖЕЛАЕМЫЕ КАТЕГОРИИ: {user_categories}
        ПРЕДПОЧТИТЕЛЬНЫЕ ЯЗЫКИ: {user_languages}
        ДИАПАЗОН ДЛИТЕЛЬНОСТИ: {min_duration}-{max_duration} минут
        ОБРАЗОВАТЕЛЬНЫЙ КОНТЕНТ: {"ДА" if educational_pref else "НЕТ"}
        РАЗВЛЕКАТЕЛЬНЫЙ КОНТЕНТ: {"ДА" if entertainment_pref else "НЕТ"}
        ИСКЛЮЧАТЬ ЯВНЫЙ КОНТЕНТ: {"ДА" if exclude_explicit else "НЕТ"}

        === КРИТЕРИИ АНАЛИЗА ===
        1. Соответствие тематики видео желаемым категориям пользователя
        2. Соответствие длительности видео предпочтительному диапазону  
        3. Соответствие типа контента (образовательный/развлекательный) предпочтениям
        4. Соответствие языка контента предпочтительным языкам
        5. Отсутствие явного контента (если пользователь этого хочет)

        === ТРЕБУЕМЫЙ ФОРМАТ ОТВЕТА ===
        Ответь ТОЛЬКО в формате JSON со следующей структурой:

        {{
            "is_suitable": true/false,
            "analysis": "Детальный анализ на русском языке. Объясни конкретно почему видео подходит или не подходит. Укажи соответствие по каждому критерию.",
            "confidence": 0.85,
            "reasons": [
                "Конкретная причина 1",
                "Конкретная причина 2", 
                "Конкретная причина 3"
            ],
            "match_score": 85
        }}

        Будь честным и объективным. Если видео не соответствует предпочтениям - так и скажи.
        Учитывай контекст названия, описания, тегов и категорий.
        """
        
        return prompt
    
    def _parse_mistral_response(self, response_text: str) -> Dict[str, Any]:
        """
        Парсит JSON ответ от Mistral AI
        """
        try:
            # Очищаем текст ответа
            clean_text = response_text.strip()
            
            # Парсим JSON
            result = json.loads(clean_text)
            
            # Проверяем наличие обязательных полей
            required_fields = ['is_suitable', 'analysis', 'confidence', 'reasons', 'match_score']
            if all(field in result for field in required_fields):
                # Валидируем типы данных
                if (isinstance(result['is_suitable'], bool) and
                    isinstance(result['analysis'], str) and
                    isinstance(result['confidence'], (int, float)) and
                    isinstance(result['reasons'], list) and
                    isinstance(result['match_score'], (int, float))):
                    
                    # Нормализуем значения
                    result['confidence'] = max(0.0, min(1.0, float(result['confidence'])))
                    result['match_score'] = max(0, min(100, int(result['match_score'])))
                    
                    return result
            
            print(f"❌ Invalid response format from Mistral: {result}")
            return None
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON response from Mistral: {e}")
            print(f"📄 Response was: {response_text}")
            return None
        except Exception as e:
            print(f"❌ Error parsing Mistral response: {e}")
            return None
    
    def _improved_fallback_analysis(self, video_info: Dict[str, Any], user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Улучшенный анализ когда Mistral AI недоступен
        """
        duration_minutes = video_info.get('duration', 0) / 60
        video_title = video_info.get('title', '').lower()
        video_description = video_info.get('description', '').lower()
        full_text = f"{video_title} {video_description}"
        
        reasons = []
        positive_aspects = []
        match_score = 100
        detailed_analysis = []
        
        # 1. Анализ длительности
        min_duration = user_preferences.get('min_duration_minutes', 0)
        max_duration = user_preferences.get('max_duration_minutes', 120)
        
        if duration_minutes < min_duration:
            reasons.append(f"Слишком короткое ({duration_minutes:.1f}мин < {min_duration}мин)")
            match_score -= 25
            detailed_analysis.append(f"❌ Длительность: видео слишком короткое")
        elif duration_minutes > max_duration:
            reasons.append(f"Слишком длинное ({duration_minutes:.1f}мин > {max_duration}мин)")
            match_score -= 25
            detailed_analysis.append(f"❌ Длительность: видео слишком длинное")
        else:
            positive_aspects.append(f"Длительность подходит")
            detailed_analysis.append(f"✅ Длительность: подходит ({duration_minutes:.1f}мин)")
        
        # 2. Анализ категорий и тематики
        preferred_categories = [cat.lower() for cat in user_preferences.get('preferred_categories', [])]
        
        category_keywords = {
            'python': ['python', 'программирование', 'код', 'разработка', 'programming', 'алгоритм'],
            'javascript': ['javascript', 'js', 'web', 'frontend', 'node', 'react', 'vue'],
            'программирование': ['программирование', 'код', 'разработка', 'алгоритм', 'программа', 'coding', 'software'],
            'образование': ['урок', 'курс', 'обучение', 'образование', 'tutorial', 'лекция', 'учеба', 'education'],
            'технологии': ['технологии', 'гаджеты', 'it', 'компьютер', 'техника', 'tech', 'technology'],
            'развлечения': ['развлечения', 'юмор', 'прикол', 'funny', 'comedy', 'смех', 'развлекательный', 'entertainment'],
            'музыка': ['музыка', 'песня', 'клип', 'music', 'музыкальный', 'concert', 'audio'],
            'игры': ['игры', 'гейминг', 'game', 'игровой', 'gaming', 'play', 'video game'],
            'кулинария': ['рецепт', 'готовка', 'кулинария', 'еда', 'cooking', 'recipe', 'food'],
            'путешествия': ['путешествия', 'туризм', 'поездка', 'travel', 'trip', 'tour'],
            'спорт': ['спорт', 'тренировка', 'фитнес', 'sport', 'workout', 'exercise'],
            'наука': ['наука', 'исследование', 'scientific', 'science', 'research'],
            'бизнес': ['бизнес', 'предпринимательство', 'business', 'entrepreneur'],
            'новости': ['новости', 'news', 'события', 'политика']
        }
        
        # Проверяем соответствие категорий
        category_match = False
        matched_categories = []
        for user_cat in preferred_categories:
            if user_cat in category_keywords:
                keywords = category_keywords[user_cat]
                for keyword in keywords:
                    if keyword in full_text:
                        category_match = True
                        matched_categories.append(user_cat)
                        detailed_analysis.append(f"✅ Категория: соответствует '{user_cat}' (найдено '{keyword}')")
                        break
                if category_match:
                    break
        
        if category_match and matched_categories:
            positive_aspects.append(f"Соответствует категориям: {', '.join(matched_categories)}")
        elif preferred_categories:
            reasons.append("Тематика не соответствует предпочтениям")
            match_score -= 30
            detailed_analysis.append(f"❌ Категория: не соответствует предпочтениям {preferred_categories}")
        
        # 3. Анализ образовательного/развлекательного контента
        educational_pref = user_preferences.get('educational_preference', False)
        entertainment_pref = user_preferences.get('entertainment_preference', True)
        
        educational_keywords = ['урок', 'курс', 'обучение', 'образование', 'tutorial', 'лекция', 'учеба', 'объяснение', 'how to', 'study', 'learn']
        entertainment_keywords = ['развлечения', 'юмор', 'прикол', 'funny', 'comedy', 'смех', 'шутка', 'розыгрыш', 'entertainment', 'fun', 'laugh']
        
        has_educational = any(keyword in full_text for keyword in educational_keywords)
        has_entertainment = any(keyword in full_text for keyword in entertainment_keywords)
        
        content_type_analysis = []
        
        if educational_pref:
            if has_educational:
                positive_aspects.append("Образовательный контент")
                content_type_analysis.append("✅ Образовательный: да")
            else:
                reasons.append("Не образовательный контент")
                match_score -= 20
                content_type_analysis.append("❌ Образовательный: нет")
        
        if entertainment_pref:
            if has_entertainment:
                positive_aspects.append("Развлекательный контент")
                content_type_analysis.append("✅ Развлекательный: да")
            else:
                reasons.append("Не развлекательный контент")
                match_score -= 20
                content_type_analysis.append("❌ Развлекательный: нет")
        
        detailed_analysis.extend(content_type_analysis)
        
        # 4. Анализ языка
        preferred_languages = user_preferences.get('preferred_languages', [])
        russian_keywords = ['в', 'на', 'с', 'по', 'что', 'это', 'как', 'для', 'или', 'но', 'если', 'русск', 'росси']
        english_keywords = ['the', 'and', 'for', 'with', 'this', 'that', 'what', 'how', 'why', 'when', 'english', 'eng']
        
        has_russian = any(keyword in full_text for keyword in russian_keywords)
        has_english = any(keyword in full_text for keyword in english_keywords)
        
        language_ok = False
        language_analysis = []
        
        if 'ru' in preferred_languages and has_russian:
            language_ok = True
            positive_aspects.append("Русский язык")
            language_analysis.append("✅ Язык: русский")
        elif 'ru' in preferred_languages and not has_russian:
            language_analysis.append("❌ Язык: русский не обнаружен")
        
        if 'en' in preferred_languages and has_english:
            language_ok = True
            positive_aspects.append("Английский язык")
            language_analysis.append("✅ Язык: английский")
        elif 'en' in preferred_languages and not has_english:
            language_analysis.append("❌ Язык: английский не обнаружен")
        
        if preferred_languages and not language_ok:
            reasons.append("Язык не соответствует")
            match_score -= 15
        
        detailed_analysis.extend(language_analysis)
        
        # 5. Фильтр явного контента
        if user_preferences.get('exclude_explicit_content', False):
            explicit_keywords = ['18+', 'эротика', 'секс', 'porn', 'xxx', 'adult', 'nsfw', 'нагота', 'интим', 'explicit']
            if any(keyword in full_text for keyword in explicit_keywords):
                reasons.append("Обнаружен явный контент")
                match_score = 0
                detailed_analysis.append("🚫 Содержание: обнаружен явный контент")
            else:
                detailed_analysis.append("✅ Содержание: явный контент не обнаружен")
        
        # 6. Итоговый вывод
        is_suitable = match_score >= 60
        
        # Формируем детальный анализ
        analysis_text = f"Анализ видео '{video_info['title']}':\n"
        analysis_text += "\n".join(detailed_analysis)
        
        if positive_aspects:
            analysis_text += f"\n\n📈 Положительные аспекты:\n" + "\n".join([f"• {aspect}" for aspect in positive_aspects])
        
        if reasons:
            analysis_text += f"\n\n📉 Проблемные аспекты:\n" + "\n".join([f"• {reason}" for reason in reasons])
        
        analysis_text += f"\n\n🎯 Итоговый результат: {'ПОДХОДИТ' if is_suitable else 'НЕ ПОДХОДИТ'} (оценка: {match_score}%)"
        
        if not reasons:
            reasons = ["Видео соответствует основным предпочтениям"]
        
        return {
            "is_suitable": is_suitable,
            "analysis": analysis_text,
            "confidence": max(0.0, min(1.0, match_score / 100)),
            "reasons": reasons,
            "match_score": max(0, min(100, match_score))
        }