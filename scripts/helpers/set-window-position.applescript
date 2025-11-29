#!/usr/bin/osascript

-- Set SketchUp window position and size
-- Arguments: x y width height maximized (0 or 1)

on run argv
    if (count of argv) < 4 then
        return "Error: Usage: set-window-position.applescript x y width height [maximized]"
    end if
    
    -- Parse arguments
    set x to item 1 of argv as integer
    set y to item 2 of argv as integer
    set w to item 3 of argv as integer
    set h to item 4 of argv as integer
    
    set shouldMaximize to false
    if (count of argv) ≥ 5 then
        if item 5 of argv is "1" or item 5 of argv is "true" then
            set shouldMaximize to true
        end if
    end if
    
    try
        tell application "System Events"
            tell process "SketchUp"
                -- Make sure SketchUp is frontmost
                set frontmost to true
                
                -- Wait a moment for window to be ready
                delay 0.5
                
                -- Find the main document window (largest window)
                set mainWindow to missing value
                set maxArea to 0
                
                repeat with win in windows
                    try
                        -- Get window size to find the largest one
                        set winSize to size of win
                        set winArea to (item 1 of winSize) * (item 2 of winSize)
                        
                        -- Main window is typically the largest
                        if winArea > maxArea then
                            set maxArea to winArea
                            set mainWindow to win
                        end if
                    end try
                end repeat
                
                if mainWindow is missing value then
                    error "No suitable SketchUp window found"
                end if
                
                tell mainWindow
                    if shouldMaximize then
                        -- Click the zoom button (green button)
                        try
                            click button 2
                        on error
                            -- Fallback: try to maximize by setting to screen size
                            set position to {0, 25}
                            -- Note: Would need screen size detection for proper maximize
                        end try
                    else
                        -- Set position and size
                        set position to {x, y}
                        set size to {w, h}
                    end if
                end tell
            end tell
        end tell
        
        return "Window position set successfully"
        
    on error errMsg
        return "Error: " & errMsg
    end try
end run