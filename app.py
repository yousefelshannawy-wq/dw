#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Educational Bot - نظام البوت التعليمي المحدث
@author AI Assistant  
@version 3.0 - Enhanced Version with all requested features
@updated with CRUD operations, Gemini integration, and error handling
"""

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import sqlite3
import hashlib
import time
import uuid
import requests
from datetime import datetime, timedelta
import logging
import re
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()


# مكتبات لمعالجة ملفات PDF و Word
try:
    import PyPDF2
    import docx
    import pdfplumber
    import magic
except ImportError:
    print("تحذير: بعض مكتبات معالجة الملفات غير متوفرة. سيتم تثبيتها عند الحاجة.")

# إعداد التطبيق
app = Flask(__name__)

# التأكد من وجود المفاتيح الأمنية المطلوبة في الإنتاج
if os.environ.get('FLASK_ENV') == 'production':
    if not os.environ.get('SECRET_KEY'):
        raise RuntimeError("SECRET_KEY environment variable must be set in production")
    if not os.environ.get('ADMIN_PASSWORD'):
        raise RuntimeError("ADMIN_PASSWORD environment variable must be set in production")

app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# إعدادات الجلسة الآمنة
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=300 * 1024 * 1024  # 300MB max file size
)

# تمكين CORS for Replit environment - must allow all hosts for proxy to work
# In production, this should be more restrictive
if os.environ.get('FLASK_ENV') == 'production':
    replit_pattern = re.compile(r'^https://[a-z0-9-]+\.replit\.dev$')
    allowed_origins = ['http://localhost:5000', 'http://127.0.0.1:5000']
    replit_domains = os.environ.get('REPLIT_DOMAINS')
    if replit_domains:
        allowed_origins.extend(replit_domains.split(','))
    CORS(app, origins=allowed_origins, supports_credentials=True)
else:
    # Development mode - allow specific origins for Replit proxy to work
    replit_dev_domain = os.environ.get('REPLIT_DEV_DOMAIN')
    dev_origins = ['http://localhost:5000', 'http://127.0.0.1:5000']
    if replit_dev_domain:
        dev_origins.extend([f'https://{replit_dev_domain}', f'http://{replit_dev_domain}'])
    CORS(app, origins=dev_origins, supports_credentials=True)

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إعدادات قاعدة البيانات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'educational_bot.db')

def get_db_connection(timeout=10):
    """Get database connection with timeout and WAL mode"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=timeout)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA wal_autocheckpoint=1000')
    return conn

def execute_with_retry(func, max_retries=3, delay=0.1):
    """Execute database operation with retry logic"""
    import time
    for attempt in range(max_retries):
        try:
            return func()
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e) and attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
                continue
            raise
        except Exception:
            raise

# إعدادات Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'your-gemini-api-key-here')
try:
    from google import genai
    # استيراد الوظائف المتقدمة لـ Gemini
    import gemini_multimodal
    
    if GEMINI_API_KEY and GEMINI_API_KEY != 'your-gemini-api-key-here':
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini AI initialized successfully")
    else:
        gemini_client = None
        logger.warning("Gemini API key not configured")
except ImportError:
    gemini_client = None
    logger.warning("google-genai package not installed")
except Exception as e:
    logger.error(f"Failed to initialize Gemini AI: {e}")
    gemini_client = None

# إعدادات الأمان
MAX_LOGIN_ATTEMPTS = 3
BLOCKED_IPS_FILE = 'blocked_ips.json'
ADMIN_SESSION_TIMEOUT = 1800  # 30 دقيقة

# الامتدادات المسموحة للملفات
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'mp3', 'wav', 'm4a', 'ogg', 'flac', 'webm'}

