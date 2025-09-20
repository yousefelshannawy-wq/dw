/**
 * Educational Bot - Enhanced Frontend
 * @version 3.0 - Fixed fetch issues and added CRUD operations
 */

// إعدادات API
const API_BASE_URL = '/api';

// متغيرات عامة
let currentUsername = '';
let selectedGradeId = null;
let selectedSemesterId = null;
let selectedDepartmentId = null;

/**
 * تهيئة التطبيق
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Educational Bot...');
    initializeApp();
});

function initializeApp() {
    try {
        // تحميل البيانات الأولية
        loadInitialData();

        // إعداد مستمعي الأحداث
        setupEventListeners();

        // إعداد نماذج إدارة البيانات
        setupDataManagementForms();

        // التحقق من جلسة الإدارة
        checkAdminSession();

        console.log('App initialized successfully');
    } catch (error) {
        console.error('Error initializing app:', error);
        showAlert('حدث خطأ في تهيئة التطبيق', 'error');
    }
}

/**
 * تحميل البيانات الأولية
 */
async function loadInitialData() {
    try {
        console.log('Loading initial data...');

        // تحميل البيانات بشكل متوازي
        await Promise.all([
            loadGrades(),
            loadSemesters()
        ]);
        
        // عرض رسالة للمستخدم لاختيار الفرقة أولاً
        const container = document.getElementById('departmentCheckboxes');
        if (container) {
            container.innerHTML = '<p class="text-muted">يرجى اختيار الفرقة أولاً</p>';
        }

        console.log('Initial data loaded successfully');
    } catch (error) {
        console.error('Error loading initial data:', error);
        showAlert('حدث خطأ في تحميل البيانات', 'error');
    }
}

/**
 * تحميل الدرجات/الفرق
 */
async function loadGrades() {
    try {
        console.log('Loading grades...');
        const response = await apiRequest('get_grades');

        if (response.success && response.grades) {
            populateSelect('gradeSelect', response.grades, 'اختر الصف');
            populateAdminManagement('gradesManagement', response.grades, 'grade');
            console.log('Grades loaded:', response.grades.length);
        } else {
            throw new Error(response.error || 'Failed to load grades');
        }
    } catch (error) {
        console.error('Error loading grades:', error);
        showAlert('خطأ في تحميل الصفوف الدراسية', 'error');
    }
}

/**
 * تحميل الفصول الدراسية/الترم
 */
async function loadSemesters() {
    try {
        console.log('Loading semesters...');
        const response = await apiRequest('get_semesters');

        if (response.success && response.semesters) {
            populateSelect('semesterSelect', response.semesters, 'اختر الفصل الدراسي');
            populateAdminManagement('semestersManagement', response.semesters, 'semester');
            console.log('Semesters loaded:', response.semesters.length);
        } else {
            throw new Error(response.error || 'Failed to load semesters');
        }
    } catch (error) {
        console.error('Error loading semesters:', error);
        showAlert('خطأ في تحميل الفصول الدراسية', 'error');
    }
}

/**
 * تحميل الأقسام (جميع الأقسام)
 */
