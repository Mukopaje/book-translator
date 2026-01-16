# Super Admin Guide: Technical Book Translator

## 1. Promoting a User to Admin
For security, admin privileges cannot be granted through the web interface. You must use the command-line tool from the backend container.

### Prerequisites
1. The user must already have an account (signed up through the landing page).

### Promotion Command
Run this command on your host machine (replacing `user@example.com` with the actual email):

```bash
docker exec -it book-translator-backend python3 tools/manage_admin.py --email user@example.com
```

### What This Does
*   Sets `is_admin = 1` in the database.
*   Grants `999,999` page credits.
*   Sets subscription status to `admin`.
*   Enables the **Admin Control Room** toggle in the app sidebar.

---

## 2. Managing Users & Credits
Once logged in as an admin, toggle **"👑 Admin Mode"** in the sidebar.

### Granting Credits manually
If a user pays via a non-Stripe method or needs a top-up:
1. Go to the **User Management** section.
2. Select the user from the dropdown.
3. Enter the amount of credits (pages) to add.
4. Click **🎁 Grant Credits**.

---

## 3. System Maintenance

### Stuck Task Recovery
If diagrams or pages seem stuck in "Processing" for more than 10 minutes (due to worker restarts or API timeouts), click **"🧹 Cleanup Stuck Tasks"** in the Admin Dashboard. This will safely re-queue them.

### Real-time Monitoring
The dashboard provides live stats on:
*   **Total Users & Projects**
*   **Success vs. Failure Rates**
*   **Worker Queue Latency**
*   **Premium Conversion Tracking**