# مجلد رفع الملفات
UPLOAD_FOLDER = 'user_uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# مجلد تسجيل الشاتات
CHAT_LOGS_FOLDER = 'chat_logs'
os.makedirs(CHAT_LOGS_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_chat_to_file(username, user_message, bot_response, chat_info):
    """حفظ الشات في ملف منفصل لكل مستخدم مع ترميز UTF-8 صحيح"""
    try:
        # إنشاء اسم الملف باسم المستخدم
        safe_username = re.sub(r'[^\w\s-]', '', username).strip().replace(' ', '_')
        if not safe_username:
            safe_username = 'unknown_user'
        
        filename = f"{safe_username}_chat.txt"
        filepath = os.path.join(CHAT_LOGS_FOLDER, filename)
        
        # إعداد رسالة الشات مع التاريخ والترميز الصحيح
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        chat_entry = f"""
=== {timestamp} ===
المستخدم: {username}
الفرقة: {chat_info.get('grade_name', 'غير محدد')}
الترم: {chat_info.get('semester_name', 'غير محدد')}
القسم: {chat_info.get('department_name', 'غير محدد')}

السؤال: {user_message}

رد البوت: {bot_response}

{'='*50}

"""
        
        # حفظ في الملف مع ترميز UTF-8 صريح
        with open(filepath, 'a', encoding='utf-8', errors='ignore') as f:
            f.write(chat_entry)
            
        return filepath
        
    except Exception as e:
        logger.error(f"Error saving chat to file: {e}")
        return None

def get_user_chat_files():
    """جلب قائمة بملفات الشات الموجودة"""
    try:
        files = []
        for filename in os.listdir(CHAT_LOGS_FOLDER):
            if filename.endswith('_chat.txt'):
                filepath = os.path.join(CHAT_LOGS_FOLDER, filename)
                stat = os.stat(filepath)
                username = filename.replace('_chat.txt', '')
                files.append({
                    'username': username,
                    'filename': filename,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        return sorted(files, key=lambda x: x['modified'], reverse=True)
    except Exception as e:
        logger.error(f"Error getting user chat files: {e}")
        return []

def init_database():
    """إنشاء قاعدة البيانات والجداول - Enhanced Version"""
    try:
        # إنشاء مجلد قاعدة البيانات
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # جدول الدرجات/الفرق
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)

        # جدول الفصول الدراسية/الترم
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)

        # جدول الأقسام
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)

        # جدول الأسئلة والأجوبة من الكتاب
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_qa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grade_id INTEGER,
                semester_id INTEGER,
                department_id INTEGER,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (grade_id) REFERENCES grades (id),
                FOREIGN KEY (semester_id) REFERENCES semesters (id),
                FOREIGN KEY (department_id) REFERENCES departments (id)
            )
        """)

        # جدول المحادثات المحسن
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                grade_id INTEGER,
                semester_id INTEGER,
                department_id INTEGER,
                response_source TEXT DEFAULT 'manual',
                session_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (grade_id) REFERENCES grades (id),
                FOREIGN KEY (semester_id) REFERENCES semesters (id),
                FOREIGN KEY (department_id) REFERENCES departments (id)
            )
        """)

        # جدول الملفات المرفوعة
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                uploaded_by TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول البيانات المرفوعة من المطور مع الربط بالفرقة والترم
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS developer_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                file_size INTEGER,
                content TEXT,
                grade_id INTEGER,
                semester_id INTEGER,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                uploaded_by TEXT DEFAULT 'admin',
                FOREIGN KEY (grade_id) REFERENCES grades (id),
                FOREIGN KEY (semester_id) REFERENCES semesters (id)
            )
        """)

        # جدول ربط الأقسام بالفرق (many-to-many relationship) - بدون ترم
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS department_grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER,
                grade_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE CASCADE,
                FOREIGN KEY (grade_id) REFERENCES grades (id),
                UNIQUE(department_id, grade_id)
            )
        """)

        # جدول ربط الملفات بالأقسام (many-to-many relationship)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                department_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES developer_files (id) ON DELETE CASCADE,
                FOREIGN KEY (department_id) REFERENCES departments (id),
                UNIQUE(file_id, department_id)
            )
        """)

        # جدول جلسات الإدارة
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        """)

        # إنشاء فهارس لتحسين الأداء
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_username ON conversations(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_book_qa_grade_semester_dept ON book_qa(grade_id, semester_id, department_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_developer_files_grade_semester ON developer_files(grade_id, semester_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_departments_file_id ON file_departments(file_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_department_grades_dept_id ON department_grades(department_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_department_grades_grade_id ON department_grades(grade_id)')

        # إدراج البيانات الأولية
        insert_initial_data(cursor)

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

def insert_initial_data(cursor):
    """إدراج البيانات الأولية - Enhanced"""
    try:
        # إدراج الدرجات الافتراضية
        default_grades = [
            ('الصف الأول الثانوي', 'المرحلة الثانوية - الصف الأول'),
            ('الصف الثاني الثانوي', 'المرحلة الثانوية - الصف الثاني'),
            ('الصف الثالث الثانوي', 'المرحلة الثانوية - الصف الثالث'),
        ]

        for name, desc in default_grades:
            cursor.execute('INSERT OR IGNORE INTO grades (name, description) VALUES (?, ?)', (name, desc))

        # إدراج الفصول الدراسية الافتراضية
        default_semesters = [
            ('الفصل الدراسي الأول', 'الترم الأول من العام الدراسي'),
            ('الفصل الدراسي الثاني', 'الترم الثاني من العام الدراسي'),
        ]

        for name, desc in default_semesters:
            cursor.execute('INSERT OR IGNORE INTO semesters (name, description) VALUES (?, ?)', (name, desc))

        # إدراج الأقسام الافتراضية
        # تم حذف الأقسام العلمي والأدبي والتجاري حسب طلب المستخدم
        # default_departments = []
        
        # إدراج ربط افتراضي بين الأقسام والفرق فقط عند عدم وجود روابط سابقة
        # فحص ما إذا كانت هناك روابط موجودة بالفعل
        cursor.execute('SELECT COUNT(*) FROM department_grades')
        existing_links = cursor.fetchone()[0]
        
        # إذا لم تكن هناك روابط موجودة، ربط الأقسام بجميع الفرق افتراضياً
        if existing_links == 0:
            cursor.execute('SELECT id FROM departments')
            dept_ids = [row[0] for row in cursor.fetchall()]
            cursor.execute('SELECT id FROM grades')
            grade_ids = [row[0] for row in cursor.fetchall()]
            
            for dept_id in dept_ids:
                for grade_id in grade_ids:
                    cursor.execute('''
                        INSERT OR IGNORE INTO department_grades 
                        (department_id, grade_id) 
                        VALUES (?, ?)
                    ''', (dept_id, grade_id))

        # إدراج بعض الأسئلة والأجوبة النموذجية
        sample_qa = [
            (1, 1, 1, 'ما هو تعريف الجاذبية؟', 'الجاذبية هي القوة التي تجذب الأجسام نحو بعضها البعض، وهي المسؤولة عن جذب الأجسام نحو سطح الأرض.', 'جاذبية، فيزياء، قوة'),
            (1, 1, 1, 'اشرح قانون نيوتن الأول', 'قانون نيوتن الأول ينص على أن الجسم الساكن يبقى ساكناً والجسم المتحرك يبقى متحركاً في خط مستقيم بسرعة ثابتة ما لم تؤثر عليه قوة خارجية.', 'نيوتن، حركة، قانون، قصور ذاتي'),
        ]

        for grade_id, semester_id, dept_id, question, answer, keywords in sample_qa:
            cursor.execute("""INSERT OR IGNORE INTO book_qa 
                            (grade_id, semester_id, department_id, question, answer, keywords) 
                            VALUES (?, ?, ?, ?, ?, ?)""", 
                          (grade_id, semester_id, dept_id, question, answer, keywords))

    except Exception as e:
        logger.error(f"Error inserting initial data: {e}")

# تهيئة قاعدة البيانات عند بدء التطبيق
init_database()

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error serving index page: {e}")
        return "حدث خطأ في تحميل الصفحة", 500

def search_in_book(question, grade_id, semester_id, department_id):
    """البحث في أسئلة وأجوبة الكتاب مع تحسين دقة البحث"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # البحث المتقدم مع أولوية للتطابق الدقيق
        search_terms = question.strip().lower()
        
        # أولاً: بحث دقيق بنفس الفرقة والترم والقسم
        cursor.execute("""
            SELECT answer, question FROM book_qa 
            WHERE grade_id = ? AND semester_id = ? AND department_id = ?
            AND (LOWER(question) LIKE ? OR LOWER(keywords) LIKE ? OR LOWER(answer) LIKE ?)
            ORDER BY 
                CASE 
                    WHEN LOWER(question) = ? THEN 1
                    WHEN LOWER(question) LIKE ? THEN 2
                    WHEN LOWER(keywords) LIKE ? THEN 3
                    ELSE 4
                END
            LIMIT 1
        """, (grade_id, semester_id, department_id,
              f'%{search_terms}%', f'%{search_terms}%', f'%{search_terms}%',
              search_terms, f'%{search_terms}%', f'%{search_terms}%'))

        result = cursor.fetchone()
        
        # إذا لم نجد نتيجة، نبحث في نفس الفرقة والترم فقط
        if not result:
            cursor.execute("""
                SELECT answer, question FROM book_qa 
                WHERE grade_id = ? AND semester_id = ?
                AND (LOWER(question) LIKE ? OR LOWER(keywords) LIKE ?)
                ORDER BY 
                    CASE 
                        WHEN LOWER(question) LIKE ? THEN 1
                        WHEN LOWER(keywords) LIKE ? THEN 2
                        ELSE 3
                    END
                LIMIT 1
            """, (grade_id, semester_id,
                  f'%{search_terms}%', f'%{search_terms}%',
                  f'%{search_terms}%', f'%{search_terms}%'))
            result = cursor.fetchone()
        
        conn.close()

        if result:
            return result[0], 'book'
        return None, None

    except Exception as e:
        logger.error(f"Error searching in book: {e}")
        return None, None

def get_gemini_response(question, context="", grade_name="", semester_name="", department_name="", grade_id=None, semester_id=None, department_id=None):
    """الحصول على إجابة من Gemini AI مع سياق محدد ومحتوى المنهج المرفوع"""
    try:
        if not gemini_client:
            return None

        # تحضير سياق محدد ودقيق
        context_info = ""
        if grade_name and grade_name != 'غير محدد':
            context_info += f"الصف الدراسي: {grade_name}\n"
        if semester_name and semester_name != 'غير محدد':
            context_info += f"الفصل الدراسي: {semester_name}\n"
        if department_name and department_name != 'غير محدد':
            context_info += f"القسم: {department_name}\n"
        
        # جلب محتوى المنهج المرفوع للفرقة والترم والقسم المحددين
        curriculum_content = ""
        if grade_id and semester_id and department_id:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                cursor = conn.cursor()
                
                # جلب محتوى الملفات المرفوعة
                cursor.execute("""
                    SELECT df.content 
                    FROM developer_files df
                    INNER JOIN file_departments fd ON df.id = fd.file_id
                    WHERE df.grade_id = ? AND df.semester_id = ? 
                    AND fd.department_id = ? AND df.status = 'active'
                    AND df.content IS NOT NULL AND df.content != ''
                    LIMIT 3
                """, (grade_id, semester_id, department_id))
                
                curriculum_contents = cursor.fetchall()
                conn.close()
                
                if curriculum_contents:
                    curriculum_parts = []
                    for content_row in curriculum_contents:
                        if content_row[0]:
                            # قراءة المحتوى مع حد معقول لتجنب timeout
                            content = content_row[0][:100000] if len(content_row[0]) > 100000 else content_row[0]
                            curriculum_parts.append(content)
                    
                    if curriculum_parts:
                        curriculum_content = "\n\n---\n\n".join(curriculum_parts)
            except Exception as e:
                logger.error(f"Error fetching curriculum content: {e}")
        
        # تحضير النص مع السياق المحدد والتشديد على المنهج فقط
        prompt = f"""أنت مساعد تعليمي ذكي متخصص في المناهج الدراسية فقط.

معلومات السياق:
{context_info}

محتوى المنهج المرفوع:
{curriculum_content if curriculum_content else "لا يوجد محتوى منهج مرفوع لهذه الفرقة والقسم"}

السؤال: {question}

التعليمات المهمة والملزمة:
1. أجب فقط من محتوى المنهج المرفوع أعلاه
2. إذا لم تجد الإجابة في محتوى المنهج المرفوع، قل: "هذا السؤال غير موجود في المنهج المرفوع. يرجى مراجعة المنهج أو سؤال المدرس."
3. لا تجب على أسئلة عامة أو غير مرتبطة بالمنهج المرفوع
4. اركز على المحتوى التعليمي المقرر فقط
5. لا تخترع معلومات أو تضيف محتوى من خارج المنهج المرفوع
6. استشهد بأجزاء من المنهج عند الإجابة لتأكيد أن الإجابة من المصدر الصحيح"""

        # إضافة timeout للطلب مع Gemini مع retry logic
        try:
            if not gemini_client:
                return "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً."
            
            # استخدام retry logic للمحادثة النصية أيضاً
            def call_gemini_text():
                return gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
            
            response = gemini_multimodal.gemini_with_retry(call_gemini_text)
            return response.text if response else None
        except Exception as gemini_error:
            logger.error(f"Gemini API error: {gemini_error}")
            # في حالة فشل Gemini، إرسال رد بديل
            return "عذراً، حدث خطأ أثناء معالجة سؤالك. يرجى المحاولة مرة أخرى أو إعادة صياغة السؤال."

    except Exception as e:
        logger.error(f"Error getting Gemini response: {e}")
        return "عذراً، حدث خطأ في النظام. يرجى المحاولة مرة أخرى."

def check_answer_from_curriculum(gemini_answer, grade_id, semester_id, department_id):
    """التحقق من أن إجابة Gemini مستمدة من المنهج المرفوع بمطابقة فعلية للمحتوى"""
    try:
        if not gemini_answer:
            return False
            
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # جلب محتوى الملفات المرفوعة للفرقة والترم والقسم المحددين
        cursor.execute("""
            SELECT df.content 
            FROM developer_files df
            INNER JOIN file_departments fd ON df.id = fd.file_id
            WHERE df.grade_id = ? AND df.semester_id = ? 
            AND fd.department_id = ? AND df.status = 'active'
            AND df.content IS NOT NULL AND df.content != ''
        """, (grade_id, semester_id, department_id))
        
        curriculum_contents = cursor.fetchall()
        conn.close()
        
        if not curriculum_contents:
            return False
            
        # تنظيف إجابة Gemini
        gemini_clean = gemini_answer.lower().strip()
        
        # فحص كلمات الرفض أولاً - إذا كانت موجودة، فليست من المنهج
        rejection_phrases = [
            "غير موجود", "ليس في المنهج", "خارج نطاق", "غير مقرر", 
            "ليس مقرر", "غير متوفر", "لا أستطيع", "عذراً", "لا يمكنني"
        ]
        
        if any(phrase in gemini_clean for phrase in rejection_phrases):
            logger.info(f"Answer rejected due to rejection phrase")
            return False
        
        # إجراء مطابقة فعلية مع محتوى المنهج المرفوع
        for content_row in curriculum_contents:
            curriculum_text = content_row[0].lower().strip() if content_row[0] else ""
            if not curriculum_text:
                continue
            
            # إنشاء قائمة من العبارات المهمة (4+ كلمات) من إجابة Gemini
            import re
            gemini_sentences = re.split(r'[.!?。]', gemini_clean)
            gemini_phrases = []
            
            for sentence in gemini_sentences:
                words = sentence.split()
                if len(words) >= 4:
                    # أخذ عبارات من 4-8 كلمات متتالية
                    for i in range(len(words) - 3):
                        phrase = ' '.join(words[i:i+min(6, len(words)-i)])
                        if len(phrase) > 15:  # تجنب العبارات القصيرة جداً
                            gemini_phrases.append(phrase.strip())
            
            # فحص كم عبارة من Gemini موجودة في المنهج
            matches = 0
            total_phrases = len(gemini_phrases)
            
            for phrase in gemini_phrases:
                if phrase in curriculum_text:
                    matches += 1
            
            # إذا وجدنا تطابق في 15% أو أكثر من العبارات، أو 2+ عبارات، فهي من المنهج
            if total_phrases > 0 and (matches/total_phrases >= 0.15 or matches >= 2):
                logger.info(f"Answer verified as from curriculum: {matches}/{total_phrases} phrase matches")
                return True
        
        # فحص إضافي: إذا كانت الإجابة طويلة ومفصلة جداً (800+ حرف)، فهي من المنهج
        if len(gemini_answer) > 800:
            logger.info(f"Answer verified as from curriculum due to length: {len(gemini_answer)} chars")
            return True
            
        logger.info(f"Answer not verified as from curriculum")
        return False
        
    except Exception as e:
        logger.error(f"Error checking curriculum match: {e}")
        return False

@app.route('/api', methods=['GET', 'POST'])
@app.route('/api/<action>', methods=['GET', 'POST'])
def api_handler(action=None):
    """معالج API محسن مع CORS والتعامل مع الأخطاء"""
    try:
        # إعداد CORS headers
        response_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }

        # معالجة OPTIONS request
        if request.method == 'OPTIONS':
            return jsonify({'status': 'ok'}), 200, response_headers

        # الحصول على action من المعاملات
        if not action:
            action = request.args.get('action') or request.form.get('action')
            # التحقق من JSON data إذا لم نجد action في المعاملات
            if not action and request.is_json:
                json_data = request.get_json()
                action = json_data.get('action') if json_data else None

        if not action:
            logger.error(f"No action found. request.is_json: {request.is_json}, request.form: {request.form}, request.args: {request.args}")
            if request.is_json:
                logger.error(f"JSON data: {request.get_json()}")
            return jsonify({'error': 'No action specified'}), 400, response_headers
        
        logger.info(f"API action: {action}, method: {request.method}, is_json: {request.is_json}")

        # توجيه الطلبات حسب النوع
        if action == 'get_grades':
            return jsonify(get_grades()), 200, response_headers
        elif action == 'get_semesters':
            return jsonify(get_semesters()), 200, response_headers
        elif action == 'get_departments':
            return jsonify(get_departments()), 200, response_headers
        elif action == 'get_departments_by_grade':
            return jsonify(get_departments_by_grade()), 200, response_headers
        elif action == 'ask_question':
            return jsonify(handle_chat()), 200, response_headers
        elif action == 'admin_login':
            return jsonify(admin_login()), 200, response_headers
        elif action == 'admin_logout':
            return jsonify(admin_logout()), 200, response_headers
        elif action == 'validate_admin_session':
            return jsonify(check_admin_session()), 200, response_headers
        elif action == 'get_conversation_history':
            return jsonify(get_conversation_history()), 200, response_headers
        elif action == 'get_dashboard_stats':
            return jsonify(get_dashboard_stats()), 200, response_headers
        # CRUD Operations
        elif action == 'add_grade':
            return jsonify(add_grade()), 200, response_headers
        elif action == 'delete_grade':
            return jsonify(delete_grade()), 200, response_headers
        elif action == 'add_semester':
            return jsonify(add_semester()), 200, response_headers
        elif action == 'delete_semester':
            return jsonify(delete_semester()), 200, response_headers
        elif action == 'add_department':
            return jsonify(add_department()), 200, response_headers
        elif action == 'add_department_with_grades':
            return jsonify(add_department_with_grades()), 200, response_headers
        elif action == 'delete_department':
            return jsonify(delete_department()), 200, response_headers
        elif action == 'upload_developer_file':
            return jsonify(upload_developer_file()), 200, response_headers
        elif action == 'get_developer_files':
            return jsonify(get_developer_files()), 200, response_headers
        elif action == 'delete_developer_file':
            return jsonify(delete_developer_file()), 200, response_headers
        elif action == 'add_department_to_grade':
            return jsonify(add_department_to_grade()), 200, response_headers
        elif action == 'get_department_grades':
            return jsonify(get_department_grades()), 200, response_headers
        elif action == 'remove_department_from_grade':
            return jsonify(remove_department_from_grade()), 200, response_headers
        elif action == 'get_chat_files':
            return jsonify(get_chat_files()), 200, response_headers
        elif action == 'download_chat_file':
            return download_chat_file()
        elif action == 'view_chat_file':
            return jsonify(view_chat_file()), 200, response_headers
        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400, response_headers

    except Exception as e:
        logger.error(f"API handler error: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500, response_headers

def get_grades():
    """جلب قائمة الدرجات/الفرق"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, description FROM grades WHERE is_active = 1 ORDER BY name')
        grades = [{'id': row[0], 'name': row[1], 'description': row[2]} for row in cursor.fetchall()]
        conn.close()
        return {'success': True, 'grades': grades}
    except Exception as e:
        logger.error(f"Error fetching grades: {e}")
        return {'success': False, 'error': str(e)}

def get_semesters():
    """جلب قائمة الفصول الدراسية/الترم"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, description FROM semesters WHERE is_active = 1 ORDER BY name')
        semesters = [{'id': row[0], 'name': row[1], 'description': row[2]} for row in cursor.fetchall()]
        conn.close()
        return {'success': True, 'semesters': semesters}
    except Exception as e:
        logger.error(f"Error fetching semesters: {e}")
        return {'success': False, 'error': str(e)}

def get_departments():
    """جلب قائمة الأقسام"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, description FROM departments WHERE is_active = 1 ORDER BY name')
        departments = [{'id': row[0], 'name': row[1], 'description': row[2]} for row in cursor.fetchall()]
        conn.close()
        return {'success': True, 'departments': departments}
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return {'success': False, 'error': str(e)}

def get_departments_by_grade():
    """جلب الأقسام المرتبطة بفرقة معينة"""
    try:
        # Handle both JSON and query parameters
        if request.method == 'POST' and request.is_json:
            data = request.get_json()
        else:
            data = request.args
        grade_id = data.get('grade_id')
        
        if not grade_id:
            return {'success': False, 'error': 'معرف الفرقة مطلوب'}
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT d.id, d.name, d.description 
            FROM departments d
            INNER JOIN department_grades dg ON d.id = dg.department_id
            WHERE d.is_active = 1 AND dg.grade_id = ?
            ORDER BY d.name
        ''', (grade_id,))
        
        departments = [{'id': row[0], 'name': row[1], 'description': row[2]} for row in cursor.fetchall()]
        conn.close()
        return {'success': True, 'departments': departments}
    except Exception as e:
        logger.error(f"Error fetching departments by grade: {e}")
        return {'success': False, 'error': str(e)}

def handle_chat():
    """معالجة المحادثة مع البحث في الكتاب أولاً ثم Gemini"""
    try:
        data = request.get_json() if request.is_json else request.form

        # التحقق من البيانات المطلوبة
        username = data.get('username', '').strip()
        if not username:
            return {'success': False, 'error': 'اسم المستخدم مطلوب'}

        question = data.get('message', '').strip()
        file_id = data.get('file_id', '').strip()
        
        # التحقق من وجود سؤال أو ملف
        if not question and not file_id:
            return {'success': False, 'error': 'السؤال أو الملف مطلوب'}

        grade_id = data.get('gradeId')
        semester_id = data.get('semesterId') 
        department_id = data.get('departmentId')

        # جلب أسماء الفرقة والترم والقسم أولاً
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT name FROM grades WHERE id = ?', (grade_id,))
        grade_name = cursor.fetchone()
        grade_name = grade_name[0] if grade_name else 'غير محدد'
        
        cursor.execute('SELECT name FROM semesters WHERE id = ?', (semester_id,))
        semester_name = cursor.fetchone()
        semester_name = semester_name[0] if semester_name else 'غير محدد'
        
        cursor.execute('SELECT name FROM departments WHERE id = ?', (department_id,))
        department_name = cursor.fetchone()
        department_name = department_name[0] if department_name else 'غير محدد'
        
        conn.close()

        # التحقق من إجابة تأكيد المستخدم أولاً
        confirm_answer = data.get('confirm_answer')
        pending_answer = data.get('pending_answer')
        
        if confirm_answer and pending_answer:
            if confirm_answer.lower() in ['نعم', 'اه', 'موافق', 'yes', 'نعم أريد الإجابة']:
                response = pending_answer
                response_source = 'gemini'
            else:
                response = "تم إلغاء الإجابة. يمكنك إعادة صياغة السؤال أو مراجعة المعلم."
                response_source = 'cancelled'
        elif file_id:
            # معالجة الملفات المرفوعة (صور، صوتيات، مستندات) مع حماية أمنية
            try:
                # تطهير اسم الملف للحماية من path traversal
                file_id = secure_filename(file_id)
                if not file_id or file_id == '':
                    return {'success': False, 'error': 'اسم الملف غير صالح'}
                
                # بناء المسار الآمن والتحقق من أنه داخل المجلد المحدد
                file_path = os.path.join(UPLOAD_FOLDER, file_id)
                file_path = os.path.realpath(file_path)  # resolve any symlinks/relative paths
                upload_dir = os.path.realpath(UPLOAD_FOLDER)
                
                # التحقق من أن الملف داخل مجلد الرفع المحدد (منع path traversal)
                if not file_path.startswith(upload_dir):
                    logger.warning(f"Path traversal attempt detected: {file_id}")
                    return {'success': False, 'error': 'مسار الملف غير صالح'}
                
                if not os.path.exists(file_path):
                    return {'success': False, 'error': 'الملف غير موجود'}
                
                # تحديد نوع الملف والتحقق من أنه مسموح
                file_extension = file_id.rsplit('.', 1)[1].lower() if '.' in file_id else ''
                if file_extension not in ALLOWED_EXTENSIONS:
                    return {'success': False, 'error': 'نوع الملف غير مسموح'}
                
                # معالجة الملف حسب النوع
                processing_success = False
                if file_extension in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
                    # تحليل الصورة
                    try:
                        response = gemini_multimodal.analyze_image(file_path, question or "حلل هذه الصورة واستخرج النص منها")
                        processing_success = True
                    except Exception as e:
                        logger.error(f"Error analyzing image: {e}")
                        response = "حدث خطأ في تحليل الصورة"
                elif file_extension in {'pdf', 'doc', 'docx', 'txt'}:
                    # تحليل الملفات النصية
                    try:
                        if hasattr(gemini_multimodal, 'analyze_document'):
                            response = gemini_multimodal.analyze_document(file_path, question or "لخص محتوى هذا الملف")
                            processing_success = True
                        else:
                            response = "تحليل المستندات غير متوفر حالياً"
                    except Exception as e:
                        logger.error(f"Error analyzing document: {e}")
                        response = "حدث خطأ في تحليل المستند"
                elif file_extension in {'mp3', 'wav', 'm4a', 'ogg', 'flac', 'webm'}:
                    # تحليل الملفات الصوتية
                    try:
                        if hasattr(gemini_multimodal, 'analyze_audio'):
                            response = gemini_multimodal.analyze_audio(file_path, question or "استخرج النص من هذا الملف الصوتي")
                            processing_success = True
                        else:
                            response = "تحليل الملفات الصوتية غير متوفر حالياً"
                    except Exception as e:
                        logger.error(f"Error analyzing audio: {e}")
                        response = "حدث خطأ في تحليل الملف الصوتي"
                else:
                    return {'success': False, 'error': 'نوع الملف غير مدعوم للتحليل'}
                
                response_source = 'gemini_vision'
                
                # حذف الملف بعد المعالجة الناجحة فقط وبشكل آمن
                if processing_success:
                    try:
                        # التحقق مرة أخرى من أن المسار آمن قبل الحذف
                        if file_path.startswith(upload_dir) and os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Successfully processed and deleted file: {file_id}")
                    except Exception as delete_error:
                        logger.warning(f"Could not delete processed file {file_id}: {delete_error}")
                    
            except Exception as e:
                logger.error(f"Error processing uploaded file: {e}")
                response = "حدث خطأ في معالجة الملف المرفوع"
                response_source = 'error'
        else:
            # البحث في الكتاب أولاً
            book_answer, source = search_in_book(question, grade_id, semester_id, department_id)

            if book_answer:
                response = book_answer
                response_source = 'book'
            else:
                # استخدام Gemini إذا لم توجد إجابة في الكتاب
                gemini_answer = get_gemini_response(
                    question, 
                    context="",
                    grade_name=grade_name,
                    semester_name=semester_name,
                    department_name=department_name,
                    grade_id=grade_id,
                    semester_id=semester_id,
                    department_id=department_id
                )

                if gemini_answer:
                    # التحقق من أن الإجابة من المنهج المرفوع
                    is_from_curriculum = check_answer_from_curriculum(gemini_answer, grade_id, semester_id, department_id)
                    
                    # استخدام Gemini مباشرة دون سؤال المستخدم
                    response = gemini_answer
                    response_source = 'gemini'
                else:
                    response = f"عذراً، لم أتمكن من العثور على إجابة دقيقة لسؤالك حول {department_name if department_name != 'غير محدد' else 'هذا الموضوع'}. يرجى إعادة صياغة السؤال بطريقة أوضح أو مراجعة معلمك للحصول على معلومات متخصصة عن هذا الموضوع."
                    response_source = 'default'

        # حفظ المحادثة في قاعدة البيانات
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations 
            (username, user_message, bot_response, grade_id, semester_id, 
             department_id, response_source, session_id, ip_address, user_agent) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, question, response, grade_id, semester_id, department_id, 
              response_source, session.get('session_id', ''), 
              request.remote_addr, request.headers.get('User-Agent', '')))
        conn.commit()
        conn.close()
        
        # حفظ المحادثة في ملف منفصل
        chat_info = {
            'grade_name': grade_name,
            'semester_name': semester_name,
            'department_name': department_name
        }
        save_chat_to_file(username, question, response, chat_info)

        return {
            'success': True, 
            'response': response,
            'source': response_source,
            'username': username
        }

    except Exception as e:
        logger.error(f"Error in chat handler: {e}")
        return {'success': False, 'error': 'حدث خطأ في معالجة السؤال'}

# CRUD Operations for Admin Panel
def add_grade():
    """إضافة درجة/فرقة جديدة"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return {'success': False, 'error': 'اسم الدرجة مطلوب'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO grades (name, description) VALUES (?, ?)', (name, description))
        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم إضافة الدرجة بنجاح'}

    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'success': False, 'error': 'هذا الاسم موجود بالفعل. يرجى اختيار اسم آخر.'}
        return {'success': False, 'error': 'خطأ في قاعدة البيانات'}
    except Exception as e:
        logger.error(f"Error adding grade: {e}")
        return {'success': False, 'error': 'حدث خطأ في إضافة الدرجة'}

def delete_grade():
    """حذف درجة/فرقة"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        grade_id = data.get('id')

        if not grade_id:
            return {'success': False, 'error': 'معرف الدرجة مطلوب'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE grades SET is_active = 0 WHERE id = ?', (grade_id,))
        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم حذف الدرجة بنجاح'}

    except Exception as e:
        logger.error(f"Error deleting grade: {e}")
        return {'success': False, 'error': 'حدث خطأ في حذف الدرجة'}

def add_semester():
    """إضافة فصل دراسي/ترم جديد"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return {'success': False, 'error': 'اسم الفصل الدراسي مطلوب'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO semesters (name, description) VALUES (?, ?)', (name, description))
        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم إضافة الفصل الدراسي بنجاح'}

    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'success': False, 'error': 'هذا الاسم موجود بالفعل. يرجى اختيار اسم آخر.'}
        return {'success': False, 'error': 'خطأ في قاعدة البيانات'}
    except Exception as e:
        logger.error(f"Error adding semester: {e}")
        return {'success': False, 'error': 'حدث خطأ في إضافة الفصل الدراسي'}

def delete_semester():
    """حذف فصل دراسي/ترم"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        semester_id = data.get('id')

        if not semester_id:
            return {'success': False, 'error': 'معرف الفصل الدراسي مطلوب'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE semesters SET is_active = 0 WHERE id = ?', (semester_id,))
        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم حذف الفصل الدراسي بنجاح'}

    except Exception as e:
        logger.error(f"Error deleting semester: {e}")
        return {'success': False, 'error': 'حدث خطأ في حذف الفصل الدراسي'}

def add_department():
    """إضافة قسم جديد"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        if not name:
            return {'success': False, 'error': 'اسم القسم مطلوب'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO departments (name, description) VALUES (?, ?)', (name, description))
        dept_id = cursor.lastrowid
        
        # ربط القسم بجميع الفرق افتراضياً
        cursor.execute('SELECT id FROM grades WHERE is_active = 1')
        grade_ids = [row[0] for row in cursor.fetchall()]
        
        for grade_id in grade_ids:
            cursor.execute('''
                INSERT OR IGNORE INTO department_grades 
                (department_id, grade_id) 
                VALUES (?, ?)
            ''', (dept_id, grade_id))
        
        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم إضافة القسم بنجاح'}

    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'success': False, 'error': 'هذا الاسم موجود بالفعل. يرجى اختيار اسم آخر.'}
        return {'success': False, 'error': 'خطأ في قاعدة البيانات'}
    except Exception as e:
        logger.error(f"Error adding department: {e}")
        return {'success': False, 'error': 'حدث خطأ في إضافة القسم'}

def add_department_with_grades():
    """إضافة قسم مع ربطه بعدة فرق في مرة واحدة"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        grade_ids = data.get('grade_ids', [])

        if not name:
            return {'success': False, 'error': 'اسم القسم مطلوب'}

        if not grade_ids or len(grade_ids) == 0:
            return {'success': False, 'error': 'يجب اختيار فرقة واحدة على الأقل'}

        def db_operation():
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # إضافة القسم أولاً
                cursor.execute('INSERT INTO departments (name, description) VALUES (?, ?)', (name, description))
                dept_id = cursor.lastrowid
                
                # ربط القسم بالفرق المختارة
                for grade_id in grade_ids:
                    cursor.execute('''
                        INSERT OR IGNORE INTO department_grades 
                        (department_id, grade_id) 
                        VALUES (?, ?)
                    ''', (dept_id, grade_id))
                
                conn.commit()
                return dept_id
            finally:
                conn.close()
        
        dept_id = execute_with_retry(db_operation)

        return {'success': True, 'message': f'تم إضافة القسم "{name}" وربطه بـ {len(grade_ids)} فرقة بنجاح'}

    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'success': False, 'error': 'هذا الاسم موجود بالفعل. يرجى اختيار اسم آخر.'}
        return {'success': False, 'error': 'خطأ في قاعدة البيانات'}
    except Exception as e:
        logger.error(f"Error adding department with grades: {e}")
        return {'success': False, 'error': 'حدث خطأ في إضافة القسم'}

def delete_department():
    """حذف قسم نهائياً من جميع قواعد البيانات"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        department_id = data.get('id')

        if not department_id:
            return {'success': False, 'error': 'معرف القسم مطلوب'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # حذف جميع العلاقات من جدول file_departments
        cursor.execute('DELETE FROM file_departments WHERE department_id = ?', (department_id,))
        
        # حذف جميع العلاقات من جدول department_grades
        cursor.execute('DELETE FROM department_grades WHERE department_id = ?', (department_id,))
        
        # حذف القسم نفسه نهائياً
        cursor.execute('DELETE FROM departments WHERE id = ?', (department_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return {'success': False, 'error': 'القسم غير موجود'}
        
        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم حذف القسم نهائياً من جميع قواعد البيانات'}

    except Exception as e:
        logger.error(f"Error deleting department: {e}")
        return {'success': False, 'error': 'حدث خطأ في حذف القسم'}

def add_department_to_grade():
    """ربط قسم بفرقة"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        department_id = data.get('department_id')
        grade_id = data.get('grade_id')

        if not all([department_id, grade_id]):
            return {'success': False, 'error': 'يجب اختيار القسم والفرقة'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO department_grades 
            (department_id, grade_id) 
            VALUES (?, ?)
        ''', (department_id, grade_id))
        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم ربط القسم بالفرقة بنجاح'}

    except Exception as e:
        logger.error(f"Error adding department to grade: {e}")
        return {'success': False, 'error': 'حدث خطأ في ربط القسم'}

def remove_department_from_grade():
    """إزالة ربط قسم من فرقة"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        department_id = data.get('department_id')
        grade_id = data.get('grade_id')

        if not all([department_id, grade_id]):
            return {'success': False, 'error': 'يجب تحديد القسم والفرقة'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM department_grades 
            WHERE department_id = ? AND grade_id = ?
        ''', (department_id, grade_id))
        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم إزالة ربط القسم بنجاح'}

    except Exception as e:
        logger.error(f"Error removing department from grade: {e}")
        return {'success': False, 'error': 'حدث خطأ في إزالة ربط القسم'}

def get_department_grades():
    """جلب قائمة ربط الأقسام بالفرق"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                dg.id,
                d.id as dept_id, d.name as dept_name,
                g.id as grade_id, g.name as grade_name
            FROM department_grades dg
            JOIN departments d ON dg.department_id = d.id
            JOIN grades g ON dg.grade_id = g.id
            WHERE d.is_active = 1 AND g.is_active = 1
            ORDER BY d.name, g.name
        ''')
        
        results = cursor.fetchall()
        department_grades = []
        for row in results:
            department_grades.append({
                'id': row[0],
                'department': {'id': row[1], 'name': row[2]},
                'grade': {'id': row[3], 'name': row[4]}
            })
        
        conn.close()
        return {'success': True, 'department_grades': department_grades}

    except Exception as e:
        logger.error(f"Error getting department grades: {e}")
        return {'success': False, 'error': 'حدث خطأ في جلب بيانات الأقسام'}

def get_chat_files():
    """جلب قائمة ملفات الشات"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        files = get_user_chat_files()
        return {'success': True, 'chat_files': files}

    except Exception as e:
        logger.error(f"Error getting chat files: {e}")
        return {'success': False, 'error': 'حدث خطأ في جلب ملفات الشات'}

def view_chat_file():
    """عرض محتوى ملف شات معين"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        filename = data.get('filename')
        
        # إضافة تحقق إضافي من أن filename موجود
        if not filename:
            logger.error("No filename provided in view_chat_file request")
            return {'success': False, 'error': 'لم يتم تحديد اسم الملف'}
        
        if not filename or not filename.endswith('_chat.txt'):
            return {'success': False, 'error': 'اسم ملف غير صحيح'}

        filepath = os.path.join(CHAT_LOGS_FOLDER, filename)
        if not os.path.exists(filepath):
            return {'success': False, 'error': 'الملف غير موجود'}

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        return {
            'success': True, 
            'content': content,
            'filename': filename
        }

    except Exception as e:
        logger.error(f"Error viewing chat file: {e}")
        return {'success': False, 'error': 'حدث خطأ في عرض الملف'}

@app.route('/download_chat/<filename>')
def download_chat_file():
    """تحميل ملف شات معين"""
    try:
        if not check_admin_session().get('is_admin'):
            return jsonify({'success': False, 'error': 'غير مصرح لك بهذه العملية'}), 403

        filename = request.args.get('filename')
        if not filename or not filename.endswith('_chat.txt'):
            return jsonify({'success': False, 'error': 'اسم ملف غير صحيح'}), 400

        return send_from_directory(CHAT_LOGS_FOLDER, filename, as_attachment=True)

    except Exception as e:
        logger.error(f"Error downloading chat file: {e}")
        return jsonify({'success': False, 'error': 'حدث خطأ في تحميل الملف'}), 500

def upload_developer_file():
    """رفع ملف من المطور مع ربطه بالفرقة والقسم والترم"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        # التحقق من وجود ملف مرفوع
        if 'file' not in request.files:
            return {'success': False, 'error': 'لم يتم اختيار ملف'}

        file = request.files['file']
        if file.filename == '':
            return {'success': False, 'error': 'لم يتم اختيار ملف'}

        # التحقق من نوع الملف المسموح
        allowed_extensions = {'.txt', '.pdf', '.doc', '.docx'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return {'success': False, 'error': f'نوع الملف غير مدعوم. الأنواع المدعومة: {", ".join(allowed_extensions)}'}

        # التحقق من حجم الملف (الحد الأقصى 300MB)
        if hasattr(file, 'content_length') and file.content_length > 300 * 1024 * 1024:
            return {'success': False, 'error': 'حجم الملف كبير جداً. الحد الأقصى 300MB'}

        # الحصول على البيانات
        grade_id = request.form.get('grade_id')
        semester_id = request.form.get('semester_id')
        department_ids = request.form.getlist('department_ids[]')  # قائمة الأقسام

        if not all([grade_id, semester_id, department_ids]):
            return {'success': False, 'error': 'يجب اختيار الفرقة والترم والقسم'}

        # التحقق من صحة المعرفات
        try:
            grade_id = int(grade_id)
            semester_id = int(semester_id)
            department_ids = [int(dept_id) for dept_id in department_ids]
        except ValueError:
            return {'success': False, 'error': 'معرفات غير صحيحة'}

        # التحقق من وجود الفرقة والترم والأقسام في قاعدة البيانات
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM grades WHERE id = ? AND is_active = 1', (grade_id,))
        if cursor.fetchone()[0] == 0:
            conn.close()
            return {'success': False, 'error': 'الفرقة المحددة غير موجودة'}
            
        cursor.execute('SELECT COUNT(*) FROM semesters WHERE id = ? AND is_active = 1', (semester_id,))
        if cursor.fetchone()[0] == 0:
            conn.close()
            return {'success': False, 'error': 'الترم المحدد غير موجود'}
            
        for dept_id in department_ids:
            cursor.execute('SELECT COUNT(*) FROM departments WHERE id = ? AND is_active = 1', (dept_id,))
            if cursor.fetchone()[0] == 0:
                conn.close()
                return {'success': False, 'error': f'القسم ذو المعرف {dept_id} غير موجود'}
        
        conn.close()

        # حفظ الملف
        uploads_dir = os.path.join(os.getcwd(), 'uploaded_data')
        os.makedirs(uploads_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(uploads_dir, safe_filename)
        file.save(file_path)

        # قراءة محتوى الملف حسب النوع
        content = ""
        file_type = file.content_type or "unknown"
        file_size = os.path.getsize(file_path)

        try:
            if filename.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            elif filename.endswith('.pdf'):
                # معالجة ملفات PDF
                content = extract_text_from_pdf(file_path)
            elif filename.endswith(('.doc', '.docx')):
                # معالجة ملفات Word
                content = extract_text_from_docx(file_path)
        except Exception as e:
            logger.warning(f"Could not extract content from file: {e}")
            content = f"ملف من نوع {file_type} - تم رفعه بنجاح"

        # حفظ في قاعدة البيانات
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO developer_files 
            (original_filename, file_path, file_type, file_size, content, grade_id, semester_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (filename, file_path, file_type, file_size, content, grade_id, semester_id))
        
        file_id = cursor.lastrowid

        # ربط الملف بجميع الأقسام المحددة
        for dept_id in department_ids:
            cursor.execute("""
                INSERT INTO file_departments (file_id, department_id)
                VALUES (?, ?)
            """, (file_id, dept_id))

        conn.commit()
        conn.close()

        return {'success': True, 'message': 'تم رفع الملف بنجاح', 'file_id': file_id}

    except Exception as e:
        logger.error(f"Error uploading developer file: {e}")
        return {'success': False, 'error': f'حدث خطأ في رفع الملف: {str(e)}'}

def get_developer_files():
    """جلب قائمة الملفات المرفوعة من المطور"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        # إضافة فلاتر اختيارية للبحث
        grade_filter = request.args.get('grade_id')
        semester_filter = request.args.get('semester_id')
        department_filter = request.args.get('department_id')

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # بناء الاستعلام مع الفلاتر
        query = """
            SELECT df.id, df.original_filename, df.file_type, 
                   df.file_size, df.upload_date, df.status,
                   g.name as grade_name, s.name as semester_name,
                   GROUP_CONCAT(d.name) as departments
            FROM developer_files df
            LEFT JOIN grades g ON df.grade_id = g.id
            LEFT JOIN semesters s ON df.semester_id = s.id
            LEFT JOIN file_departments fd ON df.id = fd.file_id
            LEFT JOIN departments d ON fd.department_id = d.id
            WHERE df.status = 'active'
        """
        
        params = []
        if grade_filter:
            query += " AND df.grade_id = ?"
            params.append(grade_filter)
        if semester_filter:
            query += " AND df.semester_id = ?"
            params.append(semester_filter)
        if department_filter:
            query += " AND fd.department_id = ?"
            params.append(department_filter)
            
        query += " GROUP BY df.id ORDER BY df.upload_date DESC LIMIT 100"  # تحديد عدد النتائج

        cursor.execute(query, params)
        
        files = []
        for row in cursor.fetchall():
            files.append({
                'id': row[0],
                'filename': row[1],
                'file_type': row[2],
                'file_size': row[3],
                'upload_date': row[4],
                'status': row[5],
                'grade_name': row[6],
                'semester_name': row[7],
                'departments': row[8]
            })

        conn.close()
        return {'success': True, 'files': files}

    except Exception as e:
        logger.error(f"Error getting developer files: {e}")
        return {'success': False, 'error': 'حدث خطأ في جلب الملفات'}

def delete_developer_file():
    """حذف ملف من الملفات المرفوعة"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بهذه العملية'}

        data = request.get_json() if request.is_json else request.form
        file_id = data.get('file_id')

        if not file_id:
            return {'success': False, 'error': 'معرف الملف مطلوب'}

        # التحقق من صحة معرف الملف
        try:
            file_id = int(file_id)
        except ValueError:
            return {'success': False, 'error': 'معرف الملف غير صحيح'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # التحقق من وجود الملف أولاً
        cursor.execute('SELECT file_path FROM developer_files WHERE id = ? AND status = ?', (file_id, 'active'))
        file_record = cursor.fetchone()
        
        if not file_record:
            conn.close()
            return {'success': False, 'error': 'الملف غير موجود أو تم حذفه مسبقاً'}
        
        file_path = file_record[0]
        
        # تحديث حالة الملف إلى محذوف
        cursor.execute('UPDATE developer_files SET status = ? WHERE id = ?', ('deleted', file_id))
        
        # حذف روابط الأقسام (ستتم تلقائياً بسبب ON DELETE CASCADE)
        # لكن يمكننا حذفها يدوياً للتأكد
        cursor.execute('DELETE FROM file_departments WHERE file_id = ?', (file_id,))
        
        conn.commit()
        conn.close()

        # محاولة حذف الملف من النظام
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Physical file deleted: {file_path}")
        except Exception as delete_error:
            logger.warning(f"Could not delete physical file {file_path}: {delete_error}")
            # لا نفشل العملية إذا فشل حذف الملف الفيزيائي

        return {'success': True, 'message': 'تم حذف الملف بنجاح'}

    except Exception as e:
        logger.error(f"Error deleting developer file: {e}")
        return {'success': False, 'error': 'حدث خطأ في حذف الملف'}

def admin_login():
    """تسجيل دخول الإدارة"""
    try:
        data = request.get_json() if request.is_json else request.form
        password = data.get('password', '')

        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')

        if password == admin_password:
            session_id = str(uuid.uuid4())
            session['admin_session_id'] = session_id
            session['admin_login_time'] = time.time()

            # حفظ جلسة الإدارة في قاعدة البيانات
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO admin_sessions (id, ip_address, user_agent) 
                VALUES (?, ?, ?)
            """, (session_id, request.remote_addr, request.headers.get('User-Agent', '')))
            conn.commit()
            conn.close()

            return {'success': True, 'message': 'تم تسجيل الدخول بنجاح'}
        else:
            return {'success': False, 'error': 'كلمة المرور غير صحيحة'}

    except Exception as e:
        logger.error(f"Error in admin login: {e}")
        return {'success': False, 'error': 'حدث خطأ في تسجيل الدخول'}

def admin_logout():
    """تسجيل خروج الإدارة"""
    try:
        session_id = session.get('admin_session_id')
        if session_id:
            # تحديث قاعدة البيانات
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute('UPDATE admin_sessions SET is_active = 0 WHERE id = ?', (session_id,))
            conn.commit()
            conn.close()

        session.pop('admin_session_id', None)
        session.pop('admin_login_time', None)

        return {'success': True, 'message': 'تم تسجيل الخروج بنجاح'}

    except Exception as e:
        logger.error(f"Error in admin logout: {e}")
        return {'success': False, 'error': 'حدث خطأ في تسجيل الخروج'}

def check_admin_session():
    """التحقق من جلسة الإدارة"""
    try:
        session_id = session.get('admin_session_id')
        login_time = session.get('admin_login_time')

        if not session_id or not login_time:
            return {'is_admin': False, 'error': 'لم يتم تسجيل الدخول'}

        # التحقق من انتهاء صلاحية الجلسة
        if time.time() - login_time > ADMIN_SESSION_TIMEOUT:
            session.pop('admin_session_id', None)
            session.pop('admin_login_time', None)
            return {'is_admin': False, 'error': 'انتهت صلاحية الجلسة'}

        # التحقق من قاعدة البيانات
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT is_active FROM admin_sessions WHERE id = ?', (session_id,))
        result = cursor.fetchone()
        conn.close()

        if result and result[0]:
            return {'is_admin': True, 'session_id': session_id}
        else:
            return {'is_admin': False, 'error': 'جلسة غير صالحة'}

    except Exception as e:
        logger.error(f"Error checking admin session: {e}")
        return {'is_admin': False, 'error': 'خطأ في التحقق من الجلسة'}

def get_conversation_history():
    """جلب تاريخ المحادثات للإدارة"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بعرض هذه البيانات'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.username, c.user_message, c.bot_response, c.response_source,
                   c.created_at, g.name as grade_name, s.name as semester_name, 
                   d.name as department_name
            FROM conversations c
            LEFT JOIN grades g ON c.grade_id = g.id
            LEFT JOIN semesters s ON c.semester_id = s.id  
            LEFT JOIN departments d ON c.department_id = d.id
            ORDER BY c.created_at DESC
            LIMIT 100
        """)

        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                'username': row[0],
                'user_message': row[1],
                'bot_response': row[2],
                'response_source': row[3],
                'created_at': row[4],
                'grade_name': row[5],
                'semester_name': row[6],
                'department_name': row[7]
            })

        conn.close()
        return {'success': True, 'conversations': conversations}

    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")
        return {'success': False, 'error': 'حدث خطأ في جلب المحادثات'}

def get_dashboard_stats():
    """جلب إحصائيات لوحة الإدارة"""
    try:
        if not check_admin_session().get('is_admin'):
            return {'success': False, 'error': 'غير مصرح لك بعرض هذه البيانات'}

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # عدد المحادثات الإجمالي
        cursor.execute('SELECT COUNT(*) FROM conversations')
        total_conversations = cursor.fetchone()[0]

        # عدد المستخدمين الفريدين
        cursor.execute('SELECT COUNT(DISTINCT username) FROM conversations')
        unique_users = cursor.fetchone()[0]

        # المحادثات اليوم
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE DATE(created_at) = DATE('now')")
        today_conversations = cursor.fetchone()[0]

        # إحصائيات مصادر الإجابات
        cursor.execute('SELECT response_source, COUNT(*) FROM conversations GROUP BY response_source')
        response_sources = dict(cursor.fetchall())

        conn.close()

        return {
            'success': True,
            'stats': {
                'total_conversations': total_conversations,
                'unique_users': unique_users,
                'today_conversations': today_conversations,
                'response_sources': response_sources
            }
        }

    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        return {'success': False, 'error': 'حدث خطأ في جلب الإحصائيات'}

@app.route('/upload', methods=['POST'])
def upload_file():
    """رفع الملفات"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'لم يتم اختيار ملف'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'لم يتم اختيار ملف'})

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # إضافة timestamp لتجنب تضارب الأسماء
            timestamp = int(time.time())
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # حفظ معلومات الملف في قاعدة البيانات
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO uploaded_files 
                (filename, original_filename, file_path, file_size, mime_type, uploaded_by) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (filename, file.filename, file_path, 
                  os.path.getsize(file_path), file.content_type,
                  session.get('username', 'anonymous')))
            conn.commit()
            conn.close()

            return jsonify({'success': True, 'filename': filename})
        else:
            return jsonify({'success': False, 'error': 'نوع الملف غير مدعوم'})

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': 'حدث خطأ في رفع الملف'})

# ===========================================
# وظائف Gemini الجديدة للصور والفيديوهات
# ===========================================

@app.route('/api/upload-media', methods=['POST'])
def upload_user_media():
    """رفع الصور والفيديوهات من المستخدمين للتحليل"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'لم يتم اختيار ملف'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'لم يتم اختيار ملف'})
        
        # التحقق من نوع الملف (صور وملفات منصية وفيديوهات)
        allowed_media_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'avi', 'mov', 'pdf', 'doc', 'docx', 'txt'}
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_media_extensions):
            return jsonify({'success': False, 'error': 'نوع الملف غير مدعوم. يرجى رفع صور (jpg, png, gif)، ملفات نصية (pdf, doc, docx, txt) أو فيديوهات (mp4, avi, mov)'})
        
        # حفظ الملف
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join('user_uploads', unique_filename)
        
        # التأكد من وجود المجلد
        os.makedirs('user_uploads', exist_ok=True)
        file.save(file_path)
        
        # إرجاع معرف الملف للاستخدام في التحليل
        return jsonify({
            'success': True, 
            'file_id': unique_filename,
            'file_type': (
                'image' if file.filename.rsplit('.', 1)[1].lower() in {'jpg', 'jpeg', 'png', 'gif', 'webp'} 
                else 'document' if file.filename.rsplit('.', 1)[1].lower() in {'pdf', 'doc', 'docx', 'txt'}
                else 'video'
            ),
            'message': 'تم رفع الملف بنجاح. يمكنك الآن طرح سؤالك حول المحتوى.'
        })
        
    except Exception as e:
        logger.error(f"Error uploading user media: {e}")
        return jsonify({'success': False, 'error': 'حدث خطأ في رفع الملف'})

@app.route('/api/analyze-media', methods=['POST'])
def analyze_user_media():
    """تحليل الملفات المرفوعة بواسطة Gemini"""
    try:
        data = request.get_json() if request.is_json else request.form
        file_id = data.get('file_id')
        user_question = data.get('question', '')
        
        if not file_id:
            return jsonify({'success': False, 'error': 'معرف الملف مطلوب'})
        
        file_path = os.path.join('user_uploads', file_id)
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'الملف غير موجود'})
        
        # تحديد نوع الملف
        file_extension = file_id.rsplit('.', 1)[1].lower() if '.' in file_id else ''
        
        if file_extension in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
            # تحليل الصورة
            result = gemini_multimodal.analyze_image(file_path, user_question)
        elif file_extension in {'pdf', 'doc', 'docx', 'txt'}:
            # تحليل الملفات النصية
            result = gemini_multimodal.analyze_document(file_path, user_question)
        elif file_extension in {'mp3', 'wav', 'm4a', 'ogg', 'flac', 'webm'}:
            # تحليل الملفات الصوتية
            result = gemini_multimodal.analyze_audio(file_path, user_question)
        elif file_extension in {'mp4', 'avi', 'mov'}:
            # تحليل الفيديو  
            result = gemini_multimodal.analyze_video(file_path, user_question)
        else:
            return jsonify({'success': False, 'error': 'نوع الملف غير مدعوم للتحليل'})
        
        # حذف الملف بعد التحليل لتوفير المساحة
        try:
            os.remove(file_path)
        except:
            pass  # تجاهل الخطأ إذا فشل الحذف
        
        return jsonify({
            'success': True,
            'analysis': result,
            'source': 'gemini_vision'
        })
        
    except Exception as e:
        logger.error(f"Error analyzing user media: {e}")
        return jsonify({'success': False, 'error': 'حدث خطأ في تحليل الملف'})

@app.route('/api/generate-image', methods=['POST'])
def generate_image_endpoint():
    """إنتاج الصور بناءً على طلب المستخدم مع معالجة محسنة للأخطاء"""
    try:
        data = request.get_json() if request.is_json else request.form
        prompt = data.get('prompt', '').strip()
        
        if not prompt:
            return jsonify({'success': False, 'error': 'وصف الصورة مطلوب'})
        
        # استخدام مجلد static للوصول المباشر
        output_dir = "static/generated_images"
        image_path, message = gemini_multimodal.generate_image(prompt, output_dir)
        
        if image_path:
            # إرجاع رابط للصورة المولدة
            image_filename = os.path.basename(image_path)
            return jsonify({
                'success': True,
                'message': message,
                'image_url': f'/static/generated_images/{image_filename}',
                'source': 'gemini_image_generation'
            })
        else:
            return jsonify({
                'success': False,
                'error': message or 'فشل في إنتاج الصورة'
            })
        
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Error generating image: {e}")
        
        # معالجة أخطاء محددة
        if "not supported" in error_msg or "unavailable" in error_msg:
            return jsonify({
                'success': False,
                'error': 'عذراً، خدمة إنتاج الصور غير متوفرة حالياً. يرجى المحاولة لاحقاً.'
            })
        elif "overloaded" in error_msg or "503" in error_msg:
            return jsonify({
                'success': False,
                'error': 'خادم إنتاج الصور محمّل حالياً. يرجى المحاولة بعد قليل.'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'حدث خطأ في إنتاج الصورة. يرجى المحاولة مرة أخرى.'
            })

@app.route('/generated-image/<filename>')
def serve_generated_image(filename):
    """عرض الصور المولدة"""
    try:
        return send_from_directory('generated_images', filename)
    except Exception as e:
        logger.error(f"Error serving generated image: {e}")
        return "الصورة غير موجودة", 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)


# ===========================================
# وظائف معالجة الملفات الجديدة
# ===========================================

def extract_text_from_pdf(file_path):
    """استخراج النص من ملف PDF"""
    try:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"خطأ في استخراج النص من PDF: {e}")
        return ""

def extract_text_from_docx(file_path):
    """استخراج النص من ملف Word (docx)"""
    try:
        doc = docx.Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        print(f"خطأ في استخراج النص من Word: {e}")
        return ""

def get_file_type(file_path):
    """تحديد نوع الملف"""
    try:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        return file_type
    except:
        # fallback للامتداد
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return 'application/pdf'
        elif ext in ['.docx', '.doc']:
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        return 'unknown'

def save_developer_file(file_obj, departments=None):
    """حفظ ملف من المطور مع استخراج النص"""
    try:
        filename = secure_filename(file_obj.filename)
        timestamp = str(int(time.time()))
        unique_filename = f"{timestamp}_{filename}"

        # إنشاء مجلد الملفات إذا لم يكن موجوداً
        upload_folder = os.path.join(app.root_path, 'uploaded_files')
        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(upload_folder, unique_filename)
        file_obj.save(file_path)

        # استخراج النص من الملف
        content = ""
        file_type = get_file_type(file_path)

        if 'pdf' in file_type.lower():
            content = extract_text_from_pdf(file_path)
            file_ext = 'pdf'
        elif 'word' in file_type.lower() or 'document' in file_type.lower():
            content = extract_text_from_docx(file_path)
            file_ext = 'docx'
        else:
            file_ext = os.path.splitext(filename)[1][1:]

        # حفظ معلومات الملف في قاعدة البيانات
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO developer_files (filename, original_filename, file_path, 
                                       file_type, file_size, content_extracted)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (unique_filename, filename, file_path, file_ext, 
              os.path.getsize(file_path), content))

        file_id = cursor.lastrowid

        # ربط الملف بالأقسام المختارة
        if departments:
            for dept_id in departments:
                cursor.execute("""
                    INSERT OR IGNORE INTO file_departments (file_id, department_id)
                    VALUES (?, ?)
                """, (file_id, dept_id))

        conn.commit()
        conn.close()

        return {'success': True, 'file_id': file_id, 'filename': unique_filename}

    except Exception as e:
        print(f"خطأ في حفظ الملف: {e}")
        return {'success': False, 'error': str(e)}

def get_user_or_create(session_id, ip_address, user_agent):
    """الحصول على المستخدم أو إنشاء واحد جديد"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # البحث عن المستخدم
    cursor.execute("SELECT id FROM users WHERE session_id = ?", (session_id,))
    user = cursor.fetchone()

    if not user:
        # إنشاء مستخدم جديد
        cursor.execute("""
            INSERT INTO users (session_id, ip_address, user_agent)
            VALUES (?, ?, ?)
        """, (session_id, ip_address, user_agent))
        user_id = cursor.lastrowid
    else:
        user_id = user[0]
        # تحديث آخر نشاط
        cursor.execute("""
            UPDATE users SET last_activity = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user_id,))

    conn.commit()
    conn.close()
    return user_id

def save_conversation_enhanced(session_id, user_question, bot_response, grade_id, semester_id, department_id):
    """حفظ المحادثة مع تسجيل كامل للشات"""
    try:
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')

        # الحصول على معرف المستخدم
        user_id = get_user_or_create(session_id, ip_address, user_agent)

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # الحصول على رقم المحادثة التالي للمستخدم
        cursor.execute("""
            SELECT COALESCE(MAX(conversation_index), 0) + 1 
            FROM conversations 
            WHERE user_id = ?
        """, (user_id,))
        conv_index = cursor.fetchone()[0]

        # حفظ السؤال
        cursor.execute("""
            INSERT INTO conversations 
            (session_id, user_question, bot_response, grade_id, semester_id, 
             department_id, user_id, conversation_index, message_type)
            VALUES (?, ?, '', ?, ?, ?, ?, ?, 'question')
        """, (session_id, user_question, grade_id, semester_id, department_id, 
              user_id, conv_index))

        # حفظ الإجابة
        cursor.execute("""
            INSERT INTO conversations 
            (session_id, user_question, bot_response, grade_id, semester_id, 
             department_id, user_id, conversation_index, message_type)
            VALUES (?, '', ?, ?, ?, ?, ?, ?, 'answer')
        """, (session_id, bot_response, grade_id, semester_id, department_id, 
              user_id, conv_index))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"خطأ في حفظ المحادثة: {e}")
        return False

\

# ===========================================
# Routes جديدة للميزات المطلوبة
# ===========================================

@app.route('/admin/upload-file', methods=['GET', 'POST'])
def admin_upload_file():
    """صفحة رفع الملفات من المطور"""
    if request.method == 'GET':
        # إحضار الأقسام والفرق للعرض
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM grades ORDER BY name")
        grades = cursor.fetchall()

        cursor.execute("SELECT id, name FROM semesters ORDER BY name")
        semesters = cursor.fetchall()

        cursor.execute("SELECT d.id, d.name, g.name as grade_name FROM departments d LEFT JOIN grades g ON d.grade_id = g.id ORDER BY d.name")
        departments = cursor.fetchall()

        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'grades': grades,
                'semesters': semesters,
                'departments': departments
            }
        })

    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'لم يتم اختيار ملف'})

            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'لم يتم اختيار ملف'})

            # التحقق من نوع الملف
            allowed_extensions = ['.pdf', '.doc', '.docx']
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({'success': False, 'error': 'نوع الملف غير مدعوم. يُقبل فقط PDF و Word'})

            # الحصول على الأقسام المختارة
            departments = request.form.getlist('departments[]')
            if not departments:
                return jsonify({'success': False, 'error': 'يجب اختيار قسم واحد على الأقل'})

            # حفظ الملف
            result = save_developer_file(file, departments)

            if result['success']:
                return jsonify({
                    'success': True,
                    'message': 'تم رفع الملف بنجاح',
                    'file_id': result['file_id']
                })
            else:
                return jsonify({'success': False, 'error': result['error']})

        except Exception as e:
            return jsonify({'success': False, 'error': f'خطأ في رفع الملف: {str(e)}'})

@app.route('/admin/manage-departments', methods=['GET', 'POST'])
def admin_manage_departments():
    """إدارة الأقسام وربطها بالفرق"""
    if request.method == 'GET':
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # إحضار جميع الأقسام مع معلومات الفرقة والفصل
        cursor.execute("""
            SELECT d.id, d.name, d.grade_id, d.semester_id, 
                   g.name as grade_name, s.name as semester_name
            FROM departments d
            LEFT JOIN grades g ON d.grade_id = g.id
            LEFT JOIN semesters s ON d.semester_id = s.id
            ORDER BY d.name
        """)
        departments = cursor.fetchall()

        cursor.execute("SELECT id, name FROM grades ORDER BY name")
        grades = cursor.fetchall()

        cursor.execute("SELECT id, name FROM semesters ORDER BY name")
        semesters = cursor.fetchall()

        conn.close()

        return jsonify({
            'success': True,
            'departments': departments,
            'grades': grades,
            'semesters': semesters
        })

    if request.method == 'POST':
        try:
            action = request.json.get('action')

            if action == 'update_department':
                dept_id = request.json.get('department_id')
                grade_id = request.json.get('grade_id')
                semester_id = request.json.get('semester_id')

                conn = sqlite3.connect(DATABASE_PATH)
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE departments 
                    SET grade_id = ?, semester_id = ?
                    WHERE id = ?
                """, (grade_id, semester_id, dept_id))

                conn.commit()
                conn.close()

                return jsonify({'success': True, 'message': 'تم تحديث القسم بنجاح'})

            elif action == 'add_department':
                name = request.json.get('name')
                grade_id = request.json.get('grade_id')
                semester_id = request.json.get('semester_id')

                conn = sqlite3.connect(DATABASE_PATH)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO departments (name, grade_id, semester_id)
                    VALUES (?, ?, ?)
                """, (name, grade_id, semester_id))

                conn.commit()
                conn.close()

                return jsonify({'success': True, 'message': 'تم إضافة القسم بنجاح'})

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/chat-logs')
def admin_chat_logs():
    """عرض سجلات الشات منفصلة لكل مستخدم"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # إحضار المستخدمين مع عدد المحادثات
        cursor.execute("""
            SELECT u.id, u.session_id, u.ip_address, u.created_at,
                   COUNT(DISTINCT c.conversation_index) as total_conversations,
                   MAX(u.last_activity) as last_activity
            FROM users u
            LEFT JOIN conversations c ON u.id = c.user_id
            GROUP BY u.id
            ORDER BY u.last_activity DESC
        """)
        users = cursor.fetchall()

        conn.close()

        return jsonify({
            'success': True,
            'users': users
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/user-chat/<int:user_id>')
def admin_user_chat(user_id):
    """عرض محادثات مستخدم معين"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # إحضار محادثات المستخدم مرتبة حسب التسلسل
        cursor.execute("""
            SELECT c.conversation_index, c.user_question, c.bot_response, 
                   c.message_type, c.created_at, g.name as grade_name, 
                   s.name as semester_name, d.name as department_name
            FROM conversations c
            LEFT JOIN grades g ON c.grade_id = g.id
            LEFT JOIN semesters s ON c.semester_id = s.id
            LEFT JOIN departments d ON c.department_id = d.id
            WHERE c.user_id = ?
            ORDER BY c.conversation_index, c.created_at
        """, (user_id,))
        conversations = cursor.fetchall()

        # إحضار معلومات المستخدم
        cursor.execute("""
            SELECT session_id, ip_address, user_agent, created_at, last_activity
            FROM users WHERE id = ?
        """, (user_id,))
        user_info = cursor.fetchone()

        conn.close()

        return jsonify({
            'success': True,
            'user_info': user_info,
            'conversations': conversations
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/files')
def admin_files():
    """عرض الملفات المرفوعة من المطور"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT df.id, df.original_filename, df.file_type, 
                   df.file_size, df.upload_date, df.status,
                   GROUP_CONCAT(d.name) as departments
            FROM developer_files df
            LEFT JOIN file_departments fd ON df.id = fd.file_id
            LEFT JOIN departments d ON fd.department_id = d.id
            WHERE df.status = 'active'
            GROUP BY df.id
            ORDER BY df.upload_date DESC
        """)
        files = cursor.fetchall()

        conn.close()

        return jsonify({
            'success': True,
            'files': files
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)