async function loadDepartments() {
    try {
        console.log('Loading departments...');
        const response = await apiRequest('get_departments');

        if (response.success && response.departments) {
            populateDepartmentCheckboxes(response.departments);
            // إزالة النموذج العام للأقسام والاحتفاظ بالنموذج المربوط بالفرق فقط
            const departmentsContainer = document.getElementById('departmentsManagement');
            if (departmentsContainer) {
                departmentsContainer.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h6 class="mb-0">إدارة الأقسام</h6>
                    </div>
                    <p class="text-muted">استخدم قسم "إضافة قسم مع الفرق" أدناه لإضافة الأقسام.</p>
                `;
            }
            console.log('Departments loaded:', response.departments.length);
        } else {
            throw new Error(response.error || 'Failed to load departments');
        }
    } catch (error) {
        console.error('Error loading departments:', error);
        showAlert('خطأ في تحميل الأقسام', 'error');
    }
}

/**
 * تحميل الأقسام المرتبطة بفرقة معينة
 */
async function loadDepartmentsByGrade(gradeId) {
    try {
        console.log('Loading departments for grade:', gradeId);
        
        if (!gradeId) {
            // إذا لم يتم اختيار فرقة، إخفاء الأقسام
            const container = document.getElementById('departmentCheckboxes');
            if (container) {
                container.innerHTML = '<p class="text-muted">يرجى اختيار الفرقة أولاً</p>';
            }
            return;
        }

        const response = await apiRequest('get_departments_by_grade', { grade_id: gradeId }, 'GET');

        if (response.success && response.departments) {
            populateDepartmentCheckboxes(response.departments);
            console.log('Departments by grade loaded:', response.departments.length);
        } else {
            const container = document.getElementById('departmentCheckboxes');
            if (container) {
                container.innerHTML = '<p class="text-muted">لا توجد أقسام مرتبطة بهذه الفرقة</p>';
            }
        }
    } catch (error) {
        console.error('Error loading departments by grade:', error);
        const container = document.getElementById('departmentCheckboxes');
        if (container) {
            container.innerHTML = '<p class="text-danger">خطأ في تحميل الأقسام</p>';
        }
    }
}

/**
 * ملء قائمة منسدلة
 */
function populateSelect(selectId, data, placeholder) {
    try {
        const select = document.getElementById(selectId);
        if (!select) {
            console.warn(`Select element ${selectId} not found`);
            return;
        }

        select.innerHTML = `<option value="">${placeholder}</option>`;

        data.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item.name;
            if (item.description) {
                option.title = item.description;
            }
            select.appendChild(option);
        });

        console.log(`Populated ${selectId} with ${data.length} items`);
    } catch (error) {
        console.error(`Error populating ${selectId}:`, error);
    }
}

/**
 * ملء صناديق اختيار الأقسام
 */
function populateDepartmentCheckboxes(departments) {
    try {
        const container = document.getElementById('departmentCheckboxes');
        if (!container) {
            console.warn('Department checkboxes container not found');
            return;
        }

        container.innerHTML = '';

        departments.forEach(department => {
            const checkboxDiv = document.createElement('div');
            checkboxDiv.className = 'form-check form-check-inline';

            checkboxDiv.innerHTML = `
                <input class="form-check-input" type="checkbox" 
                       id="dept_${department.id}" value="${department.id}">
                <label class="form-check-label" for="dept_${department.id}">
                    ${department.name}
                </label>
            `;

            container.appendChild(checkboxDiv);
        });

        console.log(`Created ${departments.length} department checkboxes`);
    } catch (error) {
        console.error('Error creating department checkboxes:', error);
    }
}

/**
 * ملء قسم إدارة البيانات في لوحة الإدارة
 */
function populateAdminManagement(containerId, data, type) {
    try {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="mb-0">إدارة ${getTypeDisplayName(type)}</h6>
                <button class="btn btn-sm btn-primary" onclick="showAddForm('${type}')">
                    <i class="fas fa-plus"></i> إضافة جديد
                </button>
            </div>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>الاسم</th>
                            <th>الوصف</th>
                            <th>الإجراءات</th>
                        </tr>
                    </thead>
                    <tbody id="${type}TableBody">
                        ${data.map(item => `
                            <tr>
                                <td>${item.name}</td>
                                <td>${item.description || '-'}</td>
                                <td>
                                    <button class="btn btn-sm btn-danger" 
                                            onclick="deleteItem('${type}', ${item.id}, '${item.name}')">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (error) {
        console.error(`Error populating ${containerId}:`, error);
    }
}

function getTypeDisplayName(type) {
    const names = {
        'grade': 'الدرجات',
        'semester': 'الفصول الدراسية', 
        'department': 'الأقسام'
    };
    return names[type] || type;
}

/**
 * إعداد مستمعي الأحداث
 */
function setupEventListeners() {
    try {
        // زر بدء المحادثة
        const startChatBtn = document.getElementById('startChatBtn');
        if (startChatBtn) {
            startChatBtn.addEventListener('click', startChat);
        }

        // زر إرسال الرسالة
        const sendBtn = document.getElementById('sendBtn');
        if (sendBtn) {
            sendBtn.addEventListener('click', sendMessage);
        }

        // حقل الرسالة - إرسال عند الضغط على Enter
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }

        // زر تسجيل دخول الإدارة
        const adminLoginBtn = document.getElementById('adminLoginBtn');
        if (adminLoginBtn) {
            adminLoginBtn.addEventListener('click', showAdminLogin);
        }

        // زر تسجيل خروج الإدارة
        const adminLogoutBtn = document.getElementById('adminLogoutBtn');
        if (adminLogoutBtn) {
            adminLogoutBtn.addEventListener('click', adminLogout);
        }

        // مستمع تغيير الفرقة لتحديث الأقسام
        const gradeSelect = document.getElementById('gradeSelect');
        if (gradeSelect) {
            gradeSelect.addEventListener('change', function() {
                const selectedGradeId = this.value;
                loadDepartmentsByGrade(selectedGradeId);
            });
        }

        // أحداث رفع الملفات وإنتاج الصور (الواجهة المدمجة)
        setupIntegratedMediaEventListeners();

        console.log('Event listeners setup completed');
    } catch (error) {
        console.error('Error setting up event listeners:', error);
    }
}

/**
 * إعداد نماذج إدارة البيانات
 */
function setupDataManagementForms() {
    try {
        // نموذج إضافة عنصر جديد
        const addItemForm = document.getElementById('addItemForm');
        if (addItemForm) {
            addItemForm.addEventListener('submit', async function(e) {
                e.preventDefault();

                const type = document.getElementById('itemType').value;
                const name = document.getElementById('itemName').value.trim();
                const description = document.getElementById('itemDescription').value.trim();

                if (!name) {
                    showAlert('الاسم مطلوب', 'error');
                    return;
                }

                try {
                    const response = await apiRequest(`add_${type}`, {
                        name: name,
                        description: description
                    }, 'POST');

                    if (response.success) {
                        showAlert(response.message, 'success');
                        $('#addItemModal').modal('hide');
                        // إعادة تحميل البيانات المحددة فقط
                        if (type === 'grade' || type === 'semester') {
                            loadInitialData();
                        } else if (type === 'department') {
                            // إعادة تحميل الأقسام للفرقة المختارة حالياً
                            const currentGradeSelect = document.getElementById('gradeSelect');
                            if (currentGradeSelect && currentGradeSelect.value) {
                                loadDepartmentsByGrade(currentGradeSelect.value);
                            }
                        }
                    } else {
                        showAlert(response.error || 'فشل في إضافة العنصر', 'error');
                    }
                } catch (error) {
                    console.error('Error adding item:', error);
                    showAlert('حدث خطأ في إضافة العنصر', 'error');
                }
            });
        }

        console.log('Data management forms setup completed');
    } catch (error) {
        console.error('Error setting up data management forms:', error);
    }
}

/**
 * بدء المحادثة
 */
function startChat() {
    try {
        const username = document.getElementById('usernameInput');
        const grade = document.getElementById('gradeSelect');
        const semester = document.getElementById('semesterSelect');

        if (!username || !username.value.trim()) {
            showAlert('يرجى إدخال اسم المستخدم', 'error');
            username?.focus();
            return;
        }

        if (!grade || !grade.value) {
            showAlert('يرجى اختيار الصف الدراسي', 'error');
            return;
        }

        if (!semester || !semester.value) {
            showAlert('يرجى اختيار الفصل الدراسي', 'error');
            return;
        }

        // الحصول على الأقسام المختارة
        const selectedDepartments = [];
        const departmentCheckboxes = document.querySelectorAll('#departmentCheckboxes input[type="checkbox"]:checked');
        departmentCheckboxes.forEach(checkbox => {
            selectedDepartments.push(parseInt(checkbox.value));
        });

        if (selectedDepartments.length === 0) {
            showAlert('يرجى اختيار قسم واحد على الأقل', 'error');
            return;
        }

        // حفظ الإعدادات
        currentUsername = username.value.trim();
        selectedGradeId = parseInt(grade.value);
        selectedSemesterId = parseInt(semester.value);
        selectedDepartmentId = selectedDepartments[0]; // أخذ أول قسم مختار

        // عرض معلومات المحادثة
        showChatInfo(selectedGradeId, selectedSemesterId, selectedDepartmentId);

        // إخفاء نموذج الإعداد وإظهار المحادثة
        document.getElementById('setupSection').style.display = 'none';
        document.getElementById('chatSection').style.display = 'block';

        // التركيز على حقل الرسالة
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.focus();
        }

        console.log('Chat started:', {
            username: currentUsername,
            gradeId: selectedGradeId,
            semesterId: selectedSemesterId,
            departmentId: selectedDepartmentId
        });

    } catch (error) {
        console.error('Error starting chat:', error);
        showAlert('حدث خطأ في بدء المحادثة', 'error');
    }
}

/**
 * عرض معلومات المحادثة
 */
function showChatInfo(gradeId, semesterId, departmentId) {
    try {
        const gradeSelect = document.getElementById('gradeSelect');
        const semesterSelect = document.getElementById('semesterSelect');

        const gradeName = gradeSelect?.options[gradeSelect.selectedIndex]?.text || 'غير محدد';
        const semesterName = semesterSelect?.options[semesterSelect.selectedIndex]?.text || 'غير محدد';

        // البحث عن اسم القسم
        let departmentName = 'غير محدد';
        const departmentCheckbox = document.querySelector(`#dept_${departmentId}`);
        if (departmentCheckbox) {
            const label = document.querySelector(`label[for="dept_${departmentId}"]`);
            departmentName = label?.textContent || 'غير محدد';
        }

        const chatInfo = document.getElementById('chatInfo');
        if (chatInfo) {
            chatInfo.innerHTML = `
                <div class="alert alert-info">
                    <strong>مرحباً ${currentUsername}!</strong><br>
                    الصف: ${gradeName} | الفصل: ${semesterName} | القسم: ${departmentName}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error showing chat info:', error);
    }
}

/**
 * إرسال رسالة
 */
async function sendMessage() {
    try {
        const messageInput = document.getElementById('messageInput');
        const message = messageInput?.value.trim();

        if (!message && !uploadedFileId) {
            showAlert('يرجى كتابة سؤال أو رفع ملف', 'error');
            return;
        }

        if (!currentUsername) {
            showAlert('يرجى بدء المحادثة أولاً', 'error');
            return;
        }

        // التحقق من طلبات إنشاء الصور تلقائياً
        const imageRequests = [
            'اعمل صورة', 'انشئ صورة', 'ارسم', 'خريطة ذهنية', 'مخطط', 'رسم بياني',
            'generate image', 'create image', 'draw', 'mind map', 'diagram', 'chart',
            'صمم', 'اصنع صورة', 'اريد صورة', 'ممكن صورة'
        ];
        
        const isImageRequest = message && imageRequests.some(keyword => 
            message.toLowerCase().includes(keyword.toLowerCase())
        );

        if (isImageRequest) {
            // إنتاج صورة تلقائياً
            await generateImageAutomatically(message);
            messageInput.value = '';
            return;
        }

        // إذا كان هناك ملف مرفوع، إضافته إلى السؤال العادي
        // (لا نحتاج دالة منفصلة بعد الآن)

        // المحادثة العادية
        // إضافة رسالة المستخدم للمحادثة
        addMessageToChat(message, 'user');

        // مسح حقل الإدخال
        messageInput.value = '';

        // إظهار مؤشر الكتابة
        showTypingIndicator();

        try {
            // إعداد بيانات الطلب
            const requestData = {
                username: currentUsername,
                message: message,
                gradeId: selectedGradeId,
                semesterId: selectedSemesterId,
                departmentId: selectedDepartmentId
            };

            // إضافة معرف الملف إذا كان مرفوعاً
            if (uploadedFileId) {
                requestData.file_id = uploadedFileId;
            }
            
            // إذا كان المستخدم يجيب على سؤال تأكيد
            if (window.waitingForConfirmation && window.pendingAnswer) {
                requestData.confirm_answer = message;
                requestData.pending_answer = window.pendingAnswer;
                // إعادة تعيين المتغيرات
                window.waitingForConfirmation = false;
                window.pendingAnswer = null;
            }
            
            // إرسال السؤال للخادم
            const response = await apiRequest('ask_question', requestData, 'POST');

            // إخفاء مؤشر الكتابة
            hideTypingIndicator();

            if (response.success) {
                // إضافة رد البوت
                addMessageToChat(response.response, 'bot', response.source);

                // مسح الملف المرفوع بعد المعالجة الناجحة
                if (uploadedFileId) {
                    clearUploadedFile();
                }
                
                // إذا كانت الإجابة تتطلب تأكيد المستخدم
                if (response.requires_confirmation && response.pending_answer) {
                    // حفظ الإجابة المعلقة للاستخدام لاحقاً
                    window.pendingAnswer = response.pending_answer;
                    window.waitingForConfirmation = true;
                }
            } else {
                addMessageToChat('عذراً، حدث خطأ في معالجة سؤالك. يرجى المحاولة مرة أخرى.', 'bot', 'error');
                showAlert(response.error || 'فشل في إرسال الرسالة', 'error');
            }
        } catch (error) {
            hideTypingIndicator();
            addMessageToChat('عذراً، حدث خطأ في الاتصال. يرجى التحقق من الاتصال والمحاولة مرة أخرى.', 'bot', 'error');
            console.error('Error sending message:', error);
        }

    } catch (error) {
        console.error('Error in sendMessage:', error);
        showAlert('حدث خطأ في إرسال الرسالة', 'error');
    }
}

/**
 * إنتاج صورة تلقائياً بناءً على طلب المستخدم
 */
async function generateImageAutomatically(prompt) {
    try {
        addMessageToChat(prompt, 'user');
        showTypingIndicator();
        showFileStatus('جارٍ إنتاج الصورة...', 'info');

        const response = await fetch('/api/generate-image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ prompt: prompt }),
            credentials: 'same-origin'
        });

        const result = await response.json();
        hideTypingIndicator();

        if (result.success) {
            addMessageToChat(`تم إنتاج الصورة بنجاح! <br><img src="${result.image_url}" class="img-fluid rounded mt-2" style="max-width: 300px;">`, 'bot', result.source);
            showFileStatus('', 'success');
        } else {
            let errorMessage = result.error || 'فشل في إنتاج الصورة';
            
            // معالجة أخطاء محددة
            if (errorMessage.includes('not supported') || errorMessage.includes('لا يدعم')) {
                errorMessage = 'عذراً، لا يمكنني إنتاج الصور حالياً. خدمة إنتاج الصور غير متوفرة.';
            }
            
            addMessageToChat(errorMessage, 'bot', 'error');
            showFileStatus(errorMessage, 'error');
        }

    } catch (error) {
        hideTypingIndicator();
        console.error('Error generating image automatically:', error);
        addMessageToChat('عذراً، لا يمكنني إنتاج الصور حالياً. حدث خطأ في النظام.', 'bot', 'error');
        showFileStatus('خطأ في إنتاج الصورة', 'error');
    }
}

/**
 * تحليل الملف المرفوع
 */
async function analyzeUploadedFile(question) {
    try {
        if (!uploadedFileId) {
            showAlert('لا يوجد ملف مرفوع للتحليل', 'error');
            return;
        }

        addMessageToChat(question, 'user');
        showTypingIndicator();
        showFileStatus('جارٍ تحليل الملف...', 'info');

        const response = await fetch('/api/analyze-media', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_id: uploadedFileId,
                question: question
            }),
            credentials: 'same-origin'
        });

        const result = await response.json();
        hideTypingIndicator();

        if (result.success) {
            addMessageToChat(result.analysis, 'bot', result.source);
            showFileStatus('', 'success');
        } else {
            let errorMessage = result.error || 'فشل في تحليل الملف';
            
            // في حالة فشل تحليل الصورة، محاولة استخراج النص كبديل
            if (uploadedFileType === 'image' && errorMessage.includes('تحليل')) {
                addMessageToChat('حدث خطأ في تحليل الصورة. سأحاول استخراج النص منها...', 'bot', 'info');
                // هنا يمكن إضافة OCR لاحقاً
                addMessageToChat('عذراً، لا يمكنني تحليل الصورة حالياً. يرجى إعادة المحاولة لاحقاً.', 'bot', 'error');
            } else {
                addMessageToChat(errorMessage, 'bot', 'error');
            }
            showFileStatus(errorMessage, 'error');
        }

        // مسح الملف المرفوع بعد التحليل
        clearUploadedFile();

    } catch (error) {
        hideTypingIndicator();
        console.error('Error analyzing uploaded file:', error);
        addMessageToChat('حدث خطأ في تحليل الملف', 'bot', 'error');
        showFileStatus('خطأ في تحليل الملف', 'error');
        clearUploadedFile();
    }
}

/**
 * مسح الملف المرفوع
 */
function clearUploadedFile() {
    uploadedFileId = null;
    uploadedFileType = null;
    document.getElementById('fileUploadInput').value = '';
    const messageInput = document.getElementById('messageInput');
    messageInput.placeholder = 'اكتب سؤالك هنا أو ارفق ملفاً...';
    document.getElementById('fileStatus').style.display = 'none';
}

/**
 * إضافة رسالة للمحادثة
 */
function addMessageToChat(message, type, source) {
    try {
        const chatContainer = document.getElementById('chatContainer');
        if (!chatContainer) {
            console.error('Chat container not found');
            return;
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message mb-3`;

        const sourceLabel = getSourceLabel(source);
        const timestamp = new Date().toLocaleTimeString('ar-SA', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });

        messageDiv.innerHTML = `
            <div class="message-content p-3 rounded">
                <div class="message-text">${message}</div>
                <div class="message-meta mt-2">
                    <small class="text-muted">
                        ${timestamp}
                        ${sourceLabel ? ` | ${sourceLabel}` : ''}
                    </small>
                </div>
            </div>
        `;

        chatContainer.appendChild(messageDiv);

        // التمرير لأسفل
        chatContainer.scrollTop = chatContainer.scrollHeight;

    } catch (error) {
        console.error('Error adding message to chat:', error);
    }
}

function getSourceLabel(source) {
    const labels = {
        'book': '📚 من الكتاب',
        'gemini': '🤖 ذكي اصطناعي', 
        'error': '⚠️ خطأ',
        'default': '💬 افتراضي'
    };
    return labels[source] || '';
}

/**
 * إظهار/إخفاء مؤشر الكتابة
 */
function showTypingIndicator() {
    try {
        hideTypingIndicator(); // إزالة المؤشر السابق إن وُجد

        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            const typingDiv = document.createElement('div');
            typingDiv.id = 'typingIndicator';
            typingDiv.className = 'message bot-message mb-3';
            typingDiv.innerHTML = `
                <div class="message-content p-3 rounded">
                    <div class="typing-animation">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                    <small class="text-muted">البوت يكتب...</small>
                </div>
            `;

            chatContainer.appendChild(typingDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    } catch (error) {
        console.error('Error showing typing indicator:', error);
    }
}

function hideTypingIndicator() {
    try {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    } catch (error) {
        console.error('Error hiding typing indicator:', error);
    }
}

/**
 * وظائف إدارة البيانات للمطور
 */
function showAddForm(type) {
    try {
        document.getElementById('itemType').value = type;
        document.getElementById('itemName').value = '';
        document.getElementById('itemDescription').value = '';

        const modalTitle = document.querySelector('#addItemModal .modal-title');
        if (modalTitle) {
            modalTitle.textContent = `إضافة ${getTypeDisplayName(type)} جديد`;
        }

        $('#addItemModal').modal('show');
    } catch (error) {
        console.error('Error showing add form:', error);
        showAlert('حدث خطأ في عرض النموذج', 'error');
    }
}

async function deleteItem(type, id, name) {
    try {
        const confirmed = confirm(`هل أنت متأكد من حذف "${name}"؟`);
        if (!confirmed) return;

        const response = await apiRequest(`delete_${type}`, { id: id }, 'POST');

        if (response.success) {
            showAlert(response.message, 'success');
            loadInitialData(); // إعادة تحميل البيانات
        } else {
            showAlert(response.error || 'فشل في حذف العنصر', 'error');
        }
    } catch (error) {
        console.error('Error deleting item:', error);
        showAlert('حدث خطأ في حذف العنصر', 'error');
    }
}

/**
 * وظائف إدارة الجلسة
 */
function showAdminLogin() {
    try {
        $('#adminLoginModal').modal('show');
    } catch (error) {
        console.error('Error showing admin login:', error);
    }
}

async function adminLogin() {
    try {
        const password = document.getElementById('adminPassword');
        if (!password || !password.value) {
            showAlert('يرجى إدخال كلمة المرور', 'error');
            return;
        }

        const response = await apiRequest('admin_login', {
            password: password.value
        }, 'POST');

        if (response.success) {
            showAlert(response.message, 'success');
            $('#adminLoginModal').modal('hide');
            password.value = '';

            // إظهار لوحة الإدارة
            document.getElementById('adminPanel').style.display = 'block';
            document.getElementById('adminLoginBtn').style.display = 'none';
            document.getElementById('adminLogoutBtn').style.display = 'inline-block';

            // تحميل البيانات الإدارية
            loadAdminData();
        } else {
            showAlert(response.error || 'فشل في تسجيل الدخول', 'error');
        }
    } catch (error) {
        console.error('Error in admin login:', error);
        showAlert('حدث خطأ في تسجيل الدخول', 'error');
    }
}

async function adminLogout() {
    try {
        const response = await apiRequest('admin_logout', {}, 'POST');

        if (response.success) {
            showAlert(response.message, 'success');

            // إخفاء لوحة الإدارة
            document.getElementById('adminPanel').style.display = 'none';
            document.getElementById('adminLoginBtn').style.display = 'inline-block';
            document.getElementById('adminLogoutBtn').style.display = 'none';
        } else {
            showAlert(response.error || 'فشل في تسجيل الخروج', 'error');
        }
    } catch (error) {
        console.error('Error in admin logout:', error);
        showAlert('حدث خطأ في تسجيل الخروج', 'error');
    }
}

async function checkAdminSession() {
    try {
        const response = await apiRequest('validate_admin_session');

        if (response.is_admin) {
            document.getElementById('adminPanel').style.display = 'block';
            document.getElementById('adminLoginBtn').style.display = 'none';
            document.getElementById('adminLogoutBtn').style.display = 'inline-block';
            loadAdminData();
        } else {
            document.getElementById('adminPanel').style.display = 'none';
            document.getElementById('adminLoginBtn').style.display = 'inline-block';
            document.getElementById('adminLogoutBtn').style.display = 'none';
        }
    } catch (error) {
        console.error('Admin session check error:', error);
        // لا نظهر رسالة خطأ هنا لأنه فحص تلقائي
    }
}

/**
 * تحميل البيانات الإدارية
 */
async function loadAdminData() {
    try {
        // تحميل الإحصائيات
        const statsResponse = await apiRequest('get_dashboard_stats');
        if (statsResponse.success) {
            updateDashboardStats(statsResponse.stats);
        }

        // تحميل تاريخ المحادثات
        const historyResponse = await apiRequest('get_conversation_history');
        if (historyResponse.success) {
            updateConversationHistory(historyResponse.conversations);
        }

        // تحميل لوحة المطور
        await loadDeveloperPanel();
    } catch (error) {
        console.error('Error loading admin data:', error);
        showAlert('حدث خطأ في تحميل البيانات الإدارية', 'error');
    }
}

function updateDashboardStats(stats) {
    try {
        const statsContainer = document.getElementById('dashboardStats');
        if (statsContainer && stats) {
            statsContainer.innerHTML = `
                <div class="row">
                    <div class="col-md-3">
                        <div class="card bg-primary text-white">
                            <div class="card-body">
                                <h5>${stats.total_conversations || 0}</h5>
                                <p>إجمالي المحادثات</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-success text-white">
                            <div class="card-body">
                                <h5>${stats.unique_users || 0}</h5>
                                <p>المستخدمين الفريدين</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-info text-white">
                            <div class="card-body">
                                <h5>${stats.today_conversations || 0}</h5>
                                <p>محادثات اليوم</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-warning text-white">
                            <div class="card-body">
                                <h5>${Object.keys(stats.response_sources || {}).length}</h5>
                                <p>مصادر الإجابة</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error updating dashboard stats:', error);
    }
}

function updateConversationHistory(conversations) {
    try {
        const historyContainer = document.getElementById('conversationHistory');
        if (historyContainer && conversations) {
            historyContainer.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>المستخدم</th>
                                <th>السؤال</th>
                                <th>المصدر</th>
                                <th>الوقت</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${conversations.slice(0, 20).map(conv => `
                                <tr>
                                    <td>${conv.username}</td>
                                    <td title="${conv.user_message}">
                                        ${conv.user_message.length > 50 ? 
                                          conv.user_message.substring(0, 50) + '...' : 
                                          conv.user_message}
                                    </td>
                                    <td>
                                        <span class="badge ${getSourceBadgeClass(conv.response_source)}">
                                            ${getSourceLabel(conv.response_source)}
                                        </span>
                                    </td>
                                    <td>${new Date(conv.created_at).toLocaleDateString('ar-SA')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error updating conversation history:', error);
    }
}

function getSourceBadgeClass(source) {
    const classes = {
        'book': 'bg-success',
        'gemini': 'bg-info',
        'default': 'bg-secondary',
        'error': 'bg-danger'
    };
    return classes[source] || 'bg-secondary';
}

/**
 * طلب API محسن مع معالجة أفضل للأخطاء
 */
async function apiRequest(action, data = {}, method = 'GET') {
    try {
        console.log(`API Request: ${method} ${action}`, data);

        let url;
        if (method === 'GET') {
            const urlParams = new URLSearchParams();
            urlParams.append('action', action);
            
            // إضافة باقي البارامترات للطلبات GET
            Object.keys(data).forEach(key => {
                if (data[key] !== null && data[key] !== undefined) {
                    urlParams.append(key, data[key]);
                }
            });
            
            url = `${API_BASE_URL}?${urlParams.toString()}`;
        } else {
            url = API_BASE_URL;
        }

        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        };

        if (method === 'POST') {
            // استخدام JSON دائماً للبيانات POST
            options.body = JSON.stringify({
                action: action,
                ...data
            });
        }

        console.log('Making fetch request:', url, options);

        const response = await fetch(url, options);

        console.log('Response received:', response.status, response.statusText);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
        }

        const result = await response.json();
        console.log('API Response:', result);

        return result;

    } catch (error) {
        console.error(`API Request Failed for ${action}:`, error);

        // معالجة أخطاء الشبكة
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            return {
                success: false,
                error: 'خطأ في الاتصال بالخادم. يرجى التحقق من الاتصال والمحاولة مرة أخرى.'
            };
        }

        // معالجة الأخطاء الأخرى
        return {
            success: false,
            error: error.message || 'حدث خطأ غير متوقع'
        };
    }
}

/**
 * إظهار رسالة تنبيه
 */
function showAlert(message, type = 'info', duration = 5000) {
    try {
        // إنشاء عنصر التنبيه
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 10000; max-width: 400px;';

        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alertDiv);

        // إزالة التنبيه تلقائياً
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, duration);

    } catch (error) {
        console.error('Error showing alert:', error);
        // استخدام alert عادي كبديل
        alert(message);
    }
}

