#!/usr/bin/osascript

-- Get SketchUp window position and size
-- Returns JSON format: {"x":100,"y":50,"width":1200,"height":800,"isMaximized":false}

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
                -- Find the main document window (largest window)
                set mainWindow to missing value
                set maxArea to 0

                repeat with w in windows
                    try
                        -- Get window size to find the largest one
                        set wSize to size of w
                        set wArea to (item 1 of wSize) * (item 2 of wSize)

                        -- Main window is typically the largest
                        if wArea > maxArea then
                            set maxArea to wArea
                            set mainWindow to w
                        end if
                    end try
                end repeat

                if mainWindow is missing value then
                    return "{\"error\":\"No suitable SketchUp window found\"}"
                end if

                tell mainWindow
                    -- Get position and size
                    set windowPosition to position
                    set windowSize to size

                    -- Extract values
                    set x to item 1 of windowPosition
                    set y to item 2 of windowPosition
                    set winWidth to item 1 of windowSize
                    set winHeight to item 2 of windowSize

                    -- Detect if window is maximized
                    -- Window is considered maximized if it covers most of the screen
                    -- Allow 100px tolerance for menu bar, dock, etc.
                    set isMaximized to false
                    if winWidth >= (screenWidth - 100) and winHeight >= (screenHeight - 150) then
                        set isMaximized to true
                    end if

                    -- Build JSON response
                    set jsonResult to "{\"x\":" & x & ",\"y\":" & y & ",\"width\":" & winWidth & ",\"height\":" & winHeight & ",\"isMaximized\":" & isMaximized & "}"

                    return jsonResult
                end tell
            end tell
        end tell
    on error errMsg
        return "{\"error\":\"" & errMsg & "\"}"
    end try
end run
