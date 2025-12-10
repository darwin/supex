#!/usr/bin/osascript

-- Get ALL SketchUp window positions and sizes
-- Returns JSON v2 format with all windows keyed by title (or "main" for document window)
-- Main window is identified by title ending with " - SketchUp XXXX"

on run
    try
        -- Get screen size from Finder desktop bounds
        tell application "Finder"
            set screenBounds to bounds of window of desktop
            set screenWidth to item 3 of screenBounds
            set screenHeight to item 4 of screenBounds
        end tell

        tell application "System Events"
            -- Check if SketchUp is running
            if not (exists process "SketchUp") then
                return "{\"error\":\"SketchUp is not running\"}"
            end if

            tell process "SketchUp"
                set windowCount to count of windows
                if windowCount is 0 then
                    return "{\"error\":\"No SketchUp windows found\"}"
                end if

                -- Build windows JSON object
                set windowsJson to ""
                set isFirst to true

                repeat with w in windows
                    try
                        set winTitle to name of w
                        set winPos to position of w
                        set winSize to size of w

                        set x to item 1 of winPos
                        set y to item 2 of winPos
                        set winWidth to item 1 of winSize
                        set winHeight to item 2 of winSize

                        -- Detect if window is maximized
                        set isMaximized to false
                        if winWidth >= (screenWidth - 100) and winHeight >= (screenHeight - 150) then
                            set isMaximized to true
                        end if

                        -- Determine window key
                        -- Main window title ends with " - SketchUp XXXX" (year)
                        set windowKey to winTitle
                        set titlePattern to ""
                        set matchedTitle to winTitle

                        if winTitle ends with " - SketchUp 2024" or winTitle ends with " - SketchUp 2025" or winTitle ends with " - SketchUp 2026" or winTitle ends with " - SketchUp 2027" then
                            set windowKey to "main"
                            set titlePattern to " - SketchUp [0-9]{4}$"
                        end if

                        -- Add comma separator if not first
                        if not isFirst then
                            set windowsJson to windowsJson & ","
                        end if
                        set isFirst to false

                        -- Escape quotes in title for JSON
                        set escapedTitle to my replaceText(matchedTitle, "\"", "\\\"")

                        -- Build JSON for this window
                        set windowJson to "\"" & windowKey & "\":{"
                        if titlePattern is not "" then
                            set windowJson to windowJson & "\"titlePattern\":\"" & titlePattern & "\","
                        end if
                        set windowJson to windowJson & "\"matchedTitle\":\"" & escapedTitle & "\","
                        set windowJson to windowJson & "\"x\":" & x & ","
                        set windowJson to windowJson & "\"y\":" & y & ","
                        set windowJson to windowJson & "\"width\":" & winWidth & ","
                        set windowJson to windowJson & "\"height\":" & winHeight & ","
                        set windowJson to windowJson & "\"isMaximized\":" & isMaximized
                        set windowJson to windowJson & "}"

                        set windowsJson to windowsJson & windowJson
                    end try
                end repeat

                -- Build final JSON with version 2 format
                set timestamp to do shell script "date -u +\"%Y-%m-%dT%H:%M:%SZ\""
                set jsonResult to "{\"version\":2,\"timestamp\":\"" & timestamp & "\",\"windows\":{" & windowsJson & "}}"

                return jsonResult
            end tell
        end tell
    on error errMsg
        return "{\"error\":\"" & errMsg & "\"}"
    end try
end run

-- Helper function to replace text
on replaceText(theText, searchString, replacementString)
    set AppleScript's text item delimiters to searchString
    set theTextItems to every text item of theText
    set AppleScript's text item delimiters to replacementString
    set theText to theTextItems as string
    set AppleScript's text item delimiters to ""
    return theText
end replaceText
