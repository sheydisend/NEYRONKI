import os
import json
import tempfile
import librosa
import requests
from typing import Dict, Any
from yt_dlp import YoutubeDL
from whisper import load_model

class VideoAnalyzer:
    def __init__(self):
        self.mistral_api_key = os.getenv("MISTRAL_API_KEY")
        self.mistral_api_url = "https://api.mistral.ai/v1/chat/completions"
        
        # Добавляем FFmpeg в PATH
        ffmpeg_path = r'C:\ffmpeg\bin'
        if ffmpeg_path not in os.environ['PATH']:
            os.environ['PATH'] = ffmpeg_path + os.pathsep + os.environ['PATH']
        
        if self.mistral_api_key and self.mistral_api_key != "your-mistral-api-key-here":
            print("✅ Mistral AI client initialized successfully")
        else:
            print("❌ Mistral API key not found or not configured")
    
    def _get_video_info(self, video_url: str) -> Dict[str, Any]:
        """
        Получает базовую информацию о видео
        """
        try:
            ydl_opts = {
                'quiet': True,
                'cookiefile': 'cookies.txt',
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'uploader': info.get('uploader', 'Unknown Uploader'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'view_count': info.get('view_count', 0),
                    'description': info.get('description', ''),
                    'success': True
                }
        except Exception as e:
            print(f"❌ Error getting video info: {e}")
            return {
                'title': 'Unknown Title',
                'uploader': 'Unknown Uploader',
                'duration': 0,
                'thumbnail': '',
                'view_count': 0,
                'success': False
            }
    
    def analyze_video_suitability(self, video_url: str, user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основной метод анализа видео на соответствие предпочтениям пользователя
        через транскрибацию аудио
        """
        print(f"🔍 Analyzing video: {video_url}")
        print(f"📊 User preferences: {user_preferences}")
        
        # Получаем информацию о видео
        video_info = self._get_video_info(video_url)
        
        # Транскрибируем аудио видео
        print("🎵 Starting audio transcription...")
        transcription_result = self._download_and_transcribe_audio(video_url)
        
        if not transcription_result.get('success', False):
            error_msg = f"Failed to transcribe audio: {transcription_result.get('error')}"
            print(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'is_suitable': False,
                'video_info': video_info  # Все равно возвращаем информацию о видео
            }
        
        transcription = transcription_result['transcription']
        print(f"📝 Transcription completed ({len(transcription)} characters)")
        
        # Анализируем через Mistral AI
        mistral_result = self._analyze_with_mistral(transcription, user_preferences, video_url)
        if mistral_result:
            print("✅ Using Mistral AI analysis")
            return {
                'success': True,
                'video_info': video_info,
                'transcription_preview': transcription[:500] + "..." if len(transcription) > 500 else transcription,
                'word_count': len(transcription.split()),
                'analysis': mistral_result,
                'is_suitable': mistral_result.get('is_suitable', False)
            }
        
        # Fallback анализ
        print("🔄 Using fallback analysis")
        fallback_result = self._fallback_analysis(transcription, user_preferences)
        return {
            'success': True,
            'video_info': video_info,
            'transcription_preview': transcription[:500] + "..." if len(transcription) > 500 else transcription,
            'word_count': len(transcription.split()),
            'analysis': fallback_result,
            'is_suitable': fallback_result.get('is_suitable', False)
        }
    
    def _download_and_transcribe_audio(self, url: str) -> Dict[str, Any]:
        """
        Скачивает аудио и транскрибирует его
        """
        try:
            # Создаем временную директорию, которая автоматически удалится
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_path = os.path.join(temp_dir, "audio.%(ext)s")
                
                ydl_opts = {
                    'quiet': True,
                    'format': 'bestaudio/best',
                    'cookiefile': 'cookies.txt',
                    'ffmpeg_location': r'C:\ffmpeg\bin',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': audio_path,
                }
                
                print("📥 Downloading audio...")
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # Находим созданный файл
                final_audio_path = None
                for file in os.listdir(temp_dir):
                    if file.startswith("audio."):
                        final_audio_path = os.path.join(temp_dir, file)
                        break
                
                if not final_audio_path:
                    return {
                        'success': False,
                        'error': "Audio file was not created"
                    }
                
                print(f"🔊 Found audio file: {final_audio_path}")
                print("🎤 Transcribing audio...")
                
                # Транскрибируем
                audio, sr = librosa.load(final_audio_path, sr=16000)
                model = load_model('base')
                transcription = model.transcribe(audio)
                
                return {
                    'success': True,
                    'transcription': transcription['text'],
                    'language': transcription.get('language', 'unknown')
                }
                
        except Exception as e:
            print(f"❌ Audio transcription failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _analyze_with_mistral(self, transcription: str, user_preferences: Dict[str, Any], video_url: str) -> Dict[str, Any]:
        """
        Анализ транскрипции с помощью Mistral AI
        """
        if not self.mistral_api_key or self.mistral_api_key == "your-mistral-api-key-here":
            return None
        
        try:
            prompt = self._build_mistral_prompt(transcription, user_preferences)
            
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "mistral-medium",
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты - AI помощник для анализа YouTube видео. Анализируй ТОЛЬКО на основе транскрибированного текста. Отвечай ТОЛЬКО в формате JSON."
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
            response = requests.post(self.mistral_api_url, headers=headers, json=payload, timeout=60)
            
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
    
    def _build_mistral_prompt(self, transcription: str, user_preferences: Dict[str, Any]) -> str:
        """
        Строит промпт для Mistral AI на основе транскрипции
        """
        # Обрезаем транскрипцию если слишком длинная
        max_transcription_length = 4000
        if len(transcription) > max_transcription_length:
            transcription = transcription[:max_transcription_length] + "... [текст обрезан]"
        
        # Предпочтения пользователя
        user_categories = user_preferences.get('preferred_categories', [])
        user_languages = user_preferences.get('preferred_languages', ['русский'])
        educational_pref = user_preferences.get('educational_preference', False)
        entertainment_pref = user_preferences.get('entertainment_preference', True)
        exclude_explicit = user_preferences.get('exclude_explicit_content', False)
        min_content_length = user_preferences.get('min_content_length', 100)
        
        word_count = len(transcription.split())
        
        prompt = f"""
        ПРОАНАЛИЗИРУЙ транскрибированный текст YouTube видео на соответствие предпочтениям пользователя.

        === ТРАНСКРИБИРОВАННЫЙ ТЕКСТ ВИДЕО ===
        {transcription}

        === СТАТИСТИКА ТЕКСТА ===
        Общее количество слов: {word_count}

        === ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЯ ===
        ЖЕЛАЕМЫЕ ТЕМАТИКИ: {user_categories}
        ПРЕДПОЧТИТЕЛЬНЫЕ ЯЗЫКИ: {user_languages}
        МИНИМАЛЬНЫЙ ОБЪЕМ КОНТЕНТА: {min_content_length} слов
        ОБРАЗОВАТЕЛЬНЫЙ КОНТЕНТ: {"ДА" if educational_pref else "НЕТ"}
        РАЗВЛЕКАТЕЛЬНЫЙ КОНТЕНТ: {"ДА" if entertainment_pref else "НЕТ"}
        ИСКЛЮЧАТЬ ЯВНЫЙ КОНТЕНТ: {"ДА" if exclude_explicit else "НЕТ"}

        === КРИТЕРИИ АНАЛИЗА ===
        1. СОДЕРЖАТЕЛЬНОСТЬ: Достаточно ли текста для анализа? Минимум {min_content_length} слов
        2. ТЕМАТИКА: Соответствует ли содержание видео желаемым тематикам?
        3. ТИП КОНТЕНТА: Образовательный или развлекательный согласно предпочтениям?
        4. ЯЗЫК: Соответствует ли язык предпочтительным языкам?
        5. КАЧЕСТВО: Есть ли признаки явного или нежелательного контента?

        === ТРЕБУЕМЫЙ ФОРМАТ ОТВЕТА ===
        Ответь ТОЛЬКО в формате JSON:

        {{
            "is_suitable": true/false,
            "analysis": "Детальный анализ на русском языке",
            "confidence": 0.85,
            "reasons": [
                "Причина 1",
                "Причина 2", 
                "Причина 3"
            ],
            "match_score": 85,
            "detected_topics": ["тема1", "тема2"],
            "content_type": "educational/entertainment/mixed/unknown",
            "language_detected": "русский/английский/другой"
        }}

        Будь объективным и анализируй только представленный текст.
        """
        
        return prompt
    
    def _parse_mistral_response(self, response_text: str) -> Dict[str, Any]:
        """
        Парсит JSON ответ от Mistral AI
        """
        try:
            clean_text = response_text.strip()
            result = json.loads(clean_text)
            
            required_fields = ['is_suitable', 'analysis', 'confidence', 'reasons', 'match_score']
            if all(field in result for field in required_fields):
                if (isinstance(result['is_suitable'], bool) and
                    isinstance(result['analysis'], str) and
                    isinstance(result['confidence'], (int, float)) and
                    isinstance(result['reasons'], list) and
                    isinstance(result['match_score'], (int, float))):
                    
                    result['confidence'] = max(0.0, min(1.0, float(result['confidence'])))
                    result['match_score'] = max(0, min(100, int(result['match_score'])))
                    
                    if 'detected_topics' not in result:
                        result['detected_topics'] = []
                    if 'content_type' not in result:
                        result['content_type'] = 'unknown'
                    if 'language_detected' not in result:
                        result['language_detected'] = 'unknown'
                    
                    return result
            
            print(f"❌ Invalid response format from Mistral: {result}")
            return None
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON response from Mistral: {e}")
            return None
        except Exception as e:
            print(f"❌ Error parsing Mistral response: {e}")
            return None
    
    def _fallback_analysis(self, transcription: str, user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Простой анализ если Mistral недоступен
        """
        transcription_lower = transcription.lower()
        word_count = len(transcription.split())
        
        score = 50
        reasons = []
        detected_topics = []
        
        # Проверка объема контента
        min_content_length = user_preferences.get('min_content_length', 100)
        if word_count < min_content_length:
            score -= 30
            reasons.append(f"Слишком мало контента ({word_count} слов)")
        else:
            score += 10
            reasons.append(f"Достаточный объем контента ({word_count} слов)")
        
        # Анализ тематик
        preferred_categories = user_preferences.get('preferred_categories', [])
        if preferred_categories:
            category_matches = []
            for category in preferred_categories:
                if category.lower() in transcription_lower:
                    category_matches.append(category)
                    detected_topics.append(category)
            
            if category_matches:
                score += 20
                reasons.append(f"Найдены тематики: {', '.join(category_matches)}")
            else:
                score -= 15
                reasons.append("Тематики не соответствуют предпочтениям")
        
        # Проверка на явный контент
        if user_preferences.get('exclude_explicit_content', False):
            explicit_keywords = ['мат', 'ругательство', 'оскорбление', 'порно', 'секс', 'насилие']
            explicit_found = any(keyword in transcription_lower for keyword in explicit_keywords)
            if explicit_found:
                score -= 40
                reasons.append("Обнаружен нежелательный контент")
        
        # Определение типа контента
        educational_keywords = ['обучение', 'урок', 'курс', 'лекция', 'образование']
        entertainment_keywords = ['развлечение', 'юмор', 'смех', 'прикол', 'комедия']
        
        edu_count = sum(1 for kw in educational_keywords if kw in transcription_lower)
        ent_count = sum(1 for kw in entertainment_keywords if kw in transcription_lower)
        
        if edu_count > ent_count:
            content_type = "educational"
            if user_preferences.get('educational_preference', False):
                score += 15
        elif ent_count > edu_count:
            content_type = "entertainment"
            if user_preferences.get('entertainment_preference', True):
                score += 15
        else:
            content_type = "mixed"
        
        is_suitable = score >= 60
        
        return {
            'is_suitable': is_suitable,
            'analysis': f"Fallback анализ: контент {'соответствует' if is_suitable else 'не соответствует'} предпочтениям",
            'confidence': 0.5,
            'reasons': reasons,
            'match_score': max(0, min(100, score)),
            'detected_topics': detected_topics,
            'content_type': content_type,
            'language_detected': 'russian'
        }