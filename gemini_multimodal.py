import json
import logging
import os
import time
import random
import uuid
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel
import pytesseract
from PIL import Image
import speech_recognition as sr
from pydub import AudioSegment
import tempfile


# IMPORTANT: KEEP THIS COMMENT
# Follow these instructions when using this blueprint:
# - Note that the newest Gemini model series is "gemini-2.5-flash" or gemini-2.5-pro"
#   - do not change this unless explicitly requested by the user
# - Sometimes the google genai SDK has occasional type errors. You might need to run to validate, at time.  
# The SDK was recently renamed from google-generativeai to google-genai. This file reflects the new name and the new APIs.

# This API key is from Gemini Developer API Key, not vertex AI API Key
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key != "your-gemini-api-key-here":
        client = genai.Client(api_key=api_key)
        logging.info("Gemini client initialized successfully")
    else:
        client = None
        logging.warning("Gemini API key not configured")
except Exception as e:
    client = None
    logging.error(f"Failed to initialize Gemini client: {e}")

def gemini_with_retry(func, max_retries=3, timeout=60):
    """
    تنفيذ دالة Gemini مع إعادة المحاولة التلقائية عند 503 error مع حد زمني
    """
    retry_delay = 1  # البداية بثانية واحدة
    start_time = time.time()
    
    for attempt in range(max_retries):
        try:
            # التحقق من انتهاء الوقت المسموح
            if time.time() - start_time > timeout:
                raise Exception("Timeout exceeded while waiting for Gemini API")
            
            return func()
        except Exception as e:
            error_str = str(e).lower()
            # التحقق من أخطاء 503 أو "overloaded"
            if ("503" in error_str or "overloaded" in error_str or "unavailable" in error_str or "timeout" in error_str):
                if attempt == max_retries - 1:
                    logging.error(f"Maximum retry attempts ({max_retries}) reached for Gemini API")
                    raise e
                
                # إضافة عشوائية لتجنب التحميل المتزامن
                jitter = random.uniform(0, 0.5) 
                sleep_time = min(retry_delay + jitter, 5)  # الحد الأقصى 5 ثواني بين المحاولات
                
                logging.warning(f"Gemini API overloaded (attempt {attempt + 1}/{max_retries}), retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                retry_delay = min(retry_delay * 1.5, 5)  # الحد الأقصى 5 ثواني
            else:
                # خطأ آخر، لا نعيد المحاولة
                raise e
    
    raise Exception("Maximum retry attempts reached")

def extract_text_from_image(image_path: str) -> str:
    """استخراج النص من الصورة باستخدام OCR مع تحسين الأداء"""
    try:
        # فتح الصورة وتحسين جودتها
        image = Image.open(image_path)
        
        # تصغير الصورة إذا كانت كبيرة جداً لتسريع المعالجة
        max_size = (2048, 2048)
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # تحويل إلى RGB إذا لزم الأمر
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # استخراج النص باللغة العربية والإنجليزية مع تحسين الإعدادات
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzأبتثجحخدذرزسشصضطظعغفقكلمنهوياً ة'
        text = pytesseract.image_to_string(image, lang='ara+eng', config=custom_config, timeout=30)
        
        if text.strip():
            return f"النص المستخرج من الصورة:\n\n{text.strip()}"
        else:
            return "لا يمكن استخراج نص واضح من الصورة."
            
    except Exception as e:
        logging.error(f"Error extracting text from image: {e}")
        return "فشل في استخراج النص من الصورة."

def analyze_image(image_path: str, user_question: str = None) -> str:
    """تحليل الصور عن طريق استخراج النص أولاً ثم استخدام Gemini للإجابة"""
    try:
        # استخراج النص من الصورة أولاً
        extracted_text = extract_text_from_image(image_path)
        
        if not extracted_text or "لا يمكن استخراج نص" in extracted_text or "فشل في استخراج" in extracted_text:
            return "عذراً، لا يمكنني استخراج نص واضح من هذه الصورة. يرجى التأكد من وضوح النص في الصورة."
        
        # إذا كان هناك سؤال، استخدم Gemini للإجابة بناءً على النص المستخرج
        if user_question and client:
            try:
                prompt = f"بناءً على النص التالي المستخرج من صورة:\n\n{extracted_text}\n\nأجب على السؤال التالي: {user_question}"
                
                def call_gemini():
                    return client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[prompt]
                    )
                
                response = gemini_with_retry(call_gemini)
                
                if response and response.text:
                    return f"النص المستخرج من الصورة:\n{extracted_text}\n\n---\n\nالإجابة:\n{response.text}"
                else:
                    return f"النص المستخرج من الصورة:\n{extracted_text}\n\n(لم أتمكن من تحليل المحتوى بواسطة الذكاء الاصطناعي)"
                    
            except Exception as e:
                logging.error(f"Gemini text analysis failed: {e}")
                return f"النص المستخرج من الصورة:\n{extracted_text}\n\n(خطأ في التحليل: {str(e)})"
        
        # إرجاع النص المستخرج فقط إذا لم يكن هناك سؤال أو إذا لم يكن Gemini متاح
        return extracted_text
        
    except Exception as e:
        logging.error(f"Error analyzing image: {e}")
        return f"حدث خطأ في تحليل الصورة: {str(e)}"

