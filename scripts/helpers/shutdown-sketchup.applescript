#!/usr/bin/osascript

-- Gracefully shutdown SketchUp after saving window position

on run
    set appname to "SketchUp"
    
    -- Get the directory of this script
    set scriptPath to (POSIX path of (path to me))
    set AppleScript's text item delimiters to "/"
    set pathItems to text items of scriptPath
    set pathItems to items 1 thru -2 of pathItems
    set scriptDir to pathItems as string
    set AppleScript's text item delimiters to ""
    
    -- Save window position before quitting
    try
        do shell script scriptDir & "/manage-window-position.sh save"
    on error errMsg
        -- Log error but continue with shutdown
        log "Warning: Could not save window position: " & errMsg
    end try
    
    -- Quit SketchUp
    tell application appname to quit
    
    -- Wait until SketchUp has quit
    repeat until application appname is not running
        delay 0.2
    end repeat
end run