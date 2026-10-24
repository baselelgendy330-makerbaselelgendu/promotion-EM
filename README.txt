Elite announcer: separate service for your second Telegram account.
Required environment variables: TG_API_ID, TG_API_HASH, TG_SESSION.
Target: elitemethodchat. Source: latest Saved Messages item.
Sends immediately on every startup, then waits 5400 seconds after each attempt.
Use one running replica. Redeploy/restart triggers an immediate send.
Put the advertisement as the latest Saved Messages item before starting.
Upload these files to the root of a separate repository and deploy with the Dockerfile.
No public domain or database is needed. Never commit credentials or the session.
