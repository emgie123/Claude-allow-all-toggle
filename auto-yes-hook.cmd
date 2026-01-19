@echo off
if exist "%USERPROFILE%\.claude-auto-yes" echo {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"Auto-approved by toggle"}}& exit /b 0