/**
 * مساعدات أخرى
 */
function resetChat() {
    try {
        currentUsername = '';
        selectedGradeId = null;
        selectedSemesterId = null;
        selectedDepartmentId = null;

        document.getElementById('setupSection').style.display = 'block';
        document.getElementById('chatSection').style.display = 'none';

        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.innerHTML = '';
        }

        // مسح النموذج
        const form = document.getElementById('setupForm');
        if (form) {
            form.reset();
        }

        console.log('Chat reset completed');
    } catch (error) {
        console.error('Error resetting chat:', error);
    }
}

// إضافة CSS للأنيميشن
const style = document.createElement('style');
style.textContent = `
    .typing-animation {
        display: flex;
        gap: 4px;
    }

    .typing-animation span {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #007bff;
        animation: typing 1.4s infinite ease-in-out;
    }

    .typing-animation span:nth-child(1) { animation-delay: 0s; }
    .typing-animation span:nth-child(2) { animation-delay: 0.2s; }
    .typing-animation span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes typing {
        0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
        40% { transform: scale(1); opacity: 1; }
    }

    .user-message .message-content {
        background-color: #007bff;
        color: white;
        margin-left: 20%;
    }

    .bot-message .message-content {
        background-color: #f8f9fa;
        color: #333;
        margin-right: 20%;
    }
`;
document.head.appendChild(style);

