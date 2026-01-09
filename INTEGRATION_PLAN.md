# Frontend-Backend Integration Plan
**Goal**: Complete Phase 2 - Full page persistence and project management

---

## Current Architecture

### ✅ What Works
```
User → Streamlit (app_v3.py) → FastAPI Backend → PostgreSQL
                                                 ↓
                                           GCS Storage
```

- User auth (signup/login/JWT)
- Project CRUD operations
- Database schema (users, projects, pages)
- Backend API endpoints

### ❌ What's Broken
- Pages processed in Streamlit **don't save to database**
- Refreshing browser **loses all processed pages**
- No way to see previously translated pages
- Can't download complete merged book

---

## Implementation Tasks

### Task 1: Connect Page Upload to Backend (Priority: HIGH)
**File**: `app_v3.py`
**Function**: `add_page()` around line 118

**Current Behavior**:
```python
def add_page(uploaded_file, role='page'):
    # Saves to local images_to_process/
    # Adds to session_state['pages'] (lost on reload)
```

**New Behavior**:
```python
def add_page(uploaded_file, role='page'):
    if not st.session_state.current_project:
        st.error("Please select a project first")
        return
    
    # Upload to backend
    api = get_api_client()
    project_id = st.session_state.current_project['id']
    
    # Determine page number (from filename or auto-increment)
    page_number = extract_page_number(uploaded_file.name)
    
    # Upload file
    page_data = api.upload_page(
        project_id=project_id,
        page_number=page_number,
        file=uploaded_file,
        filename=uploaded_file.name
    )
    
    # Add to local processing queue
    st.session_state['pages'].append({
        'id': page_data['id'],
        'page_id': page_data['id'],  # Backend page ID
        'path': page_data['original_image_path'],
        'name': uploaded_file.name,
        'role': role,
        'status': 'uploaded'
    })
```

---

### Task 2: Save Processing Results to Backend (Priority: HIGH)
**File**: `app_v3.py`
**Function**: Page processing workflow (around line 270-350)

**Current Behavior**:
- Processes page locally
- Stores results in session_state only
- Results lost on page reload

**New Behavior**:
After translation completes:
```python
# After successful translation
api = get_api_client()
api.update_page_status(
    project_id=project_id,
    page_id=page_id,
    status='completed',
    ocr_text=japanese_text,
    translated_text=english_text,
    output_pdf_path=pdf_path  # Upload to GCS first
)

# Update project progress
api.update_project(
    project_id=project_id,
    completed_pages=completed_pages + 1
)
```

**Backend Endpoint Needed**:
```python
# backend/app/api/pages.py
@router.patch("/projects/{project_id}/pages/{page_id}")
def update_page(
    project_id: int,
    page_id: int,
    status: Optional[str] = None,
    ocr_text: Optional[str] = None,
    translated_text: Optional[str] = None,
    output_pdf_path: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership, update page, return updated page
```

---

### Task 3: Display Pages from Database (Priority: HIGH)
**File**: `app_v3.py`
**Function**: `render_page_list()` around line 230

**Current Behavior**:
```python
def render_page_list():
    # Shows pages from session_state only
    for page in st.session_state['pages']:
        st.write(page['name'])
```

**New Behavior**:
```python
def render_page_list():
    if not st.session_state.current_project:
        st.info("No project selected")
        return
    
    api = get_api_client()
    project_id = st.session_state.current_project['id']
    
    # Load pages from database
    pages = api.list_pages(project_id)
    
    if not pages:
        st.info("No pages uploaded yet")
        return
    
    st.subheader(f"Pages ({len(pages)})")
    
    for page in pages:
        col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
        
        with col1:
            st.write(f"#{page['page_number']}")
        
        with col2:
            status_emoji = {
                'uploaded': '📤',
                'processing': '⏳',
                'completed': '✅',
                'failed': '❌'
            }
            st.write(f"{status_emoji.get(page['status'], '❓')} {page['status']}")
        
        with col3:
            if page['status'] == 'completed' and page['output_pdf_path']:
                if st.button("📥 Download PDF", key=f"dl_{page['id']}"):
                    # Download from GCS or local
                    pass
        
        with col4:
            if page['status'] == 'completed':
                if st.button("🔄 Re-translate", key=f"ret_{page['id']}"):
                    # Re-process this page
                    pass
```

---

