# Record a real demo / デモ動画

Record only after the workflow succeeds on a Mac. No simulated terminal output
or generated screen should be presented as proof of a physical-device run.

Suggested 35–60 second clip:

| Scene | Capture |
| --- | --- |
| 1 · Goal | A connected iPhone and a terminal window; title: “One command to your iPhone”. |
| 2 · Run | Type `bash Try_Demo.command --lang ja` in the tool folder. |
| 3 · Progress | Show actual Xcode check, build and install stages. Mark any speed-up/time cut. |
| 4 · Result | Show HelloDevice opening on the actual iPhone. |
| 5 · Interaction | Tap the confirmation button and show the changed screen. |

For a clean recording, use a terminal window without previous account output and
an example project. Crop/mask personal paths, device names, Team IDs and other
unrelated information visible in the terminal. You can use the device's screen
recording for the result and join it to the real terminal recording.

Caption should specify the actual Mac, Xcode and iOS versions used. Distinguish
first-time setup from subsequent one-command runs. Do not imply that Apple login,
device trust or Developer Mode are bypassed.

日本語の見せ方：「コマンドを実行 → ビルド・インストール → iPhoneで起動 → タップ確認」。
初回のログインや端末準備を済ませている旨と、実際に使ったOS・Xcodeを添えます。