// ===============================================
// وظائف لوحة المطور - Developer Panel Functions
// ===============================================

// تحميل البيانات في لوحة المطور
async function loadDeveloperPanel() {
    try {
        // تحميل الفرق والترمات والأقسام
        const [gradesResponse, semestersResponse, departmentsResponse] = await Promise.all([
            apiRequest('get_grades'),
            apiRequest('get_semesters'),
            apiRequest('get_departments')
        ]);

        // ملء قائمة الفرق
        const gradeSelect = document.getElementById('devGradeSelect');
        if (gradeSelect && gradesResponse.success) {
            gradeSelect.innerHTML = '<option value="">اختر الفرقة</option>';
            gradesResponse.grades.forEach(grade => {
                gradeSelect.innerHTML += `<option value="${grade.id}">${grade.name}</option>`;
            });
        }

        // ملء قائمة الترمات
        const semesterSelect = document.getElementById('devSemesterSelect');
        if (semesterSelect && semestersResponse.success) {
            semesterSelect.innerHTML = '<option value="">اختر الترم</option>';
            semestersResponse.semesters.forEach(semester => {
                semesterSelect.innerHTML += `<option value="${semester.id}">${semester.name}</option>`;
            });
        }

        // ملء قائمة الأقسام (جميع الأقسام في لوحة المطور)
        const departmentsList = document.getElementById('devDepartmentsList');
        if (departmentsList && departmentsResponse.success) {
            departmentsList.innerHTML = '';
            departmentsResponse.departments.forEach(department => {
                const checkbox = document.createElement('div');
                checkbox.className = 'form-check';
                checkbox.innerHTML = `
                    <input class="form-check-input" type="checkbox" value="${department.id}" id="dept_${department.id}">
                    <label class="form-check-label" for="dept_${department.id}">
                        ${department.name}
                    </label>
                `;
                departmentsList.appendChild(checkbox);
            });
        }

        // تحميل الملفات المرفوعة
        await loadDeveloperFiles();

        // إعداد نموذج رفع الملفات
        setupDeveloperUploadForm();
        
        // تحميل إدارة الأقسام
        await loadDepartmentManagement();
        
        // تحميل ملفات الشاتات
        await loadChatFiles();

    } catch (error) {
        console.error('Error loading developer panel:', error);
        showAlert('حدث خطأ في تحميل لوحة المطور', 'error');
    }
}

