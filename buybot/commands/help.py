HELP = """<b>NOX buybot commands</b> (group admins only)

/status  bot health and current settings
/stats  today's buys, volume, leaderboard
/test [usd]  post a sample buy (default $500)
/pause, /resume  stop or start posting

<b>Appearance</b>
/setemoji 🟢  bar emoji (reply to a message with the emoji to use it)
/setstep 25  USD per emoji
/setmax 60  max emojis in the bar
/setmin 25  ignore buys below this USD value
/settier medium|large|whale 1000  tier thresholds
/setmedia small|medium|large|whale|all  reply to a GIF, MP4, photo or sticker
/clearmedia tier|all
/toggle position|market|buttons|pinwhales
/addlink Trending https://...  and  /dellink Trending

<b>Emoji settings</b>
/emoji  list the emoji slots and which are customised
/emoji &lt;slot&gt;  reply to a message with an emoji to use it for that slot
/emoji &lt;slot&gt; clear  restore the standard emoji
/emojiid  reply to a message to list its emoji ids"""