def extract_text_from_audio(audio_path: str) -> str:
    """استخراج النص من الملفات الصوتية باستخدام تقنية التعرف على الصوت"""
    try:
        # إنشاء مجلد مؤقت للملف المحول
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
        
        # تحويل الملف الصوتي إلى wav إذا لزم الأمر
        try:
            audio_file = AudioSegment.from_file(audio_path)
            # تقليل جودة الصوت لتسريع المعالجة وتوفير الذاكرة
            audio_file = audio_file.set_frame_rate(16000).set_channels(1)
            # تحديد مدة الصوت (الحد الأقصى 5 دقائق لتجنب التايم آوت)
            max_duration_ms = 5 * 60 * 1000  # 5 دقائق
            if len(audio_file) > max_duration_ms:
                audio_file = audio_file[:max_duration_ms]
                logging.warning(f"تم تقليل مدة الملف الصوتي إلى 5 دقائق للمعالجة")
            
            audio_file.export(temp_wav_path, format="wav")
        except Exception as e:
            logging.error(f"Error converting audio file: {e}")
            return "فشل في تحويل الملف الصوتي للمعالجة."
        
        # استخدام مكتبة التعرف على الصوت
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(temp_wav_path) as source:
                # تقليل الضوضاء
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = recognizer.record(source)
            
            # محاولة التعرف على النص بالعربية أولاً ثم الإنجليزية
            try:
                text = recognizer.recognize_google(audio_data, language="ar-SA")
                language_detected = "العربية"
            except:
                try:
                    text = recognizer.recognize_google(audio_data, language="en-US")
                    language_detected = "الإنجليزية"
                except:
                    return "عذراً، لم أتمكن من التعرف على الكلام في الملف الصوتي. يرجى التأكد من جودة التسجيل ووضوح الصوت."
            
            # تنظيف الملف المؤقت
            try:
                import os
                os.unlink(temp_wav_path)
            except:
                pass
            
            if text.strip():
                return f"النص المستخرج من الملف الصوتي (باللغة {language_detected}):\n\n{text.strip()}"
            else:
                return "لم يتم العثور على نص واضح في الملف الصوتي."
                
        except Exception as e:
            logging.error(f"Error recognizing speech: {e}")
            return "فشل في التعرف على الكلام في الملف الصوتي."
            
    except Exception as e:
        logging.error(f"Error processing audio file: {e}")
        return "حدث خطأ في معالجة الملف الصوتي."

def analyze_audio(audio_path: str, user_question: str = None) -> str:
    """تحليل الملفات الصوتية عن طريق استخراج النص أولاً ثم استخدام Gemini للإجابة"""
    try:
        # استخراج النص من الملف الصوتي أولاً
        extracted_text = extract_text_from_audio(audio_path)
        
        if not extracted_text or "فشل في" in extracted_text or "لم أتمكن" in extracted_text or "حدث خطأ" in extracted_text:
            return f"عذراً، لم أتمكن من معالجة الملف الصوتي بنجاح. {extracted_text}"
        
        # إذا كان هناك سؤال، استخدم Gemini للإجابة بناءً على النص المستخرج
        if user_question and client:
            try:
                prompt = f"بناءً على النص التالي المستخرج من ملف صوتي:\n\n{extracted_text}\n\nأجب على السؤال التالي: {user_question}"
                
                def call_gemini():
                    return client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[prompt]
                    )
                
                response = gemini_with_retry(call_gemini)
                
                if response and response.text:
                    return f"النص المستخرج من الملف الصوتي:\n{extracted_text}\n\n---\n\nالإجابة:\n{response.text}"
                else:
                    return f"النص المستخرج من الملف الصوتي:\n{extracted_text}\n\n(لم أتمكن من تحليل المحتوى بواسطة الذكاء الاصطناعي)"
                    
            except Exception as e:
                logging.error(f"Gemini audio analysis failed: {e}")
                return f"النص المستخرج من الملف الصوتي:\n{extracted_text}\n\n(خطأ في التحليل: {str(e)})"
        
        # إرجاع النص المستخرج فقط إذا لم يكن هناك سؤال أو إذا لم يكن Gemini متاح
        return extracted_text
        
    except Exception as e:
        logging.error(f"Error analyzing audio: {e}")
        return f"حدث خطأ في تحليل الملف الصوتي: {str(e)}"


