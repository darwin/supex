#!/usr/bin/osascript

-- Gracefully shutdown SketchUp after saving window position

on run
    set appName to "SketchUp"
    set maxWaitSeconds to 30

    -- Get the directory of this script using simpler path manipulation
    set scriptPath to POSIX path of (path to me)
    set scriptDir to do shell script "dirname " & quoted form of scriptPath

    -- Save window position before quitting
    try
        do shell script scriptDir & "/manage-window-position.sh save"
    on error errMsg
        -- Log error but continue with shutdown
        log "Warning: Could not save window position: " & errMsg
    end try

    -- Quit SketchUp if running
    tell application "System Events"
        if exists process appName then
            tell application appName to quit
        else
            -- SketchUp not running, nothing to do
            return
        end if
    end tell

    -- Wait for SketchUp to quit with timeout
    set waitedSeconds to 0
    repeat until application appName is not running
        delay 0.5
        set waitedSeconds to waitedSeconds + 0.5
        if waitedSeconds >= maxWaitSeconds then
            log "Warning: SketchUp did not quit within " & maxWaitSeconds & " seconds"
            exit repeat
        end if
    end repeat
end run
