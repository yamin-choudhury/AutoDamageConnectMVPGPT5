# AutoDamageConnect - Complete Project Context Guide

## 🎯 PROJECT OVERVIEW
AutoDamageConnect is an AI-powered vehicle damage assessment platform that generates professional insurance-grade damage reports from photos. Users upload vehicle damage images, and the system uses multi-stage AI processing to identify damaged parts, estimate repairs, and generate comprehensive PDF reports.

## 🏗️ ARCHITECTURE OVERVIEW

### Core Workflow:
1. **Frontend (React/Vite)** → User uploads images → Stores in Supabase
2. **Supabase Edge Function** → Triggers damage report generation
3. **Railway Backend (Python/FastAPI)** → AI processing pipeline  
4. **AI Pipeline** → Multi-phase damage detection & vehicle identification
5. **Report Generation** → JSON + HTML → PDF conversion
6. **Storage** → Reports stored in Supabase Storage
7. **Frontend Display** → ReportViewer shows results with images

## 🛠️ TECH STACK

### Frontend:
- **React 18** with TypeScript
- **Vite** (dev server on port 8080)
- **Supabase Client** for database/storage
- **TailwindCSS** for styling

### Backend:
- **FastAPI** (Python) hosted on **Railway**
- **OpenAI GPT-4o** for vision analysis
- **Supabase** for database & storage
- **Playwright** for HTML→PDF conversion
- **Parallel processing** with ThreadPoolExecutor

### Database (Supabase PostgreSQL):
- `documents` - Document metadata & status
- `document_images` - Image URLs linked to documents  
- `images` - Legacy table (being phased out)

## 📊 DATABASE SCHEMA

### `documents` table:
```sql
- id (uuid, primary key)
- title (text)
- vin (text)  
- make (text)
- model (text)
- status (text) - 'uploaded', 'processing', 'completed', 'failed'
- report_pdf_url (text) - URL to generated PDF report
- created_at (timestamp)
```

### `document_images` table:
```sql
- id (uuid, primary key)
- document_id (uuid, foreign key to documents.id)
- image_url (text) - Supabase storage URL
- created_at (timestamp)
```

## 🤖 AI PROCESSING PIPELINE (Backend)

### Phase -1: Parallel Vehicle Identification (NEW OPTIMIZATION)
- **3 simultaneous attempts** with different image combinations:
  - Front-focus batch (images 0-1)
  - Mixed-angles batch (images 1-3)  
  - Single-best batch (image 0 only)
- **Voting consensus** determines final make/model/year
- **Result**: More accurate vehicle identification

### Phase 0: Parallel Quick Area Detection  
- **Parallel processing** of up to 8 images simultaneously
- Uses `detect_quick_prompt.txt` to identify damaged areas
- **4 concurrent workers** for speed
- Output: List of general damaged areas (e.g., "front end", "side")

### Phase 1: Parallel Area-Specialist Detection (MAJOR OPTIMIZATION)
- **Most complex phase** - biggest speed improvement here
- Maps damaged areas to specialized prompts:
  - `detect_front_A.txt` + `detect_front_B.txt` for front damage
  - `detect_side_A.txt` + `detect_side_B.txt` for side damage  
  - `detect_rear_A.txt` + `detect_rear_B.txt` for rear damage
- **Multi-temperature ensemble**: Each prompt runs at temps 0.1, 0.4, 0.8
- **Up to 8 concurrent workers** process all combinations simultaneously
- **OLD**: 18+ sequential API calls (3-5 minutes)
- **NEW**: 18+ parallel API calls (30-60 seconds) - **5x faster!**

### Phase 2: Part Enrichment
- Uses `describe_parts_prompt.txt` to add repair details
- Adds repair_method, descriptions, technical notes

### Phase 3: Repair Planning  
- Uses `plan_parts_prompt.txt` to generate parts list
- Calculates labor hours, paint hours, costs

### Phase 4: Summary Generation
- Uses `summary_prompt.txt` for final assessment
- Overall severity, complexity, safety impact

### Deduplication & Merging:
- `union_parts()` function merges all results from parallel processing
- Removes duplicate parts using sophisticated matching logic
- **CRITICAL**: Same deduplication logic preserved - parallel processing doesn't affect accuracy

## 🎨 FRONTEND COMPONENTS

### Key Components:
- `ReportViewer.tsx` - **MOST COMPLEX** - Displays generated reports with damage images
- `HistorySidebar.tsx` - Lists all documents with status
- `FileUploader.tsx` - Handles image uploads to Supabase

### Recent ReportViewer Fixes:
- **Fixed infinite loops** caused by unstable useEffect dependencies
- **Added useMemo** to stabilize damage image filename arrays
- **Fixed database queries** to use correct schema (report_pdf_url vs report_json)
- **Enhanced JSON fetching** with proper error handling and content-type validation
- **Smart image matching** between damaged parts and stored images