// إعداد نموذج رفع الملفات
function setupDeveloperUploadForm() {
    const uploadForm = document.getElementById('developerUploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            await uploadDeveloperFile();
        });
    }
}

// رفع ملف من المطور
async function uploadDeveloperFile() {
    try {
        const gradeId = document.getElementById('devGradeSelect').value;
        const semesterId = document.getElementById('devSemesterSelect').value;
        const fileInput = document.getElementById('developerFileInput');
        
        // جمع الأقسام المحددة
        const selectedDepartments = [];
        document.querySelectorAll('#devDepartmentsList input[type="checkbox"]:checked').forEach(checkbox => {
            selectedDepartments.push(checkbox.value);
        });

        // التحقق من البيانات
        if (!gradeId || !semesterId || selectedDepartments.length === 0) {
            showAlert('يرجى اختيار الفرقة والترم والأقسام', 'error');
            return;
        }

        if (!fileInput.files[0]) {
            showAlert('يرجى اختيار ملف للرفع', 'error');
            return;
        }

        // إنشاء FormData
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('grade_id', gradeId);
        formData.append('semester_id', semesterId);
        selectedDepartments.forEach(deptId => {
            formData.append('department_ids[]', deptId);
        });

        // إظهار مؤشر التحميل
        const submitBtn = document.querySelector('#developerUploadForm button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الرفع...';
        submitBtn.disabled = true;

        // إرسال الطلب
        const response = await fetch('/api', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: new URLSearchParams({
                action: 'upload_developer_file'
            }).toString() + '&' + new URLSearchParams(formData).toString().replace(/^/, '')
        });

        // إرسال الملف بشكل منفصل
        const fileFormData = new FormData();
        fileFormData.append('file', fileInput.files[0]);
        fileFormData.append('grade_id', gradeId);
        fileFormData.append('semester_id', semesterId);
        selectedDepartments.forEach(deptId => {
            fileFormData.append('department_ids[]', deptId);
        });

        const fileResponse = await fetch('/api?action=upload_developer_file', {
            method: 'POST',
            body: fileFormData
        });

        const result = await fileResponse.json();

        // استعادة الزر
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;

        if (result.success) {
            showAlert('تم رفع الملف بنجاح', 'success');
            document.getElementById('developerUploadForm').reset();
            // إعادة تحميل قائمة الملفات
            await loadDeveloperFiles();
        } else {
            showAlert(result.error || 'فشل في رفع الملف', 'error');
        }

    } catch (error) {
        console.error('Error uploading developer file:', error);
        showAlert('حدث خطأ في رفع الملف', 'error');
        
        // استعادة الزر في حالة الخطأ
        const submitBtn = document.querySelector('#developerUploadForm button[type="submit"]');
        submitBtn.innerHTML = '<i class="fas fa-upload"></i> رفع البيانات';
        submitBtn.disabled = false;
    }
}

// تحميل قائمة الملفات المرفوعة
async function loadDeveloperFiles() {
    try {
        const response = await apiRequest('get_developer_files');
        
        const filesList = document.getElementById('developerFilesList');
        if (filesList && response.success) {
            if (response.files.length === 0) {
                filesList.innerHTML = '<p class="text-muted">لا توجد ملفات مرفوعة</p>';
                return;
            }

            filesList.innerHTML = '';
            response.files.forEach(file => {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'border rounded p-3 mb-2';
                fileDiv.innerHTML = `
                    <div class="row align-items-center">
                        <div class="col-md-6">
                            <h6 class="mb-1">${file.filename}</h6>
                            <small class="text-muted">
                                ${file.grade_name} - ${file.semester_name}<br>
                                الأقسام: ${file.departments || 'غير محدد'}<br>
                                الحجم: ${formatFileSize(file.file_size)}
                            </small>
                        </div>
                        <div class="col-md-3">
                            <small class="text-muted">
                                تاريخ الرفع:<br>
                                ${new Date(file.upload_date).toLocaleDateString('ar-SA')}
                            </small>
                        </div>
                        <div class="col-md-3 text-end">
                            <button class="btn btn-danger btn-sm" onclick="deleteDeveloperFile(${file.id}, '${file.filename}')">
                                <i class="fas fa-trash"></i> حذف
                            </button>
                        </div>
                    </div>
                `;
                filesList.appendChild(fileDiv);
            });
        }
    } catch (error) {
        console.error('Error loading developer files:', error);
        showAlert('حدث خطأ في تحميل الملفات', 'error');
    }
}

