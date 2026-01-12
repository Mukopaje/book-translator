# Quick Start Guide - New Features

## 🚀 Getting Started with Quality Verification, Pagination & Page Replacement

---

## Step 1: Run Database Migration

Before using the new features, update your database schema:

```bash
# Make sure you're in the project root
cd /Users/mukopaje/book-translator

# Run the migration
python backend/migrations/add_quality_fields.py
```

**Expected Output**:
```
Starting migration: Adding quality verification fields...
  1. Adding NEEDS_REVIEW to PageStatus enum...
  2. Adding quality_score column...
  3. Adding quality_level column...
  4. Adding quality_issues column...
  5. Adding quality_recommendations column...
  6. Adding replaced_at column...
✅ Migration completed successfully!
```

---

## Step 2: Restart Docker Services

```bash
# Stop services
docker-compose down

# Rebuild with new code
docker-compose build

# Start services
docker-compose up -d

# Verify all services are running
docker-compose ps
```

**Expected Output**: All services should show "Up" status:
- book-translator-frontend
- book-translator-backend
- book-translator-worker
- book-translator-db
- book-translator-redis

---

## Step 3: Test the Quality Agent (Optional)

```bash
# Run the test script
python test_quality_agent.py
```

This will run three test scenarios and show you how the quality agent works.

---

## Using the New Features

### 🎯 Feature 1: Automatic Quality Verification

**What it does**: Every page is automatically checked for quality after processing

**How to use**:
1. Process pages as usual (upload → queue → wait for completion)
2. After processing, each page will have a quality score:
   - **Excellent** (90-100): Perfect quality, no issues
   - **Good** (70-89): Acceptable quality, minor issues
   - **Acceptable** (70-89): Usable but may have some warnings
   - **Poor** (50-69): Low quality, needs review
   - **Failed** (0-49): Critical issues, must reprocess

3. Pages with score < 70 are automatically marked as `NEEDS_REVIEW`

**How to view quality issues**:
- In the page list, expand any page marked `NEEDS_REVIEW`
- Click on "⚠️ X Quality Issues" to see details
- Each issue shows:
  - Severity (critical, error, warning)
  - Component (diagram_agent, table_agent, etc.)
  - Specific message explaining the problem

---

### 📄 Feature 2: Pagination for Large Books

**What it does**: Loads pages 20 at a time instead of all at once

**How to use**:

1. **Navigate Between Pages**:
   - Click "⏮️ First" to go to the first page
   - Click "◀️ Prev" to go back 20 pages
   - Click "Next ▶️" to advance 20 pages
   - Click "Last ⏭️" to jump to the last page
   - See current position: "Page 3 / 25"

2. **Filter by Status**:
   - Use the "Filter by status" dropdown
   - Options:
     - **All** - Show all pages
     - **UPLOADED** - Only uploaded, not processed
     - **PROCESSING** - Currently being processed
     - **COMPLETED** - Successfully processed
     - **FAILED** - Processing failed
     - **NEEDS_REVIEW** - Completed but quality is low

3. **Select All on Current Page**:
   - Click "☑️ Select Page (20)" to select all visible pages
   - Then use "🔁 Reprocess Selected" to reprocess them

**Tips**:
- For 500-page books, you'll see 25 page groups (500 ÷ 20)
- Use status filter to quickly find problem pages
- Pagination resets when changing filters

---

### 🔄 Feature 3: Replace Poor-Quality Images

**What it does**: Replace the input image for pages with quality issues

**When to use**:
- Page status is `FAILED` or `NEEDS_REVIEW`
- Quality score is below 70
- Quality issues mention image clarity or diagram detection problems

**How to use**:

1. **Identify pages needing replacement**:
   - Filter by status: `NEEDS_REVIEW`
   - Look for quality scores < 70
   - Check quality issues for image-related problems

2. **Replace the image**:
   - Find the page in the list
   - Look for the "🔄 Replace Image" button
   - Click to open file uploader
   - Select your better-quality scan
   - Wait for upload confirmation

3. **Reprocess**:
   - After replacement, page status returns to `UPLOADED`
   - Click "🚀 Queue" to process with the new image
   - Check the new quality score after processing

**Example workflow**:
```
Page 47: Quality Score = 55 (Poor)
Issue: "Diagram has 0 labels (expected at least 2)"

Action: Replace with higher-resolution scan
↓
Page 47: Status = UPLOADED (reset)
↓
Queue for processing
↓
Page 47: Quality Score = 95 (Excellent)
```

---

## Common Workflows

### Workflow 1: Process a 500-Page Book

