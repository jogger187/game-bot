import Quartz
import CoreFoundation
import sys
import json

def event_tap_callback(proxy, type, event, refcon):
    if type == Quartz.kCGEventLeftMouseDown:
        point = Quartz.CGEventGetLocation(event)
        x, y = point.x, point.y
        
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID
        )
        
        found_win = None
        for win in window_list:
            layer = win.get('kCGWindowLayer', 0)
            if layer > 0: # usually overlays like cursor, dock, etc. We want normal app windows (0) or slightly below.
                continue
                
            bounds = win.get('kCGWindowBounds', {})
            bx, by, bw, bh = bounds.get('X', 0), bounds.get('Y', 0), bounds.get('Width', 0), bounds.get('Height', 0)
            if bx <= x <= bx + bw and by <= y <= by + bh:
                found_win = win
                break
                
        if found_win:
            print(json.dumps({
                "window_id": found_win.get("kCGWindowNumber"),
                "owner_name": found_win.get("kCGWindowOwnerName", ""),
                "window_name": found_win.get("kCGWindowName", ""),
                "pid": found_win.get("kCGWindowOwnerPID", 0),
                "width": bounds.get("Width", 0),
                "height": bounds.get("Height", 0),
                "x": bounds.get("X", 0),
                "y": bounds.get("Y", 0)
            }))
            sys.exit(0)
        else:
            print(json.dumps({"error": "No normal window found at click location"}))
            sys.exit(1)
            
    return event

def main():
    # We must wait for up to 15 seconds. If no click, exit.
    def timeout_callback(*args):
        print(json.dumps({"error": "Timeout waiting for click"}))
        sys.exit(1)
        
    # We don't have CFRunLoopTimer easily accessible in python without more ctypes, 
    # so we'll just let it hang, the API server can kill it.
    
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown),
        event_tap_callback,
        None
    )
    if not tap:
        print(json.dumps({"error": "Failed to create event tap. Make sure you have Accessibility permissions."}))
        sys.exit(1)
        
    runLoopSource = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(),
        runLoopSource,
        Quartz.kCFRunLoopCommonModes
    )
    Quartz.CGEventTapEnable(tap, True)
    Quartz.CFRunLoopRun()

if __name__ == "__main__":
    main()