// حذف ملف مرفوع
async function deleteDeveloperFile(fileId, filename) {
    try {
        const confirmed = confirm(`هل أنت متأكد من حذف الملف "${filename}"؟`);
        if (!confirmed) return;

        const response = await apiRequest('delete_developer_file', { 
            file_id: fileId 
        }, 'POST');

        if (response.success) {
            showAlert('تم حذف الملف بنجاح', 'success');
            await loadDeveloperFiles(); // إعادة تحميل القائمة
        } else {
            showAlert(response.error || 'فشل في حذف الملف', 'error');
        }
    } catch (error) {
        console.error('Error deleting developer file:', error);
        showAlert('حدث خطأ في حذف الملف', 'error');
    }
}

// تنسيق حجم الملف
function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// إدارة الأقسام
async function loadDepartmentManagement() {
    try {
        // تحميل البيانات الأولية (جميع الأقسام في إدارة الأقسام)
        const [gradesResponse, departmentsResponse] = await Promise.all([
            apiRequest('get_grades'),
            apiRequest('get_departments')
        ]);

        // ملء قائمة الفرق كـ checkboxes في النموذج الجديد
        const gradesCheckboxes = document.getElementById('gradesCheckboxes');
        if (gradesCheckboxes && gradesResponse.success) {
            gradesCheckboxes.innerHTML = '';
            gradesResponse.grades.forEach(grade => {
                const colDiv = document.createElement('div');
                colDiv.className = 'col-md-6 mb-2';
                colDiv.innerHTML = `
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" value="${grade.id}" id="grade_${grade.id}">
                        <label class="form-check-label" for="grade_${grade.id}">
                            ${grade.name}
                        </label>
                    </div>
                `;
                gradesCheckboxes.appendChild(colDiv);
            });
        }

        // تحميل قائمة ربط الأقسام الحالية
        await loadDepartmentGrades();

        // إعداد النموذج الجديد
        setupNewDepartmentForm();

    } catch (error) {
        console.error('Error loading department management:', error);
        showAlert('حدث خطأ في تحميل إدارة الأقسام', 'error');
    }
}

async function loadDepartmentGrades() {
    try {
        const response = await apiRequest('get_department_grades');
        
        if (response.success) {
            const container = document.getElementById('departmentGradesList');
            if (container) {
                container.innerHTML = '<h8>ربط الأقسام الحالية:</h8>';
                
                if (response.department_grades.length === 0) {
                    container.innerHTML += '<p class="text-muted mt-2">لا توجد روابط أقسام حالياً</p>';
                } else {
                    const linksHtml = response.department_grades.map(link => `
                        <div class="d-flex justify-content-between align-items-center border rounded p-2 mb-2">
                            <span>
                                <strong>${link.department.name}</strong> 
                                - ${link.grade.name}
                            </span>
                            <button class="btn btn-sm btn-danger" onclick="removeDepartmentLink(${link.department.id}, ${link.grade.id})">
                                <i class="fas fa-unlink"></i> إزالة
                            </button>
                        </div>
                    `).join('');
                    
                    container.innerHTML += `<div class="mt-2">${linksHtml}</div>`;
                }
            }
        }
    } catch (error) {
        console.error('Error loading department grades:', error);
    }
}

function setupNewDepartmentForm() {
    // النموذج الجديد لإضافة قسم مع عدة فرق
    const newDepartmentForm = document.getElementById('newDepartmentForm');
    if (newDepartmentForm) {
        newDepartmentForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const name = document.getElementById('departmentName').value.trim();
            if (!name) {
                showAlert('يرجى إدخال اسم القسم', 'error');
                return;
            }
            
            // جمع الفرق المختارة
            const selectedGrades = [];
            const gradeCheckboxes = document.querySelectorAll('#gradesCheckboxes input[type="checkbox"]:checked');
            gradeCheckboxes.forEach(checkbox => {
                selectedGrades.push(parseInt(checkbox.value));
            });
            
            if (selectedGrades.length === 0) {
                showAlert('يرجى اختيار فرقة واحدة على الأقل', 'error');
                return;
            }
            
            try {
                const response = await apiRequest('add_department_with_grades', {
                    name: name,
                    description: '',
                    grade_ids: selectedGrades
                }, 'POST');
                
                if (response.success) {
                    showAlert(response.message || 'تم إضافة القسم وربطه بالفرق بنجاح', 'success');
                    
                    // إعادة تعيين النموذج
                    document.getElementById('departmentName').value = '';
                    gradeCheckboxes.forEach(checkbox => {
                        checkbox.checked = false;
                    });
                    
                    // إعادة تحميل البيانات
                    await loadDepartmentGrades();
                } else {
                    showAlert(response.error || 'فشل في إضافة القسم', 'error');
                }
            } catch (error) {
                console.error('Error adding department with grades:', error);
                showAlert('حدث خطأ في إضافة القسم', 'error');
            }
        });
    }
}

async function removeDepartmentLink(departmentId, gradeId) {
    if (!confirm('هل أنت متأكد من إزالة هذا الربط؟')) {
        return;
    }

    try {
        const response = await apiRequest('remove_department_from_grade', {
            department_id: departmentId,
            grade_id: gradeId
        }, 'POST');
        
        if (response.success) {
            showAlert(response.message || 'تم إزالة الربط بنجاح', 'success');
            await loadDepartmentGrades(); // إعادة تحميل قائمة الروابط
        } else {
            showAlert(response.error || 'فشل في إزالة الربط', 'error');
        }
    } catch (error) {
        console.error('Error removing department link:', error);
        showAlert('حدث خطأ في إزالة الربط', 'error');
    }
}

// إدارة ملفات الشاتات
async function loadChatFiles() {
    try {
        const response = await apiRequest('get_chat_files');
        
        if (response.success) {
            const container = document.getElementById('chatFilesList');
            if (container) {
                if (response.chat_files.length === 0) {
                    container.innerHTML = '<p class="text-muted">لا توجد ملفات شاتات حالياً</p>';
                } else {
                    const filesHtml = response.chat_files.map(file => `
                        <div class="d-flex justify-content-between align-items-center border rounded p-3 mb-2">
                            <div>
                                <h6 class="mb-1">
                                    <i class="fas fa-user"></i> ${file.username}
                                </h6>
                                <small class="text-muted">
                                    <i class="fas fa-calendar"></i> آخر تحديث: ${file.modified}
                                    | <i class="fas fa-file"></i> الحجم: ${(file.size / 1024).toFixed(2)} KB
                                </small>
                            </div>
                            <div>
                                <button onclick="viewChatFile('${file.filename}')" 
                                        class="btn btn-sm btn-primary me-1">
                                    <i class="fas fa-eye"></i> عرض
                                </button>
                                <a href="/download_chat?filename=${file.filename}" 
                                   class="btn btn-sm btn-outline-primary" 
                                   target="_blank">
                                    <i class="fas fa-download"></i> تحميل
                                </a>
                            </div>
                        </div>
                    `).join('');
                    
                    container.innerHTML = filesHtml;
                }
            }
        }
    } catch (error) {
        console.error('Error loading chat files:', error);
        showAlert('حدث خطأ في تحميل ملفات الشاتات', 'error');
    }
}

