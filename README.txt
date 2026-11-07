Elite announcer: separate service for your second Telegram account.
Required environment variables: TG_API_ID, TG_API_HASH, TG_SESSION.
Original target: elitemethodchat (always included).
14 additional groups are configured in the source; 15 total with no repeated Hdc5NmE9.
No TG_EXTRA_CHATS variable is needed for these configured groups:
elitemethodchat
gemini3369
ddh992
OpenHuge_ai
Hdc5NmE9
Claudeaichatss
aitoolsbuynsell
ChatgptPlusDeal
saleslabss
amygpt
maoli9112
pwawz8
https://t.me/+S3GSX490EWo2NTY9
quanziai
asoftwarez

Source: latest Saved Messages item, preserving text formatting and media.
The latest message is read again for each sending round. To change the promotion,
put the new message last in Saved Messages on the TG_SESSION account.
Sends to each group immediately on startup, then waits 4500 seconds (75 minutes)
after that group's attempt. Groups are sent to in sequence during each round.

To add groups in Railway, add the optional variable TG_EXTRA_CHATS.
Example only (replace these names with your actual group usernames):
TG_EXTRA_CHATS=your_group_one,your_group_two
Usernames, @usernames, public https://t.me/username links, and private
https://t.me/+hash or https://t.me/joinchat/hash invite links are accepted.
Separate groups with commas, spaces, or newlines. Duplicates are removed,
including duplicates of the configured groups. Empty/unset uses the 15 groups above.
You can also add actual group usernames to DEFAULT_TARGET_CHATS in telegram_promo.py.
The account must already have access and permission to send in each group.
Private invite links must be valid and the TG_SESSION account must already be a member.
Private links are checked for membership before sending; the script does not join groups.
An unavailable private group is logged and retried on its next scheduled attempt.
Message links and numeric group IDs are not supported by this setting.

An error or slow mode in one group does not stop the other groups.
For slow mode, skip the affected group and retry after Telegram's remaining wait
plus two seconds. If it still requires a wait, reschedule that group again and
continue the others. After a successful send, its normal 75-minute timer resumes.
Telegram account-wide FloodWait pauses all sending for the required time.
Telegram wait limits and connection issues may delay the normal 75-minute schedule.
Use one running replica. Redeploy/restart triggers an immediate send.
Put the advertisement as the latest Saved Messages item before starting.
Upload these files to the root of a separate repository and deploy with the Dockerfile.
No public domain or database is needed. Never commit credentials or the session.

Offline checks (no Telegram connection): python -m unittest -v test_promo.py

شرح سريع:
تمت إضافة ١٤ جروب إلى الجروب القديم elitemethodchat، والإجمالي ١٥ جروب.
الجروب Hdc5NmE9 موجود مرة واحدة فقط. الإرسال لكل جروب كل ٧٥ دقيقة.
لو جروب عليه وضع بطيء، يتم تخطيه وإكمال باقي الجروبات، ثم إعادة المحاولة
بعد مدة الانتظار التي يحددها تيليجرام مع ثانيتين احتياط. لو الانتظار مستمر،
يتأجل نفس الجروب مرة أخرى؛ وبعد نجاح الإرسال يعود لجدول الساعة والربع.
الجروبات المطلوبة مضافة داخل الكود بالفعل ولا تحتاج متغير إعدادات إضافي.
لإضافة جروبات أخرى، أضف متغير TG_EXTRA_CHATS في Railway وضع يوزرات الجروبات
مفصولة بفاصلة، أو أضفها إلى DEFAULT_TARGET_CHATS داخل telegram_promo.py.
مثال للتوضيح فقط: your_group_one,your_group_two
الإعلان هو آخر رسالة في Saved Messages لحساب الإرسال، بنفس النص والتنسيق والمرفقات.
يتم جلب آخر رسالة مجددًا قبل كل جولة؛ تغييرها يغيّر الإعلان في الإرسال التالي.
أول إرسال يكون فور تشغيل السكربت، ثم كل ساعة وربع لكل جروب.
الحساب لازم يكون منضم للجروبات وله صلاحية الكتابة، بما فيها الجروب الخاص.
رابط الدعوة الخاص مدعوم إذا كان صالحًا والحساب عضو بالفعل؛ لا يتم الانضمام تلقائيًا.
