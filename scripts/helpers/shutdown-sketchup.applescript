#!/usr/bin/osascript

-- Gracefully shutdown SketchUp

on run
    set appName to "SketchUp"
    set maxWaitSeconds to 30

    -- Check if SketchUp is running
    tell application "System Events"
        if not (exists process appName) then
            -- SketchUp not running, nothing to do
            return
        end if
    end tell

    -- Quit SketchUp (outside System Events block, with saving no to skip dialogs)
    tell application appName to quit saving no

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