async function viewChatFile(filename) {
    try {
        console.log('Viewing chat file:', filename);
        const response = await apiRequest('view_chat_file', {
            filename: filename
        }, 'POST');

        if (response.success) {
            // إنشاء modal لعرض المحتوى
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.id = 'chatFileModal';
            modal.innerHTML = `
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-comments"></i> عرض محادثات: ${response.filename}
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body" dir="rtl">
                            <pre class="chat-content" style="white-space: pre-wrap; font-family: 'Noto Sans Arabic', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 14px; line-height: 1.6; direction: rtl; text-align: right;">${response.content}</pre>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إغلاق</button>
                            <a href="/download_chat?filename=${filename}" class="btn btn-primary" target="_blank">
                                <i class="fas fa-download"></i> تحميل الملف
                            </a>
                        </div>
                    </div>
                </div>
            `;
            
            // إضافة وعرض المودال
            document.body.appendChild(modal);
            const bootstrapModal = new bootstrap.Modal(modal);
            bootstrapModal.show();
            
            // إزالة المودال عند الإغلاق
            modal.addEventListener('hidden.bs.modal', function () {
                document.body.removeChild(modal);
            });
            
        } else {
            showAlert(response.error || 'حدث خطأ في عرض الملف', 'error');
        }
    } catch (error) {
        console.error('Error viewing chat file:', error);
        showAlert('حدث خطأ في عرض الملف', 'error');
    }
}

// ===========================================
// وظائف الوسائط الجديدة - Gemini
// ===========================================

/**
 * إعداد أحداث رفع الملفات وإنتاج الصور للواجهة المدمجة
 */
function setupIntegratedMediaEventListeners() {
    try {
        // زر إرفاق الملفات الجديد
        const attachFileBtn = document.getElementById('attachFileBtn');
        const fileUploadInput = document.getElementById('fileUploadInput');
        
        if (attachFileBtn && fileUploadInput) {
            attachFileBtn.addEventListener('click', () => {
                fileUploadInput.click();
            });
            
            fileUploadInput.addEventListener('change', handleFileUpload);
        }

        // زر مسح المحادثة
        const clearChatBtn = document.getElementById('clearChatBtn');
        if (clearChatBtn) {
            clearChatBtn.addEventListener('click', clearChat);
        }

        console.log('Integrated media event listeners setup completed');
    } catch (error) {
        console.error('Error setting up integrated media event listeners:', error);
    }
}

/**
 * إظهار/إخفاء منطقة إنتاج الصور
 */
function toggleImagePromptSection() {
    const section = document.getElementById('imagePromptSection');
    const mediaSection = document.getElementById('mediaAnalysisSection');
    
    if (section.style.display === 'none') {
        section.style.display = 'block';
        mediaSection.style.display = 'none'; // إخفاء الآخر
        document.getElementById('imagePromptInput').focus();
    } else {
        section.style.display = 'none';
    }
}

// متغير لحفظ معرف الملف المرفوع
let uploadedFileId = null;
let uploadedFileType = null;

/**
 * معالج رفع الملفات الجديد - مبسط ومدمج
 */
async function handleFileUpload() {
    try {
        const fileInput = document.getElementById('fileUploadInput');
        const file = fileInput.files[0];
        
        if (!file) {
            return;
        }

        // التحقق من نوع الملف
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 
                             'video/mp4', 'video/avi', 'video/mov', 'application/pdf', 
                             'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                             'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/mp4', 'audio/ogg', 'audio/flac', 'audio/webm'];
        if (!allowedTypes.includes(file.type)) {
            showFileStatus('نوع الملف غير مدعوم. يرجى رفع صور، فيديوهات، ملفات صوتية، أو ملفات PDF/Word', 'error');
            fileInput.value = '';
            return;
        }

        // التحقق من حجم الملف (300MB حد أقصى)
        if (file.size > 300 * 1024 * 1024) {
            showFileStatus('حجم الملف كبير جداً. الحد الأقصى 300 ميجابايت', 'error');
            fileInput.value = '';
            return;
        }

        showFileStatus(`جارٍ رفع الملف: ${file.name}...`, 'info');

        // رفع الملف
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/upload-media', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        });

        const result = await response.json();

        if (result.success) {
            uploadedFileId = result.file_id;
            uploadedFileType = result.file_type;
            showFileStatus(`تم رفع الملف بنجاح: ${file.name}. اكتب سؤالك وأرسله للتحليل.`, 'success');
            
            // تحديث placeholder للإشارة أن هناك ملف مرفوع
            const messageInput = document.getElementById('messageInput');
            messageInput.placeholder = `ملف مرفوع: ${file.name} - اكتب سؤالك للتحليل...`;
            messageInput.focus();
            
        } else {
            showFileStatus(result.error || 'فشل في رفع الملف', 'error');
            fileInput.value = '';
        }

    } catch (error) {
        console.error('Error uploading file:', error);
        showFileStatus('حدث خطأ في رفع الملف', 'error');
        fileInput.value = '';
    }
}

/**
 * عرض حالة الملف
 */
function showFileStatus(message, type) {
    const statusElement = document.getElementById('fileStatus');
    if (!statusElement) return;
    
    statusElement.style.display = 'block';
    statusElement.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} small mb-2`;
    statusElement.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'exclamation-triangle' : 'info-circle'}"></i> ${message}`;
    
    // إخفاء الرسالة تلقائياً بعد 5 ثواني للرسائل الناجحة
    if (type === 'success') {
        setTimeout(() => {
            statusElement.style.display = 'none';
        }, 5000);
    }
}

/**
 * تحليل الملف المرفوع (الواجهة المدمجة)
 */
async function analyzeMediaIntegrated() {
    try {
        const fileId = document.getElementById('mediaUploadInput').dataset.fileId;
        const question = document.getElementById('mediaQuestionInput').value.trim();
        
        if (!fileId) {
            showAlert('يرجى رفع ملف أولاً', 'error');
            return;
        }

        if (!question) {
            showAlert('يرجى كتابة سؤال حول الملف', 'error');
            return;
        }

        showStatusIntegrated('uploadStatus', 'جارٍ تحليل الملف... (قد يستغرق عدة محاولات بسبب زحام الخادم)', 'info');

        const response = await fetch('/api/analyze-media', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_id: fileId,
                question: question
            }),
            credentials: 'same-origin'
        });

        const result = await response.json();

        if (result.success) {
            // إضافة السؤال والإجابة للمحادثة
            addMessageToChat(question, 'user');
            addMessageToChat(result.analysis, 'bot', result.source);
            
            // مسح النموذج وإخفاء قسم التحليل
            document.getElementById('mediaQuestionInput').value = '';
            document.getElementById('mediaAnalysisSection').style.display = 'none';
            document.getElementById('uploadStatus').style.display = 'none';
            document.getElementById('mediaUploadInput').value = '';
            delete document.getElementById('mediaUploadInput').dataset.fileId;
            
        } else {
            showStatusIntegrated('uploadStatus', result.error || 'فشل في تحليل الملف', 'error');
        }

    } catch (error) {
        console.error('Error analyzing media:', error);
        showStatusIntegrated('uploadStatus', 'حدث خطأ في تحليل الملف', 'error');
    }
}

/**
 * إنتاج صورة بناءً على الوصف (الواجهة المدمجة)
 */
