#!/usr/bin/osascript

-- Set SketchUp window position and size
-- Arguments: windowKey title x y width height maximized (0 or 1)
-- windowKey: "main" for document window (matched by title pattern), or exact window title
-- title: the actual title to match (used as hint for logging)

on run argv
    if (count of argv) < 6 then
        return "Error: Usage: set-window-position.applescript windowKey title x y width height [maximized]"
    end if

    -- Parse arguments
    set windowKey to item 1 of argv
    set searchTitle to item 2 of argv
    set x to item 3 of argv as integer
    set y to item 4 of argv as integer
    set w to item 5 of argv as integer
    set h to item 6 of argv as integer

    set shouldMaximize to false
    if (count of argv) >= 7 then
        if item 7 of argv is "1" or item 7 of argv is "true" then
            set shouldMaximize to true
        end if
    end if

    try
        -- Get screen size from Finder desktop bounds
        tell application "Finder"
            set screenBounds to bounds of window of desktop
            set screenWidth to item 3 of screenBounds
            set screenHeight to item 4 of screenBounds
        end tell

        -- Menu bar height (approximate)
        set menuBarHeight to 25

        tell application "System Events"
            tell process "SketchUp"
                -- Make sure SketchUp is frontmost
                set frontmost to true

                -- Wait a moment for window to be ready
                delay 0.3

                set targetWindow to missing value

                if windowKey is "main" then
                    -- Find main window by title pattern (ends with " - SketchUp XXXX")
                    repeat with win in windows
                        try
                            set winTitle to name of win
                            if winTitle ends with " - SketchUp 2024" or winTitle ends with " - SketchUp 2025" or winTitle ends with " - SketchUp 2026" or winTitle ends with " - SketchUp 2027" then
                                set targetWindow to win
                                exit repeat
                            end if
                        end try
                    end repeat
                else
                    -- Find window by exact title match
                    repeat with win in windows
                        try
                            if name of win is windowKey then
                                set targetWindow to win
                                exit repeat
                            end if
                        end try
                    end repeat
                end if

                if targetWindow is missing value then
                    return "Warning: Window not found: " & windowKey
                end if

                tell targetWindow
                    if shouldMaximize then
                        -- Maximize to full screen (below menu bar)
                        set position to {0, menuBarHeight}
                        set size to {screenWidth, screenHeight - menuBarHeight}
                    else
                        -- Set saved position and size
                        set position to {x, y}
                        set size to {w, h}
                    end if
                end tell

                return "Restored: " & windowKey
            end tell
        end tell

    on error errMsg
        return "Error: " & errMsg
    end try
end run
