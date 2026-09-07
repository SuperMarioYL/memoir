Output assets/demo.gif
Require MEMOIR_HOME
Set FontSize 14
Set Width 1200
Set Height 600
Set Theme "Dracula"
Set Padding 20

# 10-minute happy path: ingest -> cost -> (chat needs DEEPSEEK_API_KEY, shown last)
Type "memoir --version"
Enter
Sleep 500ms

Type "memoir ingest examples/notes"
Enter
Sleep 2s

Type "memoir cost"
Enter
Sleep 2s

Type "memoir status"
Enter
Sleep 1s