### Task 4: Implement PDF Merge (Priority: MEDIUM)
**File**: `backend/app/api/projects.py`
**New Endpoint**:

```python
@router.get("/projects/{project_id}/download-book")
def download_complete_book(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Merge all completed page PDFs into single book."""
    project = verify_project_access(db, project_id, current_user.id)
    
    # Get all completed pages in order
    pages = db.query(Page).filter(
        Page.project_id == project_id,
        Page.status == 'completed',
        Page.output_pdf_path.isnot(None)
    ).order_by(Page.page_number).all()
    
    if not pages:
        raise HTTPException(404, "No completed pages found")
    
    # Merge PDFs using PyPDF2
    from PyPDF2 import PdfMerger
    import tempfile
    
    merger = PdfMerger()
    for page in pages:
        # Download from GCS or read local
        pdf_path = download_pdf(page.output_pdf_path)
        merger.append(pdf_path)
    
    # Save merged PDF
    output_path = f"output/{project.title}_complete.pdf"
    merger.write(output_path)
    merger.close()
    
    # Upload to GCS and return signed URL
    storage_service = StorageService()
    gcs_path = storage_service.upload_output_pdf(project_id, output_path)
    signed_url = storage_service.get_signed_url(gcs_path)
    
    return {"url": signed_url, "filename": f"{project.title}_complete.pdf"}
```

**Dependencies**: Install PyPDF2
```bash
pip install PyPDF2
```

---

### Task 5: Add "Download Complete Book" Button (Priority: MEDIUM)
**File**: `app_v3.py`
**Location**: In project view, after page list

```python
if st.session_state.current_project:
    project = st.session_state.current_project
    
    if project.get('completed_pages', 0) > 0:
        if st.button("📚 Download Complete Book (Merged PDF)", type="primary"):
            with st.spinner("Merging PDFs..."):
                api = get_api_client()
                result = api.download_complete_book(project['id'])
                st.success(f"✅ Book ready!")
                st.markdown(f"[📥 Download {result['filename']}]({result['url']})")
```

---

## Testing Checklist

### End-to-End Test
1. [ ] **Signup & Login**
   - Create new user account
   - Login successfully
   - JWT token stored

2. [ ] **Create Project**
   - Fill in title, author, context
   - Project appears in database
   - Project persists after refresh

3. [ ] **Upload Pages**
   - Upload page 28
   - Upload page 29
   - Both show in page list with "uploaded" status

4. [ ] **Process Pages**
   - Translate page 28
   - Status changes to "completed"
   - OCR and translation text saved in database
   - PDF generated and path stored

5. [ ] **Persistence Test**
   - **Refresh browser**
   - Login again
   - Select project
   - **Verify both pages still show with completed status**
   - Download individual PDFs

6. [ ] **Merge Book**
   - Click "Download Complete Book"
   - Merged PDF contains pages 28 and 29 in order
   - Page numbers show correctly (28, 29)

7. [ ] **Multi-Session Test**
   - Close browser completely
   - Open new browser window
   - Login
   - Verify all projects and pages still exist

---

## Database Verification

After processing pages, verify in pgAdmin:

```sql
-- Check users
SELECT * FROM users;

-- Check projects
SELECT id, title, author, total_pages, completed_pages, created_at 
FROM projects;

-- Check pages
SELECT id, project_id, page_number, status, 
       LENGTH(ocr_text) as ocr_chars,
       LENGTH(translated_text) as trans_chars,
       output_pdf_path
FROM pages
ORDER BY project_id, page_number;
```

---

## Implementation Order

**Session 1 (2-3 hours)**: Core Integration
1. Add `update_page` endpoint to backend
2. Modify `add_page()` to call API
3. Update processing workflow to save results
4. Test: Upload → Translate → Verify database

**Session 2 (1 hour)**: UI Updates
1. Modify `render_page_list()` to load from database
2. Add status indicators
3. Add download buttons
4. Test: Refresh page → Pages still show

**Session 3 (1-2 hours)**: PDF Merging
1. Install PyPDF2
2. Add merge endpoint
3. Add download button
4. Test: Merge 3 pages → Download book

---

## Success Criteria

✅ **Phase 2 Complete When**:
- User can upload multiple pages
- Pages persist in database
- Reloading browser doesn't lose work
- Can download individual page PDFs
- Can download merged complete book
- All data survives server restarts

**Current Progress**: 40% → Target: 100%
**Estimated Time**: 4-6 hours total