## 🔧 KEY FILES & PURPOSES

### Backend Files:
- `main.py` - FastAPI server, main endpoints, Supabase integration
- `generate_damage_report_staged.py` - **CORE AI PIPELINE** with parallel processing
- `html_to_pdf.py` - PDF generation using Playwright
- `prompts/*.txt` - AI prompts for each detection phase

### Frontend Files:
- `src/components/ReportViewer.tsx` - Report display with image handling
- `src/lib/supabase.ts` - Supabase client configuration
- `src/main.tsx` - App entry point

### Config Files:
- `backend/requirements.txt` - Python dependencies
- `package.json` - Node.js dependencies  
- `supabase/functions/*/index.ts` - Edge functions

## 🚨 COMMON ISSUES & SOLUTIONS

### 1. Damage Images Not Loading in ReportViewer:
- **Cause**: useEffect dependency issues or wrong database table queries
- **Solution**: Use useMemo for stable arrays, query document_images table with image_url column

### 2. Vehicle Identification Inaccurate:
- **Cause**: Single attempt with suboptimal images
- **Solution**: Parallel identification with voting consensus (implemented)

### 3. Slow Report Generation:
- **Cause**: Sequential AI processing
- **Solution**: Parallel processing with ThreadPoolExecutor (implemented)

### 4. JSON Parsing Errors in ReportViewer:
- **Cause**: Fetching PDF content instead of JSON, or malformed responses
- **Solution**: Validate content-type and response text before parsing

### 5. Infinite Re-rendering Loops:
- **Cause**: Unstable useEffect dependencies
- **Solution**: Use useMemo/useCallback for object/array dependencies

## ⚡ RECENT PERFORMANCE OPTIMIZATIONS

### Parallel Processing Implementation (Latest):
- **Vehicle ID**: 3 parallel attempts with voting → Better accuracy
- **Area Detection**: 4 concurrent workers → Same accuracy, faster
- **Damage Analysis**: 8 concurrent workers → 5x speed improvement
- **Preserved Functionality**: All existing logic maintained, just parallelized

### Frontend Stability Fixes:
- Eliminated infinite loops in ReportViewer
- Enhanced error handling for JSON fetching
- Improved image loading reliability

## 🌐 DEPLOYMENT & ENVIRONMENT

### Railway Backend:
- **Auto-deploys** from GitHub main branch
- **Environment Variables**: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY
- **Scaling**: Handles parallel processing with ThreadPoolExecutor

### Supabase:
- **Database**: PostgreSQL with RLS policies
- **Storage**: Auto-damage-reports bucket for PDFs/JSONs
- **Edge Functions**: generate_report, report-complete

### Local Development:
- Frontend: `npm run dev` (port 8080)
- Backend: `uvicorn main:app --reload` (if running locally)

## 🔍 DEBUGGING TIPS

### Backend Debugging:
- Check Railway logs for API errors
- Monitor OpenAI API usage/rate limits
- Verify environment variables are set
- Test individual prompt phases

### Frontend Debugging:
- Browser console for React errors/warnings
- Network tab for API call failures
- Supabase dashboard for data issues
- Check localStorage for auth tokens

### Database Debugging:
- Use Supabase SQL editor for direct queries
- Check document status transitions
- Verify image URLs are accessible
- Monitor storage bucket permissions

## 🎯 CRITICAL SUCCESS FACTORS

1. **Image Quality**: Clear photos are essential for accurate AI analysis
2. **Prompt Engineering**: Specialized prompts for different damage areas
3. **Error Handling**: Robust fallbacks for AI failures
4. **Parallel Processing**: Maintains accuracy while dramatically improving speed
5. **State Management**: Proper React hooks prevent infinite loops
6. **Database Schema**: Correct table relationships for image handling

## 🔮 FUTURE IMPROVEMENTS

### Potential Enhancements:
- **Caching**: Cache AI results for similar damage patterns
- **Real-time Updates**: WebSocket progress updates during processing
- **Advanced Vision**: Integration with specialized automotive vision models
- **Mobile App**: Native mobile experience for field damage assessment
- **OCR Integration**: Extract VIN/license plate data automatically

---

## 🚀 QUICK START FOR NEW LLMS

When working on this project:

1. **Always check the current status first**: Are there active issues with ReportViewer, vehicle identification, or performance?

2. **Key areas to focus on**:
   - ReportViewer component for display issues
   - Backend pipeline for AI processing problems  
   - Database queries for data access issues
   - Parallel processing logic for performance

3. **Test workflow**:
   - Upload images → Check processing status → View generated report → Verify damage images display

4. **Common debugging**:
   - Browser console for frontend issues
   - Railway logs for backend problems
   - Supabase dashboard for database/storage issues

This guide should provide complete context for any LLM to immediately understand and work effectively with the AutoDamageConnect platform! 🚗💨