```
1. Upload all 500 pages (or batches of 100)
2. Use pagination to navigate and verify uploads
3. Click "🚀 Queue All (Async)" to process all pages
4. Monitor progress:
   - Filter by "PROCESSING" to see active pages
   - Filter by "COMPLETED" to see finished pages
   - Filter by "NEEDS_REVIEW" to find quality issues
5. For any NEEDS_REVIEW pages:
   - Check quality issues
   - Replace image if needed
   - Requeue for processing
6. When all pages are COMPLETED:
   - Download complete book using sidebar button
```

### Workflow 2: Fix Quality Issues in Bulk

```
1. After bulk processing, filter by "NEEDS_REVIEW"
2. For each flagged page:
   a. Review quality issues
   b. If image quality issue → Replace image
   c. If data issue (empty tables/diagrams) → May need source document review
   d. Requeue page
3. Monitor reprocessed pages
4. Verify improved quality scores
```

### Workflow 3: Iterative Quality Improvement

```
1. Process first 20 pages
2. Review quality scores
3. Identify common issues (e.g., all diagrams scoring low)
4. Adjust scan settings or image preprocessing
5. Replace images for problem pages
6. Compare quality before/after
7. Apply improvements to remaining pages
```

---

## Keyboard Shortcuts (Proposed)

None implemented yet, but you could add:
- `Ctrl+→` : Next page
- `Ctrl+←` : Previous page
- `Ctrl+Home` : First page
- `Ctrl+End` : Last page

---

## Troubleshooting

### Problem: Quality scores not showing

**Check**:
```bash
# Verify migration ran
docker-compose exec backend python -c "from app.database import engine; from sqlalchemy import inspect; print('quality_score' in [c['name'] for c in inspect(engine).get_columns('pages')])"
```

**Should output**: `True`

**Fix**: Run the migration script again

---

### Problem: Can't navigate pages

**Check**: Browser console for errors

**Fix**:
```bash
# Clear session state
# In Streamlit UI: Click hamburger menu → Clear cache
# Or restart frontend
docker-compose restart frontend
```

---

### Problem: Replace image button not showing

**Possible causes**:
1. Page status is COMPLETED with good quality (score >= 70)
2. Page is not from backend (local-only upload)

**Solution**: Only pages meeting these criteria show the button:
- Status is `FAILED` or `NEEDS_REVIEW`, OR
- Quality score exists and is < 70

---

## Performance Expectations

| Operation | Time | Notes |
|-----------|------|-------|
| Load 20 pages | < 1s | First page load |
| Navigate pages | < 0.5s | Subsequent navigation |
| Upload replacement image | 2-5s | Depends on image size |
| Quality verification | < 2s | Per page, automatic |
| Filter pages | < 0.5s | Instant filtering |

---

## Best Practices

1. **Start Small**: Process 10-20 pages first to calibrate your workflow
2. **Monitor Quality**: Check quality scores regularly, don't wait until all pages are done
3. **Replace Early**: If first pages have quality issues, fix scan settings before processing all
4. **Use Filters**: Leverage status filters to focus on specific page groups
5. **Batch Replacements**: If many pages have similar issues, fix source and replace in batches
6. **Review Recommendations**: Quality recommendations give specific guidance on improvements

---

## What Changed (For Developers)

### New Database Columns
- `quality_score` (INTEGER): 0-100 score
- `quality_level` (VARCHAR): Excellent, Good, Acceptable, Poor, Failed
- `quality_issues` (TEXT): JSON array of issues
- `quality_recommendations` (TEXT): JSON array of suggestions
- `replaced_at` (TIMESTAMP): When image was last replaced

### New API Endpoints
- `PUT /projects/{id}/pages/{id}/replace-image`: Replace page image
- `GET /projects/{id}/pages?skip=0&limit=20&status_filter=X`: Paginated listing

### New Page Status
- `NEEDS_REVIEW`: Page completed but quality score < 70

### New Session State Variables
- `current_page_offset`: Pagination offset
- `page_size`: Pages per view (default: 20)
- `total_pages_count`: Total pages from API
- `status_filter`: Current status filter

---

## Support

If you encounter issues:

1. Check logs:
   ```bash
   docker-compose logs worker | tail -100
   docker-compose logs backend | tail -100
   ```

2. Verify database:
   ```bash
   docker-compose exec backend python -c "from app.database import engine; print(engine.execute('SELECT COUNT(*) FROM pages').scalar())"
   ```

3. Test quality agent:
   ```bash
   python test_quality_agent.py
   ```

---

**Happy translating! 📚→📖**
