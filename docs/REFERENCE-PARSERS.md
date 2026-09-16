# Reference parsers to clone

These two projects already solve the ZIP/JSON-to-structure parsing for
Instagram and Facebook takeouts. They are NOT added as a dependency, they
serve as reference implementations to port the actual field extraction from
into `api/app/parsers/instagram.py` and `facebook.py` (including the
encoding fix, which neither original handles correctly).

## Instagram

```bash
git clone https://github.com/gavindsouza/instagram-to-sqlite.git reference/instagram-to-sqlite
```

Relevant: the iteration over `your_instagram_activity/messages/inbox/<thread>/message_1.json`
and the mapping to `chat_room`, `sender_name`, `timestamp_ms`, `content`,
`share`, `photos`, `videos`, `audio_files`. License: MIT.

## Facebook

```bash
git clone https://github.com/MyNameIsMikeGreen/Facebook-Message-Parser.git reference/facebook-message-parser
```

Relevant: merging multiple `message_1.json`, `message_2.json`, ... files per
thread (long chats get split by Meta across several files), and the SQLite
target schema as a template for our `Message` pydantic class.

## Known encoding bug (NOT fixed in either reference)

Meta serves special characters/emoji incorrectly encoded (UTF-8 bytes get
misinterpreted as Latin-1). The fix is already implemented in
`api/app/parsers/encoding_fix.py` and should be applied to every string
value (`sender_name`, `content`) extracted by either reference project.

```python
def fix_mojibake(text: str) -> str:
    return text.encode("latin1").decode("utf8")
```
