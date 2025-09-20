# Overview

This is an enhanced educational bot system built with Flask that provides intelligent answers to students with advanced administrative features. The system includes user interaction tracking, content management capabilities, file upload functionality for educational materials, and integration with Google's Gemini AI for intelligent responses. The bot first searches its knowledge base of questions and answers, then falls back to Gemini AI if no answer is found.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes

**September 20, 2025**:
- ✅ **COMPLETED Replit Environment Setup** - Successfully migrated GitHub import to Replit platform
- ✅ **FIXED Image Upload Integration** - Images now properly integrate with chat questions and get processed by Gemini AI
- ✅ **ADDED Audio File Support** - Users can now upload audio files (MP3, WAV, M4A, OGG, FLAC, WebM) for speech-to-text conversion
- ✅ **ENHANCED OCR Processing** - Improved image text extraction with optimized Tesseract configuration for Arabic and English
- ✅ **RESOLVED Worker Timeout Issues** - Optimized Gemini API retry logic and processing timeouts
- ✅ **UNIFIED File Upload System** - Standardized upload directories and file processing across all media types
- ✅ **CONFIGURED CORS for Replit** - Proper CORS setup for development and production environments
- ✅ **ADDED FFMPEG Support** - Installed system dependency for audio file processing
- ✅ **OPTIMIZED Deployment Config** - Set up autoscaling deployment configuration for production

**September 16, 2025**:
- ✅ Fixed database index naming issue preventing server startup
- ✅ Completed developer panel integration with enhanced file upload functionality  
- ✅ Implemented secure file categorization by grade, semester, and department
- ✅ Added comprehensive admin session validation for all developer functions
- ✅ **Fixed department "بيولوجي" duplicate error** - Enhanced error handling with more descriptive messages
- ✅ **Improved AI responses** - Now strictly limited to curriculum content, refuses non-curriculum questions
- ✅ **Fixed Arabic encoding issues** - Chat log files now properly save Arabic text with UTF-8 encoding
- ✅ **Implemented department filtering by grade** - Departments now display only when linked to selected grade
- ✅ **Enhanced user interface** - Departments auto-update when grade selection changes
- ✅ **REMOVED unwanted departments** - Permanently deleted العلمي، التجاري، الأدبي departments from system
- ✅ **FIXED Gemini reading limitation** - Removed 20,000 character limit, now reads complete files (250+ pages)
- ✅ **ELIMINATED confirmation messages** - Gemini AI now responds directly without asking user permission
- ✅ **VERIFIED Arabic text encoding** - Chat logs save and display Arabic text correctly with UTF-8
- ✅ **FIXED API timeout errors** - Resolved Worker timeout issue by optimizing Gemini content processing (100k character limit)
- ✅ **ENHANCED error handling** - Added comprehensive error handling for Gemini API calls with Arabic error messages
- ✅ **FIXED department persistence issue** - Departments no longer reset to default state on restart, custom configurations persist permanently
- ✅ **IMPROVED Arabic text display in modals** - Chat log modals now display Arabic text correctly with proper RTL direction and Arabic fonts
- ✅ Achieved full system functionality with all requested fixes completed and verified

# System Architecture

## Frontend Architecture
- **Framework**: HTML5 with Bootstrap 5 for responsive design
- **JavaScript**: Vanilla JavaScript for client-side interactions
- **UI Components**: Font Awesome icons, custom CSS styling
- **Language Support**: Right-to-left (RTL) Arabic language support
- **Communication**: RESTful API calls to Flask backend

## Backend Architecture
- **Framework**: Flask web framework with Python 3.8+
- **Architecture Pattern**: MVC (Model-View-Controller) pattern
- **API Design**: RESTful API with unified handler supporting both `/api/<action>` and `/api?action=<action>` formats
- **Session Management**: Flask sessions with secure secret key management
- **File Processing**: Support for PDF and Word document text extraction using PyPDF2, python-docx, and pdfplumber
- **Error Handling**: Comprehensive error handling with detailed logging

## Data Storage
- **Primary Database**: SQLite3 for persistent data storage
- **Schema Design**: Hierarchical structure linking grades → departments → uploaded files
- **Chat Logging**: Complete conversation history with timestamps and user identification
- **File Storage**: Local filesystem storage for uploaded educational materials
- **Session Storage**: Server-side session management for user state

## Authentication & Authorization
- **Admin Authentication**: Password-based authentication with Werkzeug security utilities
- **Session Security**: Secure session management with session timeouts
- **Password Hashing**: Secure password storage using generate_password_hash
- **Access Control**: Role-based access for administrative functions

## External Dependencies

- **Google Generative AI**: Gemini API integration for intelligent question answering when local knowledge base doesn't contain answers
- **Bootstrap 5**: Frontend UI framework loaded from CDN
- **Font Awesome**: Icon library for enhanced UI elements
- **Flask-CORS**: Cross-Origin Resource Sharing support for Replit deployment
- **Document Processing Libraries**: 
  - PyPDF2 for PDF text extraction
  - python-docx for Word document processing
  - pdfplumber for advanced PDF parsing
  - python-magic for file type detection
- **Environment Variables**: 
  - SECRET_KEY for session security
  - ADMIN_PASSWORD for admin access
  - GEMINI_API_KEY for AI integration (optional)