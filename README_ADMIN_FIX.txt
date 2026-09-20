ADMIN ACCESS FULL FIX

1. Set Railway variables:
   OWNER_ID=<numeric Telegram user ID>
   ADMINS=<numeric Telegram user ID(s), comma separated>
   ADMIN_IDS=<optional additional numeric IDs>

2. Redeploy the project.
3. Send /admin. If access is still wrong, send /admincheck; it reports ENV and DB admin status.

Admin access is checked from OWNER_ID/OWNER_IDS/ADMINS/ADMIN_IDS and users.is_admin.
Admin commands /admin, /panel, /getqrisid bypass Force-Join for authorized admins, and /admin is allowed through middleware for diagnosis when env config is wrong.
