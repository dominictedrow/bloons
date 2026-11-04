"""PLAN.md step 0.2 — throwaway Mac feasibility check. Not part of the harness.

Run from Terminal (needs Screen Recording + Accessibility for Terminal):
    python3 scripts/feasibility_mac.py
Open BTD6+ and start a game on any map before step 3.
"""
import subprocess
import time

import mss
import mss.tools
import Quartz as Q

KEY_Q = 12  # macOS virtual keycode for Q (ANSI layout)


def find_window():
    wins = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly, Q.kCGNullWindowID)
    for w in wins:
        if "bloons" in (w.get("kCGWindowOwnerName") or "").lower() and w.get("kCGWindowLayer") == 0:
            return w
    return None


def click(x, y, post):
    for t in (Q.kCGEventMouseMoved, Q.kCGEventLeftMouseDown, Q.kCGEventLeftMouseUp):
        post(Q.CGEventCreateMouseEvent(None, t, (x, y), Q.kCGMouseButtonLeft))
        time.sleep(0.05)


def key(code, post):
    for down in (True, False):
        post(Q.CGEventCreateKeyboardEvent(None, code, down))
        time.sleep(0.05)


def ask(q):
    return input(f"{q} [y/n] ").strip().lower().startswith("y")


def main():
    w = find_window()
    if not w:
        raise SystemExit("No on-screen window with 'Bloons' in its owner name. Is the game open?")
    b, pid, owner = w["kCGWindowBounds"], w["kCGWindowOwnerPID"], w["kCGWindowOwnerName"]
    print(f"1. window: owner={owner!r} pid={pid} bounds(points)={dict(b)}")

    with mss.mss() as sct:
        mon = {"left": int(b["X"]), "top": int(b["Y"]), "width": int(b["Width"]), "height": int(b["Height"])}
        img = sct.grab(mon)
        mss.tools.to_png(img.rgb, img.size, output="frame.png")
    print(f"2. captured {img.size} px -> frame.png (pixels/points = {img.size[0] / b['Width']:.1f})")

    subprocess.run(["osascript", "-e", f'tell application "{owner}" to activate'], check=False)
    input("3. In-game, nothing selected. Press Enter, then don't touch anything for 3 s...")
    time.sleep(1)

    results = {}
    hid = lambda e: Q.CGEventPost(Q.kCGHIDEventTap, e)
    to_pid = lambda e: Q.CGEventPostToPid(pid, e)
    for name, post in (("HID tap", hid), ("PostToPid", to_pid)):
        key(KEY_Q, post)
        time.sleep(0.5)
        results[f"Q key via {name} selected Dart Monkey"] = ask(f"   [{name}] Did Q select the Dart Monkey?")
        subprocess.run(["osascript", "-e", f'tell application "{owner}" to activate'], check=False)
        time.sleep(0.5)
        key(53, post)  # Esc to deselect; harmless if ignored

    cx, cy = b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2
    for name, post in (("HID tap", hid), ("PostToPid", to_pid)):
        click(cx, cy, post)
        time.sleep(0.5)
        results[f"click via {name} registered"] = ask(f"   [{name}] Did a click land at the window centre?")
        subprocess.run(["osascript", "-e", f'tell application "{owner}" to activate'], check=False)
        time.sleep(0.5)

    print("\nResults (paste into RESEARCH.md):")
    for k, v in results.items():
        print(f"- {k}: {'YES' if v else 'NO'}")
    if not any(results.values()):
        print("GATE FAILED: synthetic input ignored. Re-plan with the HID fallback (PLAN.md 0.2).")


if __name__ == "__main__":
    main()