def extract_text_from_pdf(file_path: str) -> str:
    """استخراج النص من ملفات PDF"""
    try:
        import PyPDF2
        import pdfplumber
        
        text_content = ""
        
        # تجربة pdfplumber أولاً (أفضل للنصوص العربية)
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    if page.extract_text():
                        text_content += page.extract_text() + "\n"
        except Exception:
            # إذا فشل pdfplumber، جرب PyPDF2
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text_content += page.extract_text() + "\n"
            except Exception as e:
                logging.error(f"Error extracting text from PDF: {e}")
                return "فشل في استخراج النص من ملف PDF"
        
        if text_content.strip():
            return f"النص المستخرج من ملف PDF:\n\n{text_content.strip()}"
        else:
            return "لا يمكن استخراج نص واضح من ملف PDF"
            
    except ImportError:
        return "مكتبات معالجة PDF غير متوفرة"
    except Exception as e:
        logging.error(f"Error processing PDF: {e}")
        return f"حدث خطأ في معالجة ملف PDF: {str(e)}"

def extract_text_from_word(file_path: str) -> str:
    """استخراج النص من ملفات Word"""
    try:
        import docx
        
        doc = docx.Document(file_path)
        text_content = ""
        
        for paragraph in doc.paragraphs:
            text_content += paragraph.text + "\n"
            
        if text_content.strip():
            return f"النص المستخرج من ملف Word:\n\n{text_content.strip()}"
        else:
            return "لا يمكن استخراج نص واضح من ملف Word"
            
    except ImportError:
        return "مكتبة معالجة Word غير متوفرة"
    except Exception as e:
        logging.error(f"Error processing Word document: {e}")
        return f"حدث خطأ في معالجة ملف Word: {str(e)}"