async function generateImageIntegrated() {
    try {
        const prompt = document.getElementById('imagePromptInput').value.trim();
        
        if (!prompt) {
            showAlert('يرجى كتابة وصف للصورة المطلوبة', 'error');
            return;
        }

        showStatusIntegrated('imageGenerationStatus', 'جارٍ إنتاج الصورة... (قد يستغرق عدة محاولات بسبب زحام الخادم)', 'info');

        const response = await fetch('/api/generate-image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: prompt
            }),
            credentials: 'same-origin'
        });

        const result = await response.json();

        if (result.success) {
            showStatusIntegrated('imageGenerationStatus', result.message, 'success');
            
            // إضافة رسالة للمحادثة
            addMessageToChat(`طلب إنتاج صورة: ${prompt}`, 'user');
            addMessageToChat(`تم إنتاج الصورة بنجاح! <br><img src="${result.image_url}" class="img-fluid rounded mt-2" style="max-width: 300px;">`, 'bot', result.source);
            
            // مسح النموذج وإخفاء القسم
            document.getElementById('imagePromptInput').value = '';
            document.getElementById('imagePromptSection').style.display = 'none';
            document.getElementById('imageGenerationStatus').style.display = 'none';
            
        } else {
            showStatusIntegrated('imageGenerationStatus', result.error || 'فشل في إنتاج الصورة', 'error');
        }

    } catch (error) {
        console.error('Error generating image:', error);
        showStatusIntegrated('imageGenerationStatus', 'حدث خطأ في إنتاج الصورة', 'error');
    }
}

/**
 * مسح المحادثة
 */
function clearChat() {
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.innerHTML = '';
        showAlert('تم مسح المحادثة', 'success');
    }
}

/**
 * عرض حالة العملية (الواجهة المدمجة)
 */
function showStatusIntegrated(elementId, message, type) {
    const statusElement = document.getElementById(elementId);
    if (!statusElement) return;
    
    statusElement.style.display = 'block';
    statusElement.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} small`;
    statusElement.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'exclamation-triangle' : 'info-circle'}"></i> ${message}`;
}

/**
 * إعداد أحداث رفع الملفات وإنتاج الصور (النسخة القديمة - للتوافق)
 */
function setupMediaEventListeners() {
    try {
        // زر اختيار ملف الوسائط
        const uploadMediaBtn = document.getElementById('uploadMediaBtn');
        const mediaUploadInput = document.getElementById('mediaUploadInput');
        
        if (uploadMediaBtn && mediaUploadInput) {
            uploadMediaBtn.addEventListener('click', () => {
                mediaUploadInput.click();
            });
            
            mediaUploadInput.addEventListener('change', uploadMedia);
        }

        // زر تحليل الملف
        const analyzeMediaBtn = document.getElementById('analyzeMediaBtn');
        if (analyzeMediaBtn) {
            analyzeMediaBtn.addEventListener('click', analyzeMedia);
        }

        // زر إنتاج الصورة
        const generateImageBtn = document.getElementById('generateImageBtn');
        if (generateImageBtn) {
            generateImageBtn.addEventListener('click', generateImage);
        }

        console.log('Media event listeners setup completed');
    } catch (error) {
        console.error('Error setting up media event listeners:', error);
    }
}

/**
 * رفع ملف الوسائط
 */
async function uploadMedia() {
    try {
        const fileInput = document.getElementById('mediaUploadInput');
        const file = fileInput.files[0];
        
        if (!file) {
            showAlert('يرجى اختيار ملف', 'error');
            return;
        }

        // التحقق من نوع الملف
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'video/mp4', 'video/avi', 'video/mov'];
        if (!allowedTypes.includes(file.type)) {
            showAlert('نوع الملف غير مدعوم. يرجى رفع صور (jpg, png, gif) أو فيديوهات (mp4, avi, mov)', 'error');
            return;
        }

        // التحقق من حجم الملف (50MB حد أقصى)
        if (file.size > 50 * 1024 * 1024) {
            showAlert('حجم الملف كبير جداً. الحد الأقصى 50 ميجابايت', 'error');
            return;
        }

        showStatus('uploadStatus', 'جارٍ رفع الملف...', 'info');

        // رفع الملف
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/upload-media', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        });

        const result = await response.json();

        if (result.success) {
            showStatus('uploadStatus', result.message, 'success');
            
            // حفظ معرف الملف وإظهار قسم التحليل
            document.getElementById('mediaUploadInput').dataset.fileId = result.file_id;
            document.getElementById('mediaAnalysisSection').style.display = 'block';
            
            // التركيز على حقل السؤال
            document.getElementById('mediaQuestionInput').focus();
            
        } else {
            showStatus('uploadStatus', result.error || 'فشل في رفع الملف', 'error');
        }

    } catch (error) {
        console.error('Error uploading media:', error);
        showStatus('uploadStatus', 'حدث خطأ في رفع الملف', 'error');
    }
}

/**
 * تحليل الملف المرفوع
 */
async function analyzeMedia() {
    try {
        const fileId = document.getElementById('mediaUploadInput').dataset.fileId;
        const question = document.getElementById('mediaQuestionInput').value.trim();
        
        if (!fileId) {
            showAlert('يرجى رفع ملف أولاً', 'error');
            return;
        }

        if (!question) {
            showAlert('يرجى كتابة سؤال حول الملف', 'error');
            return;
        }

        showStatus('uploadStatus', 'جارٍ تحليل الملف...', 'info');

        const response = await fetch('/api/analyze-media', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_id: fileId,
                question: question
            }),
            credentials: 'same-origin'
        });

        const result = await response.json();

        if (result.success) {
            // إضافة السؤال والإجابة للمحادثة
            addMessageToChat(question, 'user');
            addMessageToChat(result.analysis, 'bot', result.source);
            
            // مسح النموذج وإخفاء قسم التحليل
            document.getElementById('mediaQuestionInput').value = '';
            document.getElementById('mediaAnalysisSection').style.display = 'none';
            document.getElementById('uploadStatus').style.display = 'none';
            document.getElementById('mediaUploadInput').value = '';
            delete document.getElementById('mediaUploadInput').dataset.fileId;
            
        } else {
            showStatus('uploadStatus', result.error || 'فشل في تحليل الملف', 'error');
        }

    } catch (error) {
        console.error('Error analyzing media:', error);
        showStatus('uploadStatus', 'حدث خطأ في تحليل الملف', 'error');
    }
}

/**
 * إنتاج صورة بناءً على الوصف
 */
async function generateImage() {
    try {
        const prompt = document.getElementById('imagePromptInput').value.trim();
        
        if (!prompt) {
            showAlert('يرجى كتابة وصف للصورة المطلوبة', 'error');
            return;
        }

        showStatus('imageGenerationStatus', 'جارٍ إنتاج الصورة... قد يستغرق هذا بعض الوقت', 'info');

        const response = await fetch('/api/generate-image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: prompt
            }),
            credentials: 'same-origin'
        });

        const result = await response.json();

        if (result.success) {
            showStatus('imageGenerationStatus', result.message, 'success');
            
            // عرض الصورة المولدة
            const imageContainer = document.getElementById('generatedImageContainer');
            imageContainer.innerHTML = `
                <div class="text-center">
                    <img src="${result.image_url}" class="img-fluid rounded" alt="الصورة المولدة" style="max-width: 100%; height: auto;">
                    <p class="small text-muted mt-2">تم إنتاج الصورة بواسطة Gemini AI</p>
                </div>
            `;
            imageContainer.style.display = 'block';
            
            // إضافة رسالة للمحادثة
            addMessageToChat(`طلب إنتاج صورة: ${prompt}`, 'user');
            addMessageToChat(`تم إنتاج الصورة بنجاح! <br><img src="${result.image_url}" class="img-fluid rounded mt-2" style="max-width: 300px;">`, 'bot', result.source);
            
            // مسح النموذج
            document.getElementById('imagePromptInput').value = '';
            
        } else {
            showStatus('imageGenerationStatus', result.error || 'فشل في إنتاج الصورة', 'error');
        }

    } catch (error) {
        console.error('Error generating image:', error);
        showStatus('imageGenerationStatus', 'حدث خطأ في إنتاج الصورة', 'error');
    }
}

/**
 * عرض حالة العملية
 */
function showStatus(elementId, message, type) {
    const statusElement = document.getElementById(elementId);
    if (!statusElement) return;
    
    statusElement.style.display = 'block';
    statusElement.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} small`;
    statusElement.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'exclamation-triangle' : 'info-circle'}"></i> ${message}`;
}

console.log('Educational Bot JavaScript loaded successfully');