def extract_text_from_txt(file_path: str) -> str:
    """استخراج النص من ملفات نصية عادية"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        if content.strip():
            return f"النص المستخرج من الملف:\n\n{content.strip()}"
        else:
            return "الملف فارغ أو لا يحتوي على نص"
    except Exception as e:
        logging.error(f"Error reading text file: {e}")
        return f"حدث خطأ في قراءة الملف: {str(e)}"

def analyze_document(file_path: str, user_question: str = None) -> str:
    """تحليل الملفات النصية عن طريق استخراج النص أولاً ثم استخدام Gemini"""
    try:
        # تحديد نوع الملف
        file_extension = Path(file_path).suffix.lower()
        
        # استخراج النص حسب نوع الملف
        if file_extension == '.pdf':
            extracted_text = extract_text_from_pdf(file_path)
        elif file_extension in ['.doc', '.docx']:
            extracted_text = extract_text_from_word(file_path)
        elif file_extension == '.txt':
            extracted_text = extract_text_from_txt(file_path)
        else:
            return "نوع الملف غير مدعوم لاستخراج النص"
        
        # التحقق من نجاح استخراج النص
        if not extracted_text or "فشل في" in extracted_text or "حدث خطأ" in extracted_text:
            return f"عذراً، لم أتمكن من استخراج النص من هذا الملف. الخطأ: {extracted_text}"
        
        # إذا كان هناك سؤال، استخدم Gemini للإجابة
        if user_question and client:
            try:
                prompt = f"بناءً على النص التالي:\n\n{extracted_text}\n\nأجب على السؤال التالي: {user_question}"
                
                def call_gemini():
                    return client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[prompt]
                    )
                
                response = gemini_with_retry(call_gemini)
                
                if response and response.text:
                    return f"النص المستخرج من الملف:\n{extracted_text}\n\n---\n\nالإجابة:\n{response.text}"
                else:
                    return f"النص المستخرج من الملف:\n{extracted_text}\n\n(لم أتمكن من تحليل المحتوى بواسطة الذكاء الاصطناعي)"
                    
            except Exception as e:
                logging.error(f"Gemini text analysis failed: {e}")
                return f"النص المستخرج من الملف:\n{extracted_text}\n\n(خطأ في التحليل: {str(e)})"
        
        # إرجاع النص المستخرج فقط إذا لم يكن هناك سؤال
        return extracted_text
        
    except Exception as e:
        logging.error(f"Error analyzing document: {e}")
        return f"حدث خطأ في تحليل الملف: {str(e)}"

def analyze_video(video_path: str, user_question: str = None) -> str:
    """تحليل الفيديوهات - غير مدعوم حالياً"""
    return "عذراً، تحليل الفيديوهات غير متاح حالياً. يرجى رفع صور أو ملفات نصية (PDF/Word/TXT) بدلاً من ذلك."


def generate_image(prompt: str, output_dir: str = "generated_images") -> tuple[str | None, str]:
    """إنتاج الصور بواسطة Gemini AI مع معالجة محسنة للأخطاء"""
    try:
        # إنشاء مجلد الإخراج إذا لم يكن موجوداً
        Path(output_dir).mkdir(exist_ok=True)
        
        # إنشاء اسم ملف فريد
        unique_id = str(uuid.uuid4())[:8]
        image_filename = f"generated_image_{unique_id}.png"
        image_path = os.path.join(output_dir, image_filename)
        
        # تحسين النص للحصول على أفضل النتائج
        enhanced_prompt = f"أنشئ صورة عالية الجودة: {prompt}"
        
        def call_gemini():
            return client.models.generate_content(
                # IMPORTANT: only this gemini model supports image generation
                model="gemini-2.0-flash-exp",
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE']))
        
        response = gemini_with_retry(call_gemini)

        if not response.candidates:
            return None, "لم يتمكن Gemini من إنتاج الصورة. الخدمة قد تكون غير متوفرة حالياً."

        try:
            content = response.candidates[0].content
            if not content or not content.parts:
                return None, "لم يتم إنتاج محتوى صالح من النموذج."

            for part in content.parts:
                if part.text:
                    # طباعة وصف الصورة المولدة
                    logging.info(f"وصف الصورة: {part.text}")
                elif part.inline_data and part.inline_data.data:
                    with open(image_path, 'wb') as f:
                        f.write(part.inline_data.data)
                    return image_path, f"تم إنتاج الصورة بنجاح وحفظها في: {image_filename}"
                    
            return None, "لم يتم العثور على بيانات الصورة في الاستجابة."
            
        except Exception as e:
            logging.error(f"Error processing response: {e}")
            return None, f"خطأ في معالجة الاستجابة: {str(e)}"
            
    except Exception as e:
        error_str = str(e).lower()
        logging.error(f"Error generating image: {e}")
        
        # معالجة أخطاء محددة
        if "not supported" in error_str or "unavailable" in error_str:
            return None, "عذراً، خدمة إنتاج الصور غير متوفرة حالياً. يرجى المحاولة لاحقاً."
        elif "quota" in error_str or "limit" in error_str:
            return None, "تم تجاوز الحد المسموح لإنتاج الصور. يرجى المحاولة لاحقاً."
        elif "403" in error_str or "permission" in error_str:
            return None, "لا يوجد إذن لاستخدام خدمة إنتاج الصور."
        elif "overloaded" in error_str or "503" in error_str:
            return None, "خادم إنتاج الصور محمّل حالياً. يرجى المحاولة بعد قليل."
        else:
            return None, "حدث خطأ في إنتاج الصورة. يرجى المحاولة مرة أخرى."


def analyze_document_with_image(text_content: str, image_path: str, user_question: str) -> str:
    """تحليل المستندات مع الصور للحصول على إجابات شاملة"""
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            
        file_extension = Path(image_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(file_extension, 'image/jpeg')
        
        prompt = f"""
        لديك محتوى نصي من المنهج والصورة المرفقة. أجب على السؤال التالي بناءً على كليهما:
        
        السؤال: {user_question}
        
        المحتوى النصي:
        {text_content[:10000]}  # تحديد النص لتجنب تجاوز الحد
        
        يرجى تحليل الصورة والنص معاً وتقديم إجابة شاملة باللغة العربية.
        """
        
        def call_gemini():
            return client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type,
                    ),
                    prompt,
                ],
            )
        
        response = gemini_with_retry(call_gemini)

        return response.text if response.text else "عذراً، لم أتمكن من تحليل المحتوى."
        
    except Exception as e:
        logging.error(f"Error analyzing document with image: {e}")
        return f"حدث خطأ في تحليل المحتوى: {str(e)}